"""BRLSMASCA RL/Q-learning Numba solver with LP reduced-cost item evaluation.

This file is intentionally independent from ``BSCASMA_test_numba.py``. Shared
Numba kernels are duplicated so the RL and test-policy variants can evolve
without cross-file coupling.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
from numba import njit
from scipy.optimize import linprog

from ..engine.models import SolveResult
from ..problem import ProblemModel
from ..tools.continuous_to_binary import parse_ctf_kind
from ..tools.ctf_numba import ctf_flip_probability
from .BSMA import _argsort_pop_fit_desc_deterministic
from .BSMA_numba import _expect_mkp_problem_tensors


def _cp_list_cache_key(
    values: np.ndarray,
    weights: np.ndarray,
    capacities: np.ndarray,
) -> tuple[tuple[tuple[int, ...], str, bytes], ...]:
    return (
        (values.shape, values.dtype.str, values.tobytes()),
        (weights.shape, weights.dtype.str, weights.tobytes()),
        (capacities.shape, capacities.dtype.str, capacities.tobytes()),
    )


def _item_eval_cache_key(
    values: np.ndarray,
    weights: np.ndarray,
    capacities: np.ndarray,
    *,
    eval_group_decimals: int,
    eval_rc_eps: float,
    eval_x_eps: float,
    item_eval_method: str = "lp_rc_ordered",
    item_eval_seed: int | None = None,
    extra_params: tuple[Any, ...] = (),
) -> tuple[Any, ...]:
    return (
        _cp_list_cache_key(values, weights, capacities),
        int(eval_group_decimals),
        float(eval_rc_eps),
        float(eval_x_eps),
        str(item_eval_method),
        None if item_eval_seed is None else int(item_eval_seed),
        tuple(extra_params),
    )


def _coerce_bool_param(value: Any, *, name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    if isinstance(value, (int, np.integer)) and value in {0, 1}:
        return bool(value)
    raise ValueError(f"params.{name} must be a boolean")


def _safe_efficiency(values: np.ndarray, weighted_cost: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        efficiency = values / weighted_cost
    efficiency = np.asarray(efficiency, dtype=np.float64).ravel()
    positive_value = np.asarray(values, dtype=np.float64).ravel() > 0.0
    efficiency = np.where((weighted_cost <= 0.0) & positive_value, np.inf, efficiency)
    return np.nan_to_num(efficiency, nan=-np.inf, posinf=np.finfo(np.float64).max, neginf=-np.inf)


def _sort_items_by_bucket_efficiency(bucket: np.ndarray, efficiency: np.ndarray) -> np.ndarray:
    item_ids = np.arange(efficiency.size, dtype=np.int64)
    return np.ascontiguousarray(np.lexsort((item_ids, -efficiency, bucket)).astype(np.int64))


def _efficiency_group_count(base_order: np.ndarray, bucket: np.ndarray, rounded_efficiency: np.ndarray) -> int:
    group_count = 0
    start = 0
    items = int(base_order.size)
    while start < items:
        first = int(base_order[start])
        end = start + 1
        while end < items:
            current = int(base_order[end])
            if bucket[current] != bucket[first] or rounded_efficiency[current] != rounded_efficiency[first]:
                break
            end += 1
        if end - start > 1:
            group_count += 1
        start = end
    return group_count


def _shuffle_efficiency_groups(
    base_order: np.ndarray,
    bucket: np.ndarray,
    rounded_efficiency: np.ndarray,
) -> tuple[np.ndarray, int]:
    cp_list = np.ascontiguousarray(base_order.copy().astype(np.int64))
    group_count = 0
    start = 0
    items = int(cp_list.size)
    while start < items:
        first = int(cp_list[start])
        end = start + 1
        while end < items:
            current = int(cp_list[end])
            if bucket[current] != bucket[first] or rounded_efficiency[current] != rounded_efficiency[first]:
                break
            end += 1
        if end - start > 1:
            group_count += 1
            np.random.shuffle(cp_list[start:end])
        start = end
    return cp_list, group_count


def _dual_efficiency_fallback(
    values: np.ndarray,
    weights: np.ndarray,
    capacities: np.ndarray,
    *,
    eval_group_decimals: int,
) -> dict[str, Any]:
    constraints = np.concatenate((capacities, np.ones(values.size)))
    i_weight = -np.concatenate((weights, np.eye(values.size)), axis=1)
    i_profit = values * -1
    result = linprog(constraints, i_weight, i_profit, method="highs")
    if result.success and result.x is not None and result.x.size >= capacities.size:
        dual_price = np.asarray(result.x[: capacities.size], dtype=np.float64)
    else:
        dual_price = np.ones(capacities.size, dtype=np.float64)

    weighted_cost = np.matmul(dual_price.T, weights.T)
    efficiency = _safe_efficiency(values, np.asarray(weighted_cost, dtype=np.float64))
    bucket = np.zeros(values.size, dtype=np.int64)
    base_order = _sort_items_by_bucket_efficiency(bucket, efficiency)
    rounded_efficiency = np.round(efficiency, decimals=int(eval_group_decimals))
    return {
        "base_order": base_order,
        "bucket": bucket,
        "rounded_efficiency": np.asarray(rounded_efficiency, dtype=np.float64),
        "efficiency": efficiency,
        "x_lp": np.zeros(values.size, dtype=np.float64),
        "reduced_cost": np.zeros(values.size, dtype=np.float64),
        "dual_price": dual_price,
        "lp_fractional_count": 0,
        "eff_group_count": _efficiency_group_count(base_order, bucket, rounded_efficiency),
        "fallback": True,
    }


def _build_lp_rc_item_eval_payload(
    values: np.ndarray,
    weights: np.ndarray,
    capacities: np.ndarray,
    *,
    eval_group_decimals: int,
    eval_rc_eps: float,
    eval_x_eps: float,
) -> dict[str, Any]:
    result = linprog(
        c=-np.asarray(values, dtype=np.float64),
        A_ub=np.asarray(weights, dtype=np.float64).T,
        b_ub=np.asarray(capacities, dtype=np.float64),
        bounds=[(0.0, 1.0)] * int(values.size),
        method="highs",
    )
    if (
        not result.success
        or result.x is None
        or result.x.size != values.size
        or not hasattr(result, "ineqlin")
        or not hasattr(result.ineqlin, "marginals")
    ):
        return _dual_efficiency_fallback(
            values,
            weights,
            capacities,
            eval_group_decimals=eval_group_decimals,
        )

    x_lp = np.asarray(result.x, dtype=np.float64).ravel()
    dual_price = -np.asarray(result.ineqlin.marginals, dtype=np.float64).ravel()
    weighted_cost = np.matmul(dual_price.T, weights.T)
    weighted_cost = np.asarray(weighted_cost, dtype=np.float64).ravel()
    efficiency = _safe_efficiency(np.asarray(values, dtype=np.float64), weighted_cost)
    reduced_cost = np.asarray(values, dtype=np.float64).ravel() - weighted_cost

    bucket = np.full(values.size, 2, dtype=np.int64)
    core_mask = ((x_lp > eval_x_eps) & (x_lp < 1.0 - eval_x_eps)) | (np.abs(reduced_cost) <= eval_rc_eps)
    strong_mask = (x_lp >= 1.0 - eval_x_eps) | (reduced_cost > eval_rc_eps)
    bucket[core_mask] = 1
    bucket[strong_mask] = 0

    base_order = _sort_items_by_bucket_efficiency(bucket, efficiency)
    rounded_efficiency = np.asarray(np.round(efficiency, decimals=int(eval_group_decimals)), dtype=np.float64)
    fractional_mask = (x_lp > eval_x_eps) & (x_lp < 1.0 - eval_x_eps)
    return {
        "base_order": base_order,
        "bucket": bucket,
        "rounded_efficiency": rounded_efficiency,
        "efficiency": efficiency,
        "x_lp": x_lp,
        "reduced_cost": reduced_cost,
        "dual_price": dual_price,
        "lp_fractional_count": int(np.count_nonzero(fractional_mask)),
        "eff_group_count": _efficiency_group_count(base_order, bucket, rounded_efficiency),
        "fallback": False,
    }


def _robust_minmax(x: np.ndarray, *, q_low: float = 0.05, q_high: float = 0.95) -> np.ndarray:
    arr = np.asarray(x, dtype=np.float64).ravel()
    if arr.size == 0:
        return arr.copy()
    finite = np.isfinite(arr)
    if not np.any(finite):
        return np.zeros(arr.size, dtype=np.float64)
    clean = arr.copy()
    finite_values = clean[finite]
    min_finite = float(np.min(finite_values))
    max_finite = float(np.max(finite_values))
    clean[~finite & (clean > 0.0)] = max_finite
    clean[~finite & (clean <= 0.0)] = min_finite
    lo = float(np.quantile(clean, q_low))
    hi = float(np.quantile(clean, q_high))
    if math.isclose(hi, lo):
        return np.zeros(arr.size, dtype=np.float64)
    return np.clip((clean - lo) / (hi - lo + 1.0e-12), 0.0, 1.0)


def _clean_efficiency_for_score(efficiency: np.ndarray) -> np.ndarray:
    eff = np.asarray(efficiency, dtype=np.float64).ravel()
    finite = np.isfinite(eff)
    clean = eff.copy()
    if np.any(finite):
        max_finite = float(np.max(clean[finite]))
        clean[~finite & (clean > 0.0)] = max_finite
    clean[~finite & (clean <= 0.0)] = 0.0
    return np.nan_to_num(clean, nan=0.0, posinf=0.0, neginf=0.0)


def _bucket_score(bucket: np.ndarray) -> np.ndarray:
    bucket_i = np.asarray(bucket, dtype=np.int64).ravel()
    score = np.zeros(bucket_i.size, dtype=np.float64)
    score[bucket_i == 0] = 1.00
    score[bucket_i == 1] = 0.55
    return score


def _build_core_score_cp_payload(
    base_payload: dict[str, Any],
    *,
    core_w_x_lp: float,
    core_w_rc: float,
    core_w_eff: float,
    core_w_bucket: float,
) -> dict[str, Any]:
    x_lp = np.asarray(base_payload["x_lp"], dtype=np.float64).ravel()
    reduced_cost = np.asarray(base_payload["reduced_cost"], dtype=np.float64).ravel()
    efficiency = np.asarray(base_payload["efficiency"], dtype=np.float64).ravel()
    bucket = np.asarray(base_payload["bucket"], dtype=np.int64).ravel()

    x_score = np.clip(x_lp, 0.0, 1.0)
    rc_score = _robust_minmax(reduced_cost)
    eff_score = _robust_minmax(np.log1p(np.maximum(_clean_efficiency_for_score(efficiency), 0.0)))
    bucket_score = _bucket_score(bucket)
    core_score = (
        float(core_w_x_lp) * x_score
        + float(core_w_rc) * rc_score
        + float(core_w_eff) * eff_score
        + float(core_w_bucket) * bucket_score
    )
    item_ids = np.arange(core_score.size, dtype=np.int64)
    cp_list = np.ascontiguousarray(np.lexsort((item_ids, -eff_score, -core_score)).astype(np.int64))
    return {
        "base_order": cp_list,
        "cp_list": cp_list,
        "item_score": core_score,
        "core_score": core_score,
        "x_score": x_score,
        "rc_score": rc_score,
        "eff_score": eff_score,
        "bucket_score": bucket_score,
        "score_method": "core_score_cp",
        "item_eval_method": "core_score_cp",
        "guided_mode": "lp_original",
    }


def _repair_solution_by_order(
    initial_sol: np.ndarray,
    values: np.ndarray,
    weights: np.ndarray,
    capacities: np.ndarray,
    order: np.ndarray,
    *,
    repair_passes: int,
    repair_swap_limit: int,
) -> tuple[np.ndarray, int]:
    pop_sol = np.ascontiguousarray(np.asarray(initial_sol, dtype=np.float64).reshape(1, -1))
    pop_fit = np.asarray([float(np.dot(values, pop_sol[0]))], dtype=np.float64)
    resource = np.zeros(capacities.size, dtype=np.float64)
    repair_stats = np.zeros(1, dtype=np.int64)
    _repair_bscasma_row_v2_inplace(
        pop_sol,
        0,
        pop_fit,
        np.asarray(values, dtype=np.int64),
        np.asarray(weights, dtype=np.int64),
        np.asarray(capacities, dtype=np.int64),
        np.asarray(order, dtype=np.int64),
        resource,
        int(values.size),
        int(capacities.size),
        int(repair_passes),
        int(repair_swap_limit),
        repair_stats,
    )
    return np.asarray(pop_sol[0], dtype=np.float64), int(pop_fit[0])


def _greedy_solution_by_order(
    order: np.ndarray,
    values: np.ndarray,
    weights: np.ndarray,
    capacities: np.ndarray,
    *,
    repair_passes: int,
    repair_swap_limit: int,
) -> tuple[np.ndarray, int]:
    sol = np.zeros(values.size, dtype=np.float64)
    resource = np.zeros(capacities.size, dtype=np.float64)
    for item in np.asarray(order, dtype=np.int64):
        candidate = resource + weights[item]
        if np.all(candidate <= capacities):
            sol[item] = 1.0
            resource = candidate
    return _repair_solution_by_order(
        sol,
        values,
        weights,
        capacities,
        order,
        repair_passes=repair_passes,
        repair_swap_limit=repair_swap_limit,
    )


def _randomized_probe_solution(
    order: np.ndarray,
    score: np.ndarray,
    values: np.ndarray,
    weights: np.ndarray,
    capacities: np.ndarray,
    rng: np.random.Generator,
    *,
    repair_passes: int,
    repair_swap_limit: int,
) -> tuple[np.ndarray, int]:
    sol = np.zeros(values.size, dtype=np.float64)
    resource = np.zeros(capacities.size, dtype=np.float64)
    clipped_score = np.clip(np.asarray(score, dtype=np.float64), 0.0, 1.0)
    for item in np.asarray(order, dtype=np.int64):
        p_add = 0.15 + 0.75 * clipped_score[item]
        if rng.random() >= p_add:
            continue
        candidate = resource + weights[item]
        if np.all(candidate <= capacities):
            sol[item] = 1.0
            resource = candidate
    return _repair_solution_by_order(
        sol,
        values,
        weights,
        capacities,
        order,
        repair_passes=repair_passes,
        repair_swap_limit=repair_swap_limit,
    )


def _freq_samples_and_rho(
    dim: int,
    *,
    freq_samples_dim5: int,
    freq_samples_dim10: int,
    freq_samples_dim30: int,
    freq_blend_rho_dim5: float,
    freq_blend_rho_dim10: float,
    freq_blend_rho_dim30: float,
) -> tuple[int, float]:
    if dim <= 5:
        return int(freq_samples_dim5), float(freq_blend_rho_dim5)
    if dim <= 10:
        return int(freq_samples_dim10), float(freq_blend_rho_dim10)
    return int(freq_samples_dim30), float(freq_blend_rho_dim30)


def _build_freq_gated_v2_payload(
    values: np.ndarray,
    weights: np.ndarray,
    capacities: np.ndarray,
    base_payload: dict[str, Any],
    rng: np.random.Generator,
    *,
    core_w_x_lp: float,
    core_w_rc: float,
    core_w_eff: float,
    core_w_bucket: float,
    eval_group_decimals: int,
    eval_rc_eps: float,
    eval_x_eps: float,
    freq_cp_noise: float,
    freq_elite_ratio: float,
    freq_quality_power: float,
    freq_samples_dim5: int,
    freq_samples_dim10: int,
    freq_samples_dim30: int,
    freq_blend_rho_dim5: float,
    freq_blend_rho_dim10: float,
    freq_blend_rho_dim30: float,
    freq_gate_probe_margin: float,
    freq_gate_min_elites: int,
    freq_gate_min_std: float,
    freq_gate_min_topk_overlap: float,
    repair_passes: int,
    repair_swap_limit: int,
) -> dict[str, Any]:
    values_f = np.asarray(values, dtype=np.float64)
    weights_i = np.asarray(weights, dtype=np.int64)
    capacities_i = np.asarray(capacities, dtype=np.int64)
    core_payload = _build_core_score_cp_payload(
        base_payload,
        core_w_x_lp=core_w_x_lp,
        core_w_rc=core_w_rc,
        core_w_eff=core_w_eff,
        core_w_bucket=core_w_bucket,
    )
    core_score = np.asarray(core_payload["core_score"], dtype=np.float64)
    core_order = np.asarray(core_payload["cp_list"], dtype=np.int64)
    core_sol, core_fit = _greedy_solution_by_order(
        core_order,
        np.asarray(values, dtype=np.int64),
        weights_i,
        capacities_i,
        repair_passes=repair_passes,
        repair_swap_limit=repair_swap_limit,
    )
    samples, rho = _freq_samples_and_rho(
        int(capacities_i.size),
        freq_samples_dim5=freq_samples_dim5,
        freq_samples_dim10=freq_samples_dim10,
        freq_samples_dim30=freq_samples_dim30,
        freq_blend_rho_dim5=freq_blend_rho_dim5,
        freq_blend_rho_dim10=freq_blend_rho_dim10,
        freq_blend_rho_dim30=freq_blend_rho_dim30,
    )
    probe_solutions: list[np.ndarray] = []
    probe_fits: list[int] = []
    for _ in range(samples):
        noise = rng.uniform(-float(freq_cp_noise), float(freq_cp_noise), size=values_f.size)
        perturbed_values = values_f * (1.0 + noise)
        payload_r = _build_lp_rc_item_eval_payload(
            perturbed_values,
            weights_i,
            capacities_i,
            eval_group_decimals=eval_group_decimals,
            eval_rc_eps=eval_rc_eps,
            eval_x_eps=eval_x_eps,
        )
        score_payload_r = _build_core_score_cp_payload(
            payload_r,
            core_w_x_lp=core_w_x_lp,
            core_w_rc=core_w_rc,
            core_w_eff=core_w_eff,
            core_w_bucket=core_w_bucket,
        )
        score_r = np.asarray(score_payload_r["core_score"], dtype=np.float64)
        order_r = np.asarray(score_payload_r["cp_list"], dtype=np.int64)
        sol_r, fit_r = _randomized_probe_solution(
            order_r,
            score_r,
            np.asarray(values, dtype=np.int64),
            weights_i,
            capacities_i,
            rng,
            repair_passes=repair_passes,
            repair_swap_limit=repair_swap_limit,
        )
        probe_solutions.append(sol_r)
        probe_fits.append(fit_r)

    best_probe_fit = int(max(probe_fits)) if probe_fits else 0
    fallback_reason = ""
    if best_probe_fit < float(core_fit) * (1.0 + float(freq_gate_probe_margin)):
        fallback_reason = "probe_margin_low"

    elite_idx = [
        idx
        for idx, fit in enumerate(probe_fits)
        if best_probe_fit > 0 and fit >= float(best_probe_fit) * float(freq_elite_ratio)
    ]
    if not fallback_reason and len(elite_idx) < int(freq_gate_min_elites):
        fallback_reason = "too_few_elites"

    freq_score = np.zeros(values_f.size, dtype=np.float64)
    weight_sum = 0.0
    if not fallback_reason:
        for idx in elite_idx:
            quality = float(probe_fits[idx]) / max(float(best_probe_fit), 1.0e-12)
            q = quality ** float(freq_quality_power)
            freq_score += q * probe_solutions[idx]
            weight_sum += q
        freq_score = freq_score / max(weight_sum, 1.0e-12)
        freq_score_std = float(np.std(freq_score))
        if freq_score_std < float(freq_gate_min_std):
            fallback_reason = "low_freq_variance"
    else:
        freq_score_std = 0.0

    blended_score = float(rho) * core_score + (1.0 - float(rho)) * freq_score
    k = int(np.sum(core_sol))
    if not fallback_reason:
        top_k = max(k, 1)
        top_core = set(np.argsort(-core_score)[:top_k].tolist())
        top_blend = set(np.argsort(-blended_score)[:top_k].tolist())
        topk_overlap = len(top_core & top_blend) / float(top_k)
        if topk_overlap < float(freq_gate_min_topk_overlap):
            fallback_reason = "low_topk_overlap"
    else:
        topk_overlap = 0.0

    if fallback_reason:
        fallback_payload = dict(core_payload)
        fallback_payload.update(
            {
                "item_eval_method": "freq_gated_v2_fallback_core",
                "score_method": "freq_gated_v2_fallback_core",
                "freq_score": freq_score,
                "freq_samples": int(samples),
                "freq_rho": float(rho),
                "freq_elite_count": int(len(elite_idx)),
                "freq_best_probe_fit": int(best_probe_fit),
                "freq_core_greedy_fit": int(core_fit),
                "freq_topk_overlap": float(topk_overlap),
                "freq_score_std": float(freq_score_std),
                "freq_fallback": True,
                "freq_fallback_reason": fallback_reason,
                "guided_mode": "lp_original",
            }
        )
        return fallback_payload

    item_ids = np.arange(values_f.size, dtype=np.int64)
    cp_list = np.ascontiguousarray(np.lexsort((item_ids, -core_score, -blended_score)).astype(np.int64))
    return {
        "base_order": cp_list,
        "cp_list": cp_list,
        "item_score": blended_score,
        "core_score": core_score,
        "freq_score": freq_score,
        "score_method": "freq_gated_v2",
        "item_eval_method": "freq_gated_v2",
        "freq_samples": int(samples),
        "freq_rho": float(rho),
        "freq_elite_count": int(len(elite_idx)),
        "freq_best_probe_fit": int(best_probe_fit),
        "freq_core_greedy_fit": int(core_fit),
        "freq_topk_overlap": float(topk_overlap),
        "freq_score_std": float(freq_score_std),
        "freq_fallback": False,
        "freq_fallback_reason": "",
        "guided_x": np.clip(blended_score, 0.0, 1.0),
        "guided_mode": "freq_blended_score",
    }


@njit(cache=True)
def _sort_bscasma_rl_desc_deterministic_inplace(
    pop_sol: np.ndarray,
    pop_fit: np.ndarray,
    individual_ids: np.ndarray,
    row_hamming: np.ndarray,
    tmp_sol: np.ndarray,
    tmp_fit: np.ndarray,
    tmp_ids: np.ndarray,
    tmp_hamming: np.ndarray,
    idx_work: np.ndarray,
    pop_size: int,
    items: int,
) -> None:
    for i in range(pop_size):
        idx_work[i] = i
    for i in range(pop_size):
        bi = i
        for j in range(i + 1, pop_size):
            ia = idx_work[j]
            ib = idx_work[bi]
            fa = pop_fit[ia]
            fb = pop_fit[ib]
            if fa > fb or (fa == fb and ia < ib):
                bi = j
        t = idx_work[i]
        idx_work[i] = idx_work[bi]
        idx_work[bi] = t
    for i in range(pop_size):
        si = idx_work[i]
        for j in range(items):
            tmp_sol[i, j] = pop_sol[si, j]
        tmp_fit[i] = pop_fit[si]
        tmp_ids[i] = individual_ids[si]
        tmp_hamming[i] = row_hamming[si]
    for i in range(pop_size):
        for j in range(items):
            pop_sol[i, j] = tmp_sol[i, j]
        pop_fit[i] = tmp_fit[i]
        individual_ids[i] = tmp_ids[i]
        row_hamming[i] = tmp_hamming[i]


@njit(cache=True)
def _update_sma_weight_inplace(W: np.ndarray, pop_fit: np.ndarray, pop_size: int, items: int) -> None:
    worst_fit = pop_fit[pop_size - 1]
    best_fit = pop_fit[0]
    S = best_fit - worst_fit
    if S <= 0.0:
        S = 0.0001
    for i in range(pop_size):
        ratio = (best_fit - pop_fit[i]) / S + 1.0
        logr = np.log10(ratio)
        if i < pop_size / 2:
            for j in range(items):
                W[i, j] = 1.0 + np.random.random() * logr
        else:
            for j in range(items):
                W[i, j] = 1.0 - np.random.random() * logr


@njit(cache=True)
def _ctf_flip_probability_fast(ctf_id: int, x: float) -> float:
    if ctf_id == 0:
        return abs(math.tanh(x))
    if ctf_id == 1:
        if x >= 0.0:
            return 1.0 / (1.0 + math.exp(-x))
        et = math.exp(x)
        return et / (1.0 + et)
    if ctf_id == 9:
        return abs(x) ** 1.6
    return ctf_flip_probability(ctf_id, x)


@njit(cache=True)
def _clip01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


@njit(cache=True)
def _clip_symmetric_half(value: float) -> float:
    if value < -0.5:
        return -0.5
    if value > 0.5:
        return 0.5
    return value


@njit(cache=True)
def _guided_bucket_bias(bucket_value: int) -> float:
    if bucket_value == 0:
        return 1.0
    if bucket_value == 1:
        return 0.0
    return -1.0


@njit(cache=True)
def _guided_probability(
    ctf_id: int,
    continuous_value: float,
    x_lp_value: float,
    bucket_value: int,
    slack_score: float,
    guided_enabled: bool,
    guided_lambda_lp: float,
    guided_lambda_bucket: float,
    guided_lambda_slack: float,
) -> float:
    p = _ctf_flip_probability_fast(ctf_id, continuous_value)
    if guided_enabled:
        p += guided_lambda_lp * (x_lp_value - 0.5)
        p += guided_lambda_bucket * _guided_bucket_bias(bucket_value)
        p += guided_lambda_slack * _clip_symmetric_half(slack_score)
    return _clip01(p)


@njit(cache=True)
def _init_row_resource_from_bits(
    pop_sol: np.ndarray,
    row: int,
    weights: np.ndarray,
    resource: np.ndarray,
    items: int,
    dim: int,
) -> None:
    for d in range(dim):
        resource[d] = 0.0
    for j in range(items):
        if pop_sol[row, j] >= 0.5:
            for d in range(dim):
                resource[d] += weights[j, d]


@njit(cache=True)
def _resource_excluding_item_inplace(
    resource: np.ndarray,
    old_bit: float,
    weights: np.ndarray,
    item: int,
    dim: int,
) -> None:
    if old_bit >= 0.5:
        for d in range(dim):
            resource[d] -= weights[item, d]


@njit(cache=True)
def _guided_slack_score(
    resource_excluding_item: np.ndarray,
    weights: np.ndarray,
    capacities: np.ndarray,
    item: int,
    dim: int,
) -> float:
    best = 1.0e12
    for d in range(dim):
        denom = float(weights[item, d]) + 1.0e-12
        score = (float(capacities[d]) - resource_excluding_item[d]) / denom
        if score < best:
            best = score
    return _clip_symmetric_half(best)


@njit(cache=True)
def _set_guided_binary_bit_and_update_resource(
    pop_sol: np.ndarray,
    row: int,
    item: int,
    probability: float,
    weights: np.ndarray,
    resource_excluding_item: np.ndarray,
    dim: int,
) -> None:
    new_bit = 1.0 if np.random.random() < probability else 0.0
    pop_sol[row, item] = new_bit
    if new_bit >= 0.5:
        for d in range(dim):
            resource_excluding_item[d] += weights[item, d]


@njit(cache=True)
def _repair_bscasma_row_inplace(
    pop_sol: np.ndarray,
    row: int,
    pop_fit: np.ndarray,
    values: np.ndarray,
    weights: np.ndarray,
    capacities: np.ndarray,
    cp_list: np.ndarray,
    resource: np.ndarray,
    items: int,
    dim: int,
) -> None:
    for d in range(dim):
        resource[d] = 0.0
    fi = 0.0
    for jj in range(items):
        x = pop_sol[row, jj]
        if x != 0.0:
            for d in range(dim):
                resource[d] += weights[jj, d] * x
        if x >= 0.5:
            fi += float(values[jj])

    for pos in range(items - 1, -1, -1):
        jj = int(cp_list[pos])
        over = False
        for d in range(dim):
            if resource[d] > capacities[d]:
                over = True
                break
        if not over:
            break
        if pop_sol[row, jj] == 1.0:
            pop_sol[row, jj] = 0.0
            fi -= float(values[jj])
            for d in range(dim):
                resource[d] -= weights[jj, d]

    for pos in range(items):
        jj = int(cp_list[pos])
        if pop_sol[row, jj] == 0.0:
            ok = True
            for d in range(dim):
                if resource[d] + weights[jj, d] > capacities[d]:
                    ok = False
                    break
            if ok:
                pop_sol[row, jj] = 1.0
                fi += float(values[jj])
                for d in range(dim):
                    resource[d] += weights[jj, d]

    pop_fit[row] = fi


@njit(cache=True)
def _repair_bscasma_swap_once_inplace(
    pop_sol: np.ndarray,
    row: int,
    pop_fit: np.ndarray,
    values: np.ndarray,
    weights: np.ndarray,
    capacities: np.ndarray,
    cp_list: np.ndarray,
    resource: np.ndarray,
    items: int,
    dim: int,
) -> int:
    fi = pop_fit[row]
    for out_pos in range(items - 1, -1, -1):
        j_out = int(cp_list[out_pos])
        if pop_sol[row, j_out] != 1.0:
            continue
        for in_pos in range(items):
            j_in = int(cp_list[in_pos])
            if pop_sol[row, j_in] != 0.0:
                continue
            if values[j_in] <= values[j_out]:
                continue
            ok = True
            for d in range(dim):
                if resource[d] - weights[j_out, d] + weights[j_in, d] > capacities[d]:
                    ok = False
                    break
            if ok:
                pop_sol[row, j_out] = 0.0
                pop_sol[row, j_in] = 1.0
                pop_fit[row] = fi - float(values[j_out]) + float(values[j_in])
                for d in range(dim):
                    resource[d] += weights[j_in, d] - weights[j_out, d]
                return 1
    return 0


@njit(cache=True)
def _repair_bscasma_row_v2_inplace(
    pop_sol: np.ndarray,
    row: int,
    pop_fit: np.ndarray,
    values: np.ndarray,
    weights: np.ndarray,
    capacities: np.ndarray,
    cp_list: np.ndarray,
    resource: np.ndarray,
    items: int,
    dim: int,
    repair_passes: int,
    repair_swap_limit: int,
    repair_stats: np.ndarray,
) -> None:
    accepted_swaps = 0
    for _ in range(repair_passes):
        _repair_bscasma_row_inplace(
            pop_sol,
            row,
            pop_fit,
            values,
            weights,
            capacities,
            cp_list,
            resource,
            items,
            dim,
        )
        while accepted_swaps < repair_swap_limit:
            accepted = _repair_bscasma_swap_once_inplace(
                pop_sol,
                row,
                pop_fit,
                values,
                weights,
                capacities,
                cp_list,
                resource,
                items,
                dim,
            )
            if accepted == 0:
                break
            accepted_swaps += accepted
            repair_stats[0] += accepted
        if repair_swap_limit > 0 and accepted_swaps > 0:
            _repair_bscasma_row_inplace(
                pop_sol,
                row,
                pop_fit,
                values,
                weights,
                capacities,
                cp_list,
                resource,
                items,
                dim,
            )


@njit(cache=True)
def _copy_row_to_work(pop_sol: np.ndarray, row: int, work_row: np.ndarray, items: int) -> None:
    for j in range(items):
        work_row[j] = 1.0 if pop_sol[row, j] >= 0.5 else 0.0


@njit(cache=True)
def _restore_work_to_row(
    pop_sol: np.ndarray,
    row: int,
    work_row: np.ndarray,
    pop_fit: np.ndarray,
    fit_value: float,
    items: int,
) -> None:
    for j in range(items):
        pop_sol[row, j] = work_row[j]
    pop_fit[row] = fit_value


@njit(cache=True)
def _local_search_bscasma_row_inplace(
    pop_sol: np.ndarray,
    row: int,
    pop_fit: np.ndarray,
    values: np.ndarray,
    weights: np.ndarray,
    capacities: np.ndarray,
    cp_list: np.ndarray,
    resource: np.ndarray,
    items: int,
    dim: int,
    repair_passes: int,
    repair_swap_limit: int,
    repair_stats: np.ndarray,
    ls_work_row: np.ndarray,
    ls_max_passes: int,
    ls_add_cap: int,
    ls_drop_cap: int,
    ls_budget_per_run: int,
    ls_stats: np.ndarray,
) -> None:
    if ls_budget_per_run <= 0 or ls_stats[3] >= ls_budget_per_run:
        return
    ls_stats[0] += 1
    passes = 0
    while passes < ls_max_passes and ls_stats[3] < ls_budget_per_run:
        base_fit = pop_fit[row]
        _copy_row_to_work(pop_sol, row, ls_work_row, items)
        accepted = False

        add_seen = 0
        for pos in range(items):
            if add_seen >= ls_add_cap or ls_stats[3] >= ls_budget_per_run:
                break
            jj = int(cp_list[pos])
            if ls_work_row[jj] != 0.0:
                continue
            add_seen += 1
            _restore_work_to_row(pop_sol, row, ls_work_row, pop_fit, base_fit, items)
            pop_sol[row, jj] = 1.0
            _repair_bscasma_row_v2_inplace(
                pop_sol,
                row,
                pop_fit,
                values,
                weights,
                capacities,
                cp_list,
                resource,
                items,
                dim,
                repair_passes,
                repair_swap_limit,
                repair_stats,
            )
            ls_stats[1] += 1
            ls_stats[3] += 1
            if pop_fit[row] > base_fit:
                ls_stats[2] += 1
                accepted = True
                break

        if accepted:
            passes += 1
            continue

        drop_seen = 0
        for pos in range(items - 1, -1, -1):
            if drop_seen >= ls_drop_cap or ls_stats[3] >= ls_budget_per_run:
                break
            jj = int(cp_list[pos])
            if ls_work_row[jj] != 1.0:
                continue
            drop_seen += 1
            _restore_work_to_row(pop_sol, row, ls_work_row, pop_fit, base_fit, items)
            pop_sol[row, jj] = 0.0
            _repair_bscasma_row_v2_inplace(
                pop_sol,
                row,
                pop_fit,
                values,
                weights,
                capacities,
                cp_list,
                resource,
                items,
                dim,
                repair_passes,
                repair_swap_limit,
                repair_stats,
            )
            ls_stats[1] += 1
            ls_stats[3] += 1
            if pop_fit[row] > base_fit:
                ls_stats[2] += 1
                accepted = True
                break

        if not accepted:
            _restore_work_to_row(pop_sol, row, ls_work_row, pop_fit, base_fit, items)
            break
        passes += 1


@njit(cache=True)
def _restart_bscasma_bucket_biased_row_inplace(
    pop_sol: np.ndarray,
    row: int,
    pop_fit: np.ndarray,
    values: np.ndarray,
    weights: np.ndarray,
    capacities: np.ndarray,
    cp_list: np.ndarray,
    bucket: np.ndarray,
    resource: np.ndarray,
    items: int,
    dim: int,
    strong_p: float,
    core_p: float,
    weak_p: float,
) -> None:
    for j in range(items):
        pop_sol[row, j] = 0.0
    for d in range(dim):
        resource[d] = 0.0

    fi = 0.0
    for pos in range(items):
        jj = int(cp_list[pos])
        bj = int(bucket[jj])
        p = weak_p
        if bj == 0:
            p = strong_p
        elif bj == 1:
            p = core_p
        if np.random.random() >= p:
            continue

        ok = True
        for d in range(dim):
            if resource[d] + weights[jj, d] > capacities[d]:
                ok = False
                break
        if ok:
            pop_sol[row, jj] = 1.0
            fi += float(values[jj])
            for d in range(dim):
                resource[d] += weights[jj, d]

    pop_fit[row] = fi


@njit(cache=True)
def _archive_hamming_distance(
    archive_sol: np.ndarray,
    archive_idx: int,
    candidate_sol: np.ndarray,
    items: int,
) -> int:
    distance = 0
    for j in range(items):
        a = 1.0 if archive_sol[archive_idx, j] >= 0.5 else 0.0
        b = 1.0 if candidate_sol[j] >= 0.5 else 0.0
        if a != b:
            distance += 1
    return distance


@njit(cache=True)
def _archive_contains_vector(
    archive_sol: np.ndarray,
    archive_count: np.ndarray,
    candidate_sol: np.ndarray,
    items: int,
) -> bool:
    count = int(archive_count[0])
    for i in range(count):
        same = True
        for j in range(items):
            if archive_sol[i, j] != candidate_sol[j]:
                same = False
                break
        if same:
            return True
    return False


@njit(cache=True)
def _archive_add_vector(
    archive_sol: np.ndarray,
    archive_fit: np.ndarray,
    archive_count: np.ndarray,
    candidate_sol: np.ndarray,
    candidate_fit: float,
    archive_size: int,
    items: int,
) -> int:
    if _archive_contains_vector(archive_sol, archive_count, candidate_sol, items):
        return 0
    count = int(archive_count[0])
    if count < archive_size:
        target = count
        archive_count[0] = count + 1
    else:
        target = 0
        for i in range(1, archive_size):
            if archive_fit[i] < archive_fit[target]:
                target = i
        if candidate_fit <= archive_fit[target]:
            return 0
    for j in range(items):
        archive_sol[target, j] = candidate_sol[j]
    archive_fit[target] = candidate_fit
    return 1


@njit(cache=True)
def _archive_add_row(
    archive_sol: np.ndarray,
    archive_fit: np.ndarray,
    archive_count: np.ndarray,
    pop_sol: np.ndarray,
    pop_fit: np.ndarray,
    row: int,
    archive_size: int,
    items: int,
    work_row: np.ndarray,
) -> int:
    for j in range(items):
        work_row[j] = 1.0 if pop_sol[row, j] >= 0.5 else 0.0
    return _archive_add_vector(
        archive_sol,
        archive_fit,
        archive_count,
        work_row,
        pop_fit[row],
        archive_size,
        items,
    )


@njit(cache=True)
def _archive_select_donor(
    archive_sol: np.ndarray,
    archive_fit: np.ndarray,
    archive_count: np.ndarray,
    gbest_sol: np.ndarray,
    items: int,
) -> int:
    count = int(archive_count[0])
    best_idx = -1
    best_distance = -1
    best_fit = -1.0
    for i in range(count):
        distance = _archive_hamming_distance(archive_sol, i, gbest_sol, items)
        if distance <= 0:
            continue
        fit = archive_fit[i]
        if distance > best_distance or (distance == best_distance and fit > best_fit):
            best_idx = i
            best_distance = distance
            best_fit = fit
    return best_idx


@njit(cache=True)
def _path_relink_bscasma_inplace(
    archive_sol: np.ndarray,
    archive_fit: np.ndarray,
    archive_count: np.ndarray,
    archive_size: int,
    gbest_sol: np.ndarray,
    gbest_fit: float,
    values: np.ndarray,
    weights: np.ndarray,
    capacities: np.ndarray,
    cp_list: np.ndarray,
    bucket: np.ndarray,
    pr_sol: np.ndarray,
    pr_fit: np.ndarray,
    resource: np.ndarray,
    repair_passes: int,
    repair_swap_limit: int,
    repair_stats: np.ndarray,
    pr_max_steps: int,
    pr_core_only: bool,
    pr_stats: np.ndarray,
    items: int,
    dim: int,
) -> float:
    if int(archive_count[0]) < 2:
        return gbest_fit
    donor_idx = _archive_select_donor(archive_sol, archive_fit, archive_count, gbest_sol, items)
    if donor_idx < 0:
        return gbest_fit

    pr_stats[0] += 1
    for j in range(items):
        pr_sol[0, j] = 1.0 if gbest_sol[j] >= 0.5 else 0.0
    pr_fit[0] = gbest_fit
    best_before = gbest_fit
    steps = 0
    fallback_mode = False

    for scan_mode in range(2):
        if scan_mode == 1:
            if steps > 0 or not pr_core_only:
                break
            fallback_mode = True
        for pos in range(items):
            if steps >= pr_max_steps:
                break
            jj = int(cp_list[pos])
            bj = int(bucket[jj])
            if pr_core_only and not fallback_mode and bj != 1:
                continue
            if fallback_mode and bj > 1:
                continue
            donor_bit = 1.0 if archive_sol[donor_idx, jj] >= 0.5 else 0.0
            current_bit = 1.0 if pr_sol[0, jj] >= 0.5 else 0.0
            if donor_bit == current_bit:
                continue
            pr_sol[0, jj] = donor_bit
            _repair_bscasma_row_v2_inplace(
                pr_sol,
                0,
                pr_fit,
                values,
                weights,
                capacities,
                cp_list,
                resource,
                items,
                dim,
                repair_passes,
                repair_swap_limit,
                repair_stats,
            )
            pr_stats[1] += 1
            steps += 1
            if pr_fit[0] > gbest_fit:
                gbest_fit = pr_fit[0]
                for j in range(items):
                    gbest_sol[j] = pr_sol[0, j]
        if steps >= pr_max_steps:
            break

    if gbest_fit > best_before:
        pr_stats[2] += 1
        _archive_add_vector(
            archive_sol,
            archive_fit,
            archive_count,
            gbest_sol,
            gbest_fit,
            archive_size,
            items,
        )
    return gbest_fit


@njit(cache=True)
def _state_bin(value: float) -> int:
    if value <= (1.0 / 3.0):
        return 0
    if value <= (2.0 / 3.0):
        return 1
    return 2


@njit(cache=True)
def _init_ones_count(pop_sol: np.ndarray, ones_count: np.ndarray, pop_size: int, items: int) -> None:
    for j in range(items):
        ones_count[j] = 0
    for i in range(pop_size):
        for j in range(items):
            if pop_sol[i, j] >= 0.5:
                ones_count[j] += 1


@njit(cache=True)
def _init_density_state(
    pop_sol: np.ndarray,
    ones_count: np.ndarray,
    avg_bits: np.ndarray,
    row_hamming: np.ndarray,
    sqrt_lookup: np.ndarray,
    pop_size: int,
    items: int,
) -> float:
    _init_ones_count(pop_sol, ones_count, pop_size, items)
    for j in range(items):
        avg_bits[j] = 1.0 if ones_count[j] * 2 >= pop_size else 0.0
    density_sum = 0.0
    for i in range(pop_size):
        hd = 0.0
        for j in range(items):
            bit = 1.0 if pop_sol[i, j] >= 0.5 else 0.0
            if bit != avg_bits[j]:
                hd += 1.0
        row_hamming[i] = hd
        density_sum += sqrt_lookup[int(hd)]
    return density_sum


@njit(cache=True)
def _copy_row_bits(pop_sol: np.ndarray, row: int, old_row: np.ndarray, items: int) -> None:
    for j in range(items):
        old_row[j] = 1.0 if pop_sol[row, j] >= 0.5 else 0.0


@njit(cache=True)
def _update_density_state_for_row(
    pop_sol: np.ndarray,
    row: int,
    old_row: np.ndarray,
    ones_count: np.ndarray,
    avg_bits: np.ndarray,
    row_hamming: np.ndarray,
    density_sum: float,
    sqrt_lookup: np.ndarray,
    pop_size: int,
    items: int,
) -> float:
    for j in range(items):
        old_bit = 1 if old_row[j] >= 0.5 else 0
        new_bit = 1 if pop_sol[row, j] >= 0.5 else 0
        if old_bit == new_bit:
            continue

        old_avg = 1 if avg_bits[j] >= 0.5 else 0
        new_ones = ones_count[j] + new_bit - old_bit
        new_avg = 1 if new_ones * 2 >= pop_size else 0
        ones_count[j] = new_ones
        avg_bits[j] = float(new_avg)

        if old_avg != new_avg:
            for i in range(pop_size):
                before = row_hamming[i]
                if i == row:
                    bit_before = old_bit
                    bit_after = new_bit
                else:
                    bit_before = 1 if pop_sol[i, j] >= 0.5 else 0
                    bit_after = bit_before
                old_mismatch = 1 if bit_before != old_avg else 0
                new_mismatch = 1 if bit_after != new_avg else 0
                delta = new_mismatch - old_mismatch
                if delta != 0:
                    after = before + float(delta)
                    row_hamming[i] = after
                    density_sum += sqrt_lookup[int(after)] - sqrt_lookup[int(before)]
        else:
            before = row_hamming[row]
            old_mismatch = 1 if old_bit != old_avg else 0
            new_mismatch = 1 if new_bit != old_avg else 0
            delta = new_mismatch - old_mismatch
            if delta != 0:
                after = before + float(delta)
                row_hamming[row] = after
                density_sum += sqrt_lookup[int(after)] - sqrt_lookup[int(before)]
    return density_sum


@njit(cache=True)
def _population_density_from_counts(
    pop_sol: np.ndarray,
    ones_count: np.ndarray,
    sqrt_lookup: np.ndarray,
    pop_size: int,
    items: int,
) -> float:
    total = 0.0
    for i in range(pop_size):
        hd = 0.0
        for j in range(items):
            avg_bit = 1.0 if ones_count[j] * 2 >= pop_size else 0.0
            bit = 1.0 if pop_sol[i, j] >= 0.5 else 0.0
            if bit != avg_bit:
                hd += 1.0
        total += sqrt_lookup[int(hd)]
    return total / (float(pop_size) * float(items))


@njit(cache=True)
def _state_for_row(
    pop_sol: np.ndarray,
    row: int,
    gbest_sol: np.ndarray,
    pop_size: int,
    items: int,
    density: float,
) -> int:
    distance = 0.0
    for j in range(items):
        bit = 1.0 if pop_sol[row, j] >= 0.5 else 0.0
        best_bit = 1.0 if gbest_sol[j] >= 0.5 else 0.0
        if bit != best_bit:
            distance += 1.0
    distance_norm = distance / float(items)
    return _state_bin(distance_norm) * 3 + _state_bin(density)


@njit(cache=True)
def _select_q_action_non_global(q_table: np.ndarray, individual_id: int, state: int) -> int:
    best_value = q_table[individual_id, state, 1]
    for action in range(2, 4):
        value = q_table[individual_id, state, action]
        if value > best_value:
            best_value = value
    tie_count = 0
    for action in range(1, 4):
        if q_table[individual_id, state, action] == best_value:
            tie_count += 1
    pick = np.random.randint(0, tie_count)
    seen = 0
    for action in range(1, 4):
        if q_table[individual_id, state, action] == best_value:
            if seen == pick:
                return action
            seen += 1
    return 1


@njit(cache=True)
def _update_q_value(
    q_table: np.ndarray,
    individual_id: int,
    state: int,
    action: int,
    reward: float,
    next_state: int,
    alpha: float,
    gamma: float,
) -> None:
    next_max = q_table[individual_id, next_state, 0]
    for a in range(1, 4):
        if q_table[individual_id, next_state, a] > next_max:
            next_max = q_table[individual_id, next_state, a]
    current = q_table[individual_id, state, action]
    q_table[individual_id, state, action] = current + alpha * (reward + gamma * next_max - current)


@njit(cache=True)
def _map_position_excluding(pos: int, excluded: int) -> int:
    if pos >= excluded:
        return pos + 1
    return pos


@njit(cache=True)
def _select_two_distinct_indices_excluding(pop_size: int, excluded: int) -> tuple[int, int]:
    first_pos = np.random.randint(0, pop_size - 1)
    second_pos = np.random.randint(0, pop_size - 2)
    if second_pos >= first_pos:
        second_pos += 1
    return (
        _map_position_excluding(first_pos, excluded),
        _map_position_excluding(second_pos, excluded),
    )


@njit(cache=True)
def _sma_global_row(
    pop_sol: np.ndarray,
    row: int,
    weights: np.ndarray,
    capacities: np.ndarray,
    cp_list: np.ndarray,
    acc_res: np.ndarray,
    items: int,
    dim: int,
) -> None:
    for j in range(items):
        pop_sol[row, j] = 0.0
    for d in range(dim):
        acc_res[d] = 0.0
    for pos in range(items):
        jj = int(cp_list[pos])
        if np.random.random() < 0.5:
            ok = True
            for d in range(dim):
                if acc_res[d] + weights[jj, d] > capacities[d]:
                    ok = False
                    break
            if ok:
                pop_sol[row, jj] = 1.0
                for d in range(dim):
                    acc_res[d] += weights[jj, d]


@njit(cache=True)
def _sma_local_row(
    pop_sol: np.ndarray,
    pop_fit: np.ndarray,
    row: int,
    gbest_fit: float,
    gbest_sol: np.ndarray,
    W: np.ndarray,
    weights: np.ndarray,
    capacities: np.ndarray,
    x_lp: np.ndarray,
    bucket: np.ndarray,
    resource: np.ndarray,
    local_a: float,
    local_b: float,
    pop_size: int,
    items: int,
    dim: int,
    ctf_id: int,
    guided_enabled: bool,
    guided_lambda_lp: float,
    guided_lambda_bucket: float,
    guided_lambda_slack: float,
) -> None:
    p = math.tanh(abs(pop_fit[row] - gbest_fit))
    local_a_span = 2.0 * local_a
    local_b_span = 2.0 * local_b
    _init_row_resource_from_bits(pop_sol, row, weights, resource, items, dim)
    for j in range(items):
        old_bit = 1.0 if pop_sol[row, j] >= 0.5 else 0.0
        _resource_excluding_item_inplace(resource, old_bit, weights, j, dim)
        r = np.random.random()
        vb_j = -local_a + local_a_span * np.random.random()
        vc_j = -local_b + local_b_span * np.random.random()
        a_idx, b_idx = _select_two_distinct_indices_excluding(pop_size, row)
        if r < p:
            pop_sol[row, j] = gbest_sol[j] + vb_j * (
                W[row, j] * pop_sol[a_idx, j] - pop_sol[b_idx, j]
            )
        else:
            pop_sol[row, j] = vc_j * pop_sol[row, j]
        slack_score = _guided_slack_score(resource, weights, capacities, j, dim)
        probability = _guided_probability(
            ctf_id,
            pop_sol[row, j],
            x_lp[j],
            int(bucket[j]),
            slack_score,
            guided_enabled,
            guided_lambda_lp,
            guided_lambda_bucket,
            guided_lambda_slack,
        )
        _set_guided_binary_bit_and_update_resource(pop_sol, row, j, probability, weights, resource, dim)


@njit(cache=True)
def _sca_sin_row(
    pop_sol: np.ndarray,
    individual_best_sol: np.ndarray,
    row: int,
    individual_id: int,
    gbest_sol: np.ndarray,
    weights: np.ndarray,
    capacities: np.ndarray,
    x_lp: np.ndarray,
    bucket: np.ndarray,
    resource: np.ndarray,
    r1: float,
    items: int,
    dim: int,
    two_pi: float,
    ctf_id: int,
    guided_enabled: bool,
    guided_lambda_lp: float,
    guided_lambda_bucket: float,
    guided_lambda_slack: float,
) -> None:
    _init_row_resource_from_bits(pop_sol, row, weights, resource, items, dim)
    for j in range(items):
        old_bit = 1.0 if pop_sol[row, j] >= 0.5 else 0.0
        _resource_excluding_item_inplace(resource, old_bit, weights, j, dim)
        r2 = two_pi * np.random.random()
        r3 = 2.0 * np.random.random()
        pop_sol[row, j] = individual_best_sol[individual_id, j] + (
            r1 * math.sin(r2) * abs(r3 * gbest_sol[j] - individual_best_sol[individual_id, j])
        )
        slack_score = _guided_slack_score(resource, weights, capacities, j, dim)
        probability = _guided_probability(
            ctf_id,
            pop_sol[row, j],
            x_lp[j],
            int(bucket[j]),
            slack_score,
            guided_enabled,
            guided_lambda_lp,
            guided_lambda_bucket,
            guided_lambda_slack,
        )
        _set_guided_binary_bit_and_update_resource(pop_sol, row, j, probability, weights, resource, dim)


@njit(cache=True)
def _sca_cos_row(
    pop_sol: np.ndarray,
    individual_best_sol: np.ndarray,
    row: int,
    individual_id: int,
    gbest_sol: np.ndarray,
    weights: np.ndarray,
    capacities: np.ndarray,
    x_lp: np.ndarray,
    bucket: np.ndarray,
    resource: np.ndarray,
    r1: float,
    items: int,
    dim: int,
    two_pi: float,
    ctf_id: int,
    guided_enabled: bool,
    guided_lambda_lp: float,
    guided_lambda_bucket: float,
    guided_lambda_slack: float,
) -> None:
    _init_row_resource_from_bits(pop_sol, row, weights, resource, items, dim)
    for j in range(items):
        old_bit = 1.0 if pop_sol[row, j] >= 0.5 else 0.0
        _resource_excluding_item_inplace(resource, old_bit, weights, j, dim)
        r2 = two_pi * np.random.random()
        r3 = 2.0 * np.random.random()
        pop_sol[row, j] = individual_best_sol[individual_id, j] + (
            r1 * math.cos(r2) * abs(r3 * gbest_sol[j] - individual_best_sol[individual_id, j])
        )
        slack_score = _guided_slack_score(resource, weights, capacities, j, dim)
        probability = _guided_probability(
            ctf_id,
            pop_sol[row, j],
            x_lp[j],
            int(bucket[j]),
            slack_score,
            guided_enabled,
            guided_lambda_lp,
            guided_lambda_bucket,
            guided_lambda_slack,
        )
        _set_guided_binary_bit_and_update_resource(pop_sol, row, j, probability, weights, resource, dim)


@njit(cache=True)
def _bscasma_rl_main_loop_numba(
    pop_sol: np.ndarray,
    pop_fit: np.ndarray,
    individual_best_sol: np.ndarray,
    individual_best_fit: np.ndarray,
    individual_ids: np.ndarray,
    q_table: np.ndarray,
    action_counts: np.ndarray,
    values: np.ndarray,
    weights: np.ndarray,
    capacities: np.ndarray,
    cp_list: np.ndarray,
    W: np.ndarray,
    pop_size: int,
    items: int,
    dim: int,
    a: float,
    z: float,
    alpha: float,
    gamma: float,
    glbal_best: int,
    max_iter: int,
    rng_seed: int,
    tmp_sol: np.ndarray,
    tmp_fit: np.ndarray,
    tmp_ids: np.ndarray,
    tmp_hamming: np.ndarray,
    idx_work: np.ndarray,
    ones_count: np.ndarray,
    avg_bits: np.ndarray,
    row_hamming: np.ndarray,
    old_row: np.ndarray,
    sqrt_lookup: np.ndarray,
    acc_res: np.ndarray,
    gbest_sol: np.ndarray,
    ctf_id: int,
    repair_passes: int,
    repair_swap_limit: int,
    repair_stats: np.ndarray,
    bucket: np.ndarray,
    x_lp: np.ndarray,
    guided_binary_enabled: bool,
    guided_lambda_lp: float,
    guided_lambda_bucket: float,
    guided_lambda_slack: float,
    local_search_enabled: bool,
    ls_budget_per_run: int,
    ls_max_passes: int,
    ls_cooldown: int,
    ls_add_cap: int,
    ls_drop_cap: int,
    ls_work_row: np.ndarray,
    ls_stats: np.ndarray,
    archive_pr_enabled: bool,
    archive_size: int,
    pr_interval: int,
    pr_max_steps: int,
    pr_core_only: bool,
    archive_sol: np.ndarray,
    archive_fit: np.ndarray,
    archive_count: np.ndarray,
    pr_sol: np.ndarray,
    pr_fit: np.ndarray,
    pr_stats: np.ndarray,
    restart_enabled: bool,
    restart_window: int,
    restart_rows: int,
    restart_strong_p: float,
    restart_core_p: float,
    restart_weak_p: float,
    restart_stats: np.ndarray,
) -> float:
    np.random.seed(rng_seed)
    gbest_fit = pop_fit[0]
    for j in range(items):
        gbest_sol[j] = pop_sol[0, j]
    density_sum = _init_density_state(
        pop_sol, ones_count, avg_bits, row_hamming, sqrt_lookup, pop_size, items
    )
    mf = float(max_iter)
    density_denominator = float(pop_size) * float(items)
    two_pi = 2.0 * math.pi
    stagnation_iters = 0
    last_ls_iter = -ls_cooldown
    if archive_pr_enabled:
        for row in range(pop_size):
            _archive_add_row(
                archive_sol,
                archive_fit,
                archive_count,
                pop_sol,
                pop_fit,
                row,
                archive_size,
                items,
                ls_work_row,
            )

    for iter_idx in range(max_iter):
        iteration_improved = False
        _update_sma_weight_inplace(W, pop_fit, pop_size, items)
        r1 = a - a * (float(iter_idx) / mf)
        local_a = np.arctanh(-1.0 * ((iter_idx + 1) / mf) + 1.0)
        local_b = 1.0 - (iter_idx + 1) / mf

        for row in range(pop_size):
            individual_id = int(individual_ids[row])
            density = density_sum / density_denominator
            state = _state_for_row(pop_sol, row, gbest_sol, pop_size, items, density)
            _copy_row_bits(pop_sol, row, old_row, items)
            if np.random.random() < z:
                action = 0
            else:
                action = _select_q_action_non_global(q_table, individual_id, state)
            action_counts[individual_id, action] += 1

            if action == 0:
                _sma_global_row(pop_sol, row, weights, capacities, cp_list, acc_res, items, dim)
            elif action == 1:
                _sma_local_row(
                    pop_sol,
                    pop_fit,
                    row,
                    gbest_fit,
                    gbest_sol,
                    W,
                    weights,
                    capacities,
                    x_lp,
                    bucket,
                    acc_res,
                    local_a,
                    local_b,
                    pop_size,
                    items,
                    dim,
                    ctf_id,
                    guided_binary_enabled,
                    guided_lambda_lp,
                    guided_lambda_bucket,
                    guided_lambda_slack,
                )
            elif action == 2:
                _sca_sin_row(
                    pop_sol,
                    individual_best_sol,
                    row,
                    individual_id,
                    gbest_sol,
                    weights,
                    capacities,
                    x_lp,
                    bucket,
                    acc_res,
                    r1,
                    items,
                    dim,
                    two_pi,
                    ctf_id,
                    guided_binary_enabled,
                    guided_lambda_lp,
                    guided_lambda_bucket,
                    guided_lambda_slack,
                )
            elif action == 3:
                _sca_cos_row(
                    pop_sol,
                    individual_best_sol,
                    row,
                    individual_id,
                    gbest_sol,
                    weights,
                    capacities,
                    x_lp,
                    bucket,
                    acc_res,
                    r1,
                    items,
                    dim,
                    two_pi,
                    ctf_id,
                    guided_binary_enabled,
                    guided_lambda_lp,
                    guided_lambda_bucket,
                    guided_lambda_slack,
                )

            _repair_bscasma_row_v2_inplace(
                pop_sol,
                row,
                pop_fit,
                values,
                weights,
                capacities,
                cp_list,
                acc_res,
                items,
                dim,
                repair_passes,
                repair_swap_limit,
                repair_stats,
            )

            if (
                local_search_enabled
                and pop_fit[row] > gbest_fit
                and iter_idx - last_ls_iter >= ls_cooldown
                and ls_stats[3] < ls_budget_per_run
            ):
                _local_search_bscasma_row_inplace(
                    pop_sol,
                    row,
                    pop_fit,
                    values,
                    weights,
                    capacities,
                    cp_list,
                    acc_res,
                    items,
                    dim,
                    repair_passes,
                    repair_swap_limit,
                    repair_stats,
                    ls_work_row,
                    ls_max_passes,
                    ls_add_cap,
                    ls_drop_cap,
                    ls_budget_per_run,
                    ls_stats,
                )
                last_ls_iter = iter_idx

            density_sum = _update_density_state_for_row(
                pop_sol,
                row,
                old_row,
                ones_count,
                avg_bits,
                row_hamming,
                density_sum,
                sqrt_lookup,
                pop_size,
                items,
            )

            reward = -1.0
            if pop_fit[row] > individual_best_fit[individual_id]:
                for j in range(items):
                    individual_best_sol[individual_id, j] = pop_sol[row, j]
                individual_best_fit[individual_id] = pop_fit[row]
                reward = 1.0

            if pop_fit[row] > gbest_fit:
                gbest_fit = pop_fit[row]
                for j in range(items):
                    gbest_sol[j] = pop_sol[row, j]
                if archive_pr_enabled:
                    _archive_add_row(
                        archive_sol,
                        archive_fit,
                        archive_count,
                        pop_sol,
                        pop_fit,
                        row,
                        archive_size,
                        items,
                        ls_work_row,
                    )
                iteration_improved = True

            next_density = density_sum / density_denominator
            next_state = _state_for_row(pop_sol, row, gbest_sol, pop_size, items, next_density)
            _update_q_value(q_table, individual_id, state, action, reward, next_state, alpha, gamma)

            if gbest_fit == float(glbal_best):
                return gbest_fit
        _sort_bscasma_rl_desc_deterministic_inplace(
            pop_sol,
            pop_fit,
            individual_ids,
            row_hamming,
            tmp_sol,
            tmp_fit,
            tmp_ids,
            tmp_hamming,
            idx_work,
            pop_size,
                items,
        )
        if iteration_improved:
            stagnation_iters = 0
        else:
            stagnation_iters += 1

        if archive_pr_enabled and (
            ((iter_idx + 1) % pr_interval == 0)
            or (stagnation_iters >= restart_window)
        ):
            before_pr_fit = gbest_fit
            gbest_fit = _path_relink_bscasma_inplace(
                archive_sol,
                archive_fit,
                archive_count,
                archive_size,
                gbest_sol,
                gbest_fit,
                values,
                weights,
                capacities,
                cp_list,
                bucket,
                pr_sol,
                pr_fit,
                acc_res,
                repair_passes,
                repair_swap_limit,
                repair_stats,
                pr_max_steps,
                pr_core_only,
                pr_stats,
                items,
                dim,
            )
            if gbest_fit > before_pr_fit:
                iteration_improved = True
                stagnation_iters = 0

        if restart_enabled and stagnation_iters >= restart_window:
            first_restart_row = pop_size - restart_rows
            if first_restart_row < 0:
                first_restart_row = 0
            for row in range(first_restart_row, pop_size):
                individual_id = int(individual_ids[row])
                _copy_row_bits(pop_sol, row, old_row, items)
                _restart_bscasma_bucket_biased_row_inplace(
                    pop_sol,
                    row,
                    pop_fit,
                    values,
                    weights,
                    capacities,
                    cp_list,
                    bucket,
                    acc_res,
                    items,
                    dim,
                    restart_strong_p,
                    restart_core_p,
                    restart_weak_p,
                )
                _repair_bscasma_row_v2_inplace(
                    pop_sol,
                    row,
                    pop_fit,
                    values,
                    weights,
                    capacities,
                    cp_list,
                    acc_res,
                    items,
                    dim,
                    repair_passes,
                    repair_swap_limit,
                    repair_stats,
                )
                density_sum = _update_density_state_for_row(
                    pop_sol,
                    row,
                    old_row,
                    ones_count,
                    avg_bits,
                    row_hamming,
                    density_sum,
                    sqrt_lookup,
                    pop_size,
                    items,
                )
                for j in range(items):
                    individual_best_sol[individual_id, j] = pop_sol[row, j]
                individual_best_fit[individual_id] = pop_fit[row]
                if pop_fit[row] > gbest_fit:
                    gbest_fit = pop_fit[row]
                    for j in range(items):
                        gbest_sol[j] = pop_sol[row, j]
                    if archive_pr_enabled:
                        _archive_add_row(
                            archive_sol,
                            archive_fit,
                            archive_count,
                            pop_sol,
                            pop_fit,
                            row,
                            archive_size,
                            items,
                            ls_work_row,
                        )
                    iteration_improved = True
            restart_stats[0] += 1
            restart_stats[1] += pop_size - first_restart_row
            stagnation_iters = 0
            if gbest_fit == float(glbal_best):
                return gbest_fit
            _sort_bscasma_rl_desc_deterministic_inplace(
                pop_sol,
                pop_fit,
                individual_ids,
                row_hamming,
                tmp_sol,
                tmp_fit,
                tmp_ids,
                tmp_hamming,
                idx_work,
                pop_size,
                items,
            )
    return gbest_fit


class BRLSMASCARLRCNumbaCore:
    _cp_list_cache: dict[Any, dict[str, Any]] = {}

    def __init__(
        self,
        items: int,
        dim: int,
        glbal_best: int,
        values: np.ndarray,
        weights: np.ndarray,
        capacities: np.ndarray,
        seed: int | None = None,
        *,
        pop_size: int,
        a: float,
        z: float,
        max_iter: int,
        alpha: float,
        gamma: float,
        ctf_id: int = 0,
        eval_group_decimals: int = 1,
        eval_group_shuffle: bool = False,
        eval_rc_eps: float = 1.0e-9,
        eval_x_eps: float = 1.0e-9,
        item_eval_method: str = "lp_rc_ordered",
        core_w_x_lp: float = 0.40,
        core_w_rc: float = 0.25,
        core_w_eff: float = 0.20,
        core_w_bucket: float = 0.15,
        freq_cp_noise: float = 0.03,
        freq_elite_ratio: float = 0.995,
        freq_quality_power: float = 4.0,
        freq_samples_dim5: int = 16,
        freq_samples_dim10: int = 32,
        freq_samples_dim30: int = 48,
        freq_blend_rho_dim5: float = 0.50,
        freq_blend_rho_dim10: float = 0.70,
        freq_blend_rho_dim30: float = 0.75,
        freq_gate_probe_margin: float = 0.0002,
        freq_gate_min_elites: int = 2,
        freq_gate_min_std: float = 0.08,
        freq_gate_min_topk_overlap: float = 0.65,
        repair_passes: int = 1,
        repair_swap_limit: int = 0,
        mixed_init_enabled: bool = False,
        restart_enabled: bool = False,
        restart_window: int = 40,
        restart_ratio: float = 0.25,
        restart_strong_p: float = 0.85,
        restart_core_p: float = 0.50,
        restart_weak_p: float = 0.15,
        guided_binary_enabled: bool = False,
        guided_lambda_lp: float = 0.30,
        guided_lambda_bucket: float = 0.08,
        guided_lambda_slack: float = 0.10,
        local_search_enabled: bool = False,
        ls_budget_per_run: int = 1500,
        ls_max_passes: int = 2,
        ls_cooldown: int = 10,
        ls_add_cap: int = 80,
        ls_drop_cap: int = 80,
        archive_pr_enabled: bool = False,
        archive_size: int = 8,
        pr_interval: int = 15,
        pr_max_steps: int = 15,
        pr_core_only: bool = True,
    ) -> None:
        if seed is not None:
            np.random.seed(int(seed))
        self.items = items
        self.dim = dim
        self.glbal_best = glbal_best
        self.values, self.weights, self.capacities = _expect_mkp_problem_tensors(values, weights, capacities)
        self.seed = seed
        self.linprog_runtime = 0.0
        self.cp_list_cache_hit = False
        self.item_eval_fallback = False
        self.eval_group_decimals = int(eval_group_decimals)
        self.eval_group_shuffle = bool(eval_group_shuffle)
        self.eval_rc_eps = float(eval_rc_eps)
        self.eval_x_eps = float(eval_x_eps)
        self.requested_item_eval_method = str(item_eval_method)
        self.core_w_x_lp = float(core_w_x_lp)
        self.core_w_rc = float(core_w_rc)
        self.core_w_eff = float(core_w_eff)
        self.core_w_bucket = float(core_w_bucket)
        self.freq_cp_noise = float(freq_cp_noise)
        self.freq_elite_ratio = float(freq_elite_ratio)
        self.freq_quality_power = float(freq_quality_power)
        self.freq_samples_dim5 = int(freq_samples_dim5)
        self.freq_samples_dim10 = int(freq_samples_dim10)
        self.freq_samples_dim30 = int(freq_samples_dim30)
        self.freq_blend_rho_dim5 = float(freq_blend_rho_dim5)
        self.freq_blend_rho_dim10 = float(freq_blend_rho_dim10)
        self.freq_blend_rho_dim30 = float(freq_blend_rho_dim30)
        self.freq_gate_probe_margin = float(freq_gate_probe_margin)
        self.freq_gate_min_elites = int(freq_gate_min_elites)
        self.freq_gate_min_std = float(freq_gate_min_std)
        self.freq_gate_min_topk_overlap = float(freq_gate_min_topk_overlap)
        self.item_eval_method = self.requested_item_eval_method
        self.repair_passes = int(repair_passes)
        self.repair_swap_limit = int(repair_swap_limit)
        self.repair_swap_accepts = 0
        self.mixed_init_enabled = bool(mixed_init_enabled)
        self.restart_enabled = bool(restart_enabled)
        self.restart_window = int(restart_window)
        self.restart_ratio = float(restart_ratio)
        self.restart_strong_p = float(restart_strong_p)
        self.restart_core_p = float(restart_core_p)
        self.restart_weak_p = float(restart_weak_p)
        self.restart_count = 0
        self.restart_rows = 0
        self.guided_binary_enabled = bool(guided_binary_enabled)
        self.guided_lambda_lp = float(guided_lambda_lp)
        self.guided_lambda_bucket = float(guided_lambda_bucket)
        self.guided_lambda_slack = float(guided_lambda_slack)
        self.local_search_enabled = bool(local_search_enabled)
        self.ls_budget_per_run = int(ls_budget_per_run)
        self.ls_max_passes = int(ls_max_passes)
        self.ls_cooldown = int(ls_cooldown)
        self.ls_add_cap = int(ls_add_cap)
        self.ls_drop_cap = int(ls_drop_cap)
        self.local_search_calls = 0
        self.local_search_moves = 0
        self.local_search_improvements = 0
        self.ls_obj_evals = 0
        self.archive_pr_enabled = bool(archive_pr_enabled)
        self.archive_size = int(archive_size)
        self.pr_interval = int(pr_interval)
        self.pr_max_steps = int(pr_max_steps)
        self.pr_core_only = bool(pr_core_only)
        self.pr_calls = 0
        self.pr_steps = 0
        self.pr_improvements = 0
        self.lp_fractional_count = 0
        self.eff_group_count = 0
        self.item_eval_payload: dict[str, Any] = {}
        self.guided_mode = "lp_original"
        self.freq_samples = 0
        self.freq_rho = 0.0
        self.freq_elite_count = 0
        self.freq_best_probe_fit = 0
        self.freq_core_greedy_fit = 0
        self.freq_topk_overlap = 0.0
        self.freq_score_std = 0.0
        self.freq_fallback = False
        self.freq_fallback_reason = ""

        if max_iter <= 0:
            raise ValueError("max_iter must be > 0")
        if pop_size < 3:
            raise ValueError("pop_size must be >= 3")
        if a <= 0:
            raise ValueError("a must be > 0")
        if not (0.0 < z <= 1.0):
            raise ValueError("z must satisfy 0 < z <= 1")
        if not (0.0 < alpha <= 1.0):
            raise ValueError("alpha must satisfy 0 < alpha <= 1")
        if not (0.0 <= gamma <= 1.0):
            raise ValueError("gamma must satisfy 0 <= gamma <= 1")
        if self.eval_group_decimals < 0:
            raise ValueError("eval_group_decimals must be >= 0")
        if self.eval_rc_eps < 0.0:
            raise ValueError("eval_rc_eps must be >= 0")
        if self.eval_x_eps < 0.0:
            raise ValueError("eval_x_eps must be >= 0")
        if self.requested_item_eval_method not in {
            "lp_rc_ordered",
            "lp_rc_groups",
            "core_score_cp",
            "freq_gated_v2",
            "freq_gated_v2_gbc",
        }:
            raise ValueError("item_eval_method is unsupported")
        if self.requested_item_eval_method == "lp_rc_groups":
            self.eval_group_shuffle = True
        for name, value in (
            ("core_w_x_lp", self.core_w_x_lp),
            ("core_w_rc", self.core_w_rc),
            ("core_w_eff", self.core_w_eff),
            ("core_w_bucket", self.core_w_bucket),
        ):
            if value < 0.0:
                raise ValueError(f"{name} must be >= 0")
        if self.core_w_x_lp + self.core_w_rc + self.core_w_eff + self.core_w_bucket <= 0.0:
            raise ValueError("core score weights must sum to > 0")
        if self.freq_cp_noise < 0.0:
            raise ValueError("freq_cp_noise must be >= 0")
        if not (0.0 < self.freq_elite_ratio <= 1.0):
            raise ValueError("freq_elite_ratio must satisfy 0 < freq_elite_ratio <= 1")
        if self.freq_quality_power <= 0.0:
            raise ValueError("freq_quality_power must be > 0")
        for name, value in (
            ("freq_samples_dim5", self.freq_samples_dim5),
            ("freq_samples_dim10", self.freq_samples_dim10),
            ("freq_samples_dim30", self.freq_samples_dim30),
        ):
            if value < 1:
                raise ValueError(f"{name} must be >= 1")
        for name, value in (
            ("freq_blend_rho_dim5", self.freq_blend_rho_dim5),
            ("freq_blend_rho_dim10", self.freq_blend_rho_dim10),
            ("freq_blend_rho_dim30", self.freq_blend_rho_dim30),
        ):
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"{name} must satisfy 0 <= {name} <= 1")
        if self.freq_gate_probe_margin < 0.0:
            raise ValueError("freq_gate_probe_margin must be >= 0")
        if self.freq_gate_min_elites < 1:
            raise ValueError("freq_gate_min_elites must be >= 1")
        if self.freq_gate_min_std < 0.0:
            raise ValueError("freq_gate_min_std must be >= 0")
        if not (0.0 <= self.freq_gate_min_topk_overlap <= 1.0):
            raise ValueError("freq_gate_min_topk_overlap must satisfy 0 <= value <= 1")
        if self.repair_passes < 1:
            raise ValueError("repair_passes must be >= 1")
        if self.repair_swap_limit < 0:
            raise ValueError("repair_swap_limit must be >= 0")
        if self.restart_window < 1:
            raise ValueError("restart_window must be >= 1")
        if not (0.0 < self.restart_ratio <= 1.0):
            raise ValueError("restart_ratio must satisfy 0 < restart_ratio <= 1")
        for name, value in (
            ("restart_strong_p", self.restart_strong_p),
            ("restart_core_p", self.restart_core_p),
            ("restart_weak_p", self.restart_weak_p),
        ):
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"{name} must satisfy 0 <= {name} <= 1")
        for name, value in (
            ("guided_lambda_lp", self.guided_lambda_lp),
            ("guided_lambda_bucket", self.guided_lambda_bucket),
            ("guided_lambda_slack", self.guided_lambda_slack),
        ):
            if value < 0.0:
                raise ValueError(f"{name} must be >= 0")
        if self.ls_budget_per_run < 0:
            raise ValueError("ls_budget_per_run must be >= 0")
        if self.ls_max_passes < 1:
            raise ValueError("ls_max_passes must be >= 1")
        if self.ls_cooldown < 0:
            raise ValueError("ls_cooldown must be >= 0")
        if self.ls_add_cap < 1:
            raise ValueError("ls_add_cap must be >= 1")
        if self.ls_drop_cap < 1:
            raise ValueError("ls_drop_cap must be >= 1")
        if self.archive_size < 2:
            raise ValueError("archive_size must be >= 2")
        if self.pr_interval < 1:
            raise ValueError("pr_interval must be >= 1")
        if self.pr_max_steps < 1:
            raise ValueError("pr_max_steps must be >= 1")

        self.ctf_id = int(ctf_id)
        self.alpha = float(alpha)
        self.gamma = float(gamma)
        self.pop_size = int(pop_size)
        self.max_iter = int(max_iter)
        self.cp_list = self.pseudo_utility()
        self.cp_list_old = self.cp_list
        self.std = int(self.items * 0.15)
        self.z = float(z)
        self.W = np.zeros([self.pop_size, self.items])
        self.b = None
        self.a = float(a)
        self.p = 0.5
        self.r1: float | None = None
        self.pop_fit = np.zeros([self.pop_size], dtype=int)
        self.pop_fit_new = np.zeros([self.pop_size], dtype=int)
        self.pop_sol: np.ndarray | None = None
        self.individual_best_sol = np.zeros([self.pop_size, self.items])
        self.individual_best_fit = np.zeros([self.pop_size], dtype=int)
        self.individual_ids = np.arange(self.pop_size, dtype=np.int64)
        self.Gbest_sol: np.ndarray | None = None
        self.Gbest_fit: int | None = None
        self.initial_pop()
        self.q_table = np.zeros([self.pop_size, 9, 4], dtype=np.float64)
        self.action_counts = np.zeros([self.pop_size, 4], dtype=np.int64)

    def pseudo_utility(self) -> np.ndarray:
        method = self.requested_item_eval_method
        actual_method_for_cache = method
        if method == "lp_rc_ordered" and self.eval_group_shuffle:
            actual_method_for_cache = "lp_rc_groups"
        freq_seed = int(self.seed) if method in {"freq_gated_v2", "freq_gated_v2_gbc"} and self.seed is not None else None
        extra_params = (
            self.core_w_x_lp,
            self.core_w_rc,
            self.core_w_eff,
            self.core_w_bucket,
            self.freq_cp_noise,
            self.freq_elite_ratio,
            self.freq_quality_power,
            self.freq_samples_dim5,
            self.freq_samples_dim10,
            self.freq_samples_dim30,
            self.freq_blend_rho_dim5,
            self.freq_blend_rho_dim10,
            self.freq_blend_rho_dim30,
            self.freq_gate_probe_margin,
            self.freq_gate_min_elites,
            self.freq_gate_min_std,
            self.freq_gate_min_topk_overlap,
            self.repair_passes,
            self.repair_swap_limit,
        )
        cache_key = _item_eval_cache_key(
            self.values,
            self.weights,
            self.capacities,
            eval_group_decimals=self.eval_group_decimals,
            eval_rc_eps=self.eval_rc_eps,
            eval_x_eps=self.eval_x_eps,
            item_eval_method=actual_method_for_cache,
            item_eval_seed=freq_seed,
            extra_params=extra_params,
        )
        cached = type(self)._cp_list_cache.get(cache_key)
        if cached is not None:
            self.cp_list_cache_hit = True
            self.linprog_runtime = 0.0
            payload = cached
        else:
            self.cp_list_cache_hit = False
            t_lp0 = time.perf_counter()
            payload = _build_lp_rc_item_eval_payload(
                self.values,
                self.weights,
                self.capacities,
                eval_group_decimals=self.eval_group_decimals,
                eval_rc_eps=self.eval_rc_eps,
                eval_x_eps=self.eval_x_eps,
            )
            if method == "core_score_cp":
                score_payload = _build_core_score_cp_payload(
                    payload,
                    core_w_x_lp=self.core_w_x_lp,
                    core_w_rc=self.core_w_rc,
                    core_w_eff=self.core_w_eff,
                    core_w_bucket=self.core_w_bucket,
                )
                payload = {**payload, **score_payload}
            elif method in {"freq_gated_v2", "freq_gated_v2_gbc"}:
                rng = np.random.default_rng(int(self.seed) if self.seed is not None else 0)
                score_payload = _build_freq_gated_v2_payload(
                    self.values,
                    self.weights,
                    self.capacities,
                    payload,
                    rng,
                    core_w_x_lp=self.core_w_x_lp,
                    core_w_rc=self.core_w_rc,
                    core_w_eff=self.core_w_eff,
                    core_w_bucket=self.core_w_bucket,
                    eval_group_decimals=self.eval_group_decimals,
                    eval_rc_eps=self.eval_rc_eps,
                    eval_x_eps=self.eval_x_eps,
                    freq_cp_noise=self.freq_cp_noise,
                    freq_elite_ratio=self.freq_elite_ratio,
                    freq_quality_power=self.freq_quality_power,
                    freq_samples_dim5=self.freq_samples_dim5,
                    freq_samples_dim10=self.freq_samples_dim10,
                    freq_samples_dim30=self.freq_samples_dim30,
                    freq_blend_rho_dim5=self.freq_blend_rho_dim5,
                    freq_blend_rho_dim10=self.freq_blend_rho_dim10,
                    freq_blend_rho_dim30=self.freq_blend_rho_dim30,
                    freq_gate_probe_margin=self.freq_gate_probe_margin,
                    freq_gate_min_elites=self.freq_gate_min_elites,
                    freq_gate_min_std=self.freq_gate_min_std,
                    freq_gate_min_topk_overlap=self.freq_gate_min_topk_overlap,
                    repair_passes=self.repair_passes,
                    repair_swap_limit=self.repair_swap_limit,
                )
                payload = {**payload, **score_payload}
            self.linprog_runtime = time.perf_counter() - t_lp0
            type(self)._cp_list_cache[cache_key] = payload

        if "cp_list" in payload:
            cp_list = np.ascontiguousarray(np.asarray(payload["cp_list"], dtype=np.int64).copy())
            group_count = int(payload.get("eff_group_count", 0))
        elif self.eval_group_shuffle:
            cp_list, group_count = _shuffle_efficiency_groups(
                np.asarray(payload["base_order"], dtype=np.int64),
                np.asarray(payload["bucket"], dtype=np.int64),
                np.asarray(payload["rounded_efficiency"], dtype=np.float64),
            )
        else:
            base_order = np.asarray(payload["base_order"], dtype=np.int64)
            cp_list = np.ascontiguousarray(base_order.copy())
            group_count = int(payload["eff_group_count"])
        self.item_eval_payload = payload
        self.item_eval_fallback = bool(payload["fallback"])
        self.lp_fractional_count = int(payload["lp_fractional_count"])
        self.eff_group_count = int(group_count)
        self.item_eval_method = str(payload.get("item_eval_method", "lp_rc_groups" if self.eval_group_shuffle else "lp_rc_ordered"))
        self.guided_mode = str(payload.get("guided_mode", "lp_original"))
        self.freq_samples = int(payload.get("freq_samples", 0))
        self.freq_rho = float(payload.get("freq_rho", 0.0))
        self.freq_elite_count = int(payload.get("freq_elite_count", 0))
        self.freq_best_probe_fit = int(payload.get("freq_best_probe_fit", 0))
        self.freq_core_greedy_fit = int(payload.get("freq_core_greedy_fit", 0))
        self.freq_topk_overlap = float(payload.get("freq_topk_overlap", 0.0))
        self.freq_score_std = float(payload.get("freq_score_std", 0.0))
        self.freq_fallback = bool(payload.get("freq_fallback", False))
        self.freq_fallback_reason = str(payload.get("freq_fallback_reason", ""))
        return cp_list

    def _finish_initial_row(self, row: int) -> None:
        self.pop_fit[row] = np.sum(np.multiply(self.values, self.pop_sol[row]))
        self.individual_best_sol[row] = self.pop_sol[row]
        self.individual_best_fit[row] = self.pop_fit[row]

    def _fill_initial_random_greedy_row(self, row: int) -> None:
        accumulated_resources = np.zeros([self.dim])
        for j in self.cp_list:
            if np.random.random() < 0.5:
                candidate_resources = accumulated_resources + self.weights[j]
                if np.all(candidate_resources <= self.capacities):
                    accumulated_resources = candidate_resources
                    self.pop_sol[row, j] = 1

    def _fill_initial_deterministic_greedy_row(self, row: int) -> None:
        accumulated_resources = np.zeros([self.dim])
        for j in self.cp_list:
            candidate_resources = accumulated_resources + self.weights[j]
            if np.all(candidate_resources <= self.capacities):
                accumulated_resources = candidate_resources
                self.pop_sol[row, j] = 1

    def _fill_initial_lp_rounding_row(self, row: int, threshold: float) -> None:
        x_lp = np.asarray(self.item_eval_payload.get("x_lp", np.zeros(self.items)), dtype=np.float64)
        accumulated_resources = np.zeros([self.dim])
        for j in self.cp_list:
            if x_lp[j] >= threshold:
                candidate_resources = accumulated_resources + self.weights[j]
                if np.all(candidate_resources <= self.capacities):
                    accumulated_resources = candidate_resources
                    self.pop_sol[row, j] = 1

    def _fill_initial_rcl_greedy_row(self, row: int) -> None:
        order = np.ascontiguousarray(self.cp_list.copy())
        rcl_size = max(2, int(math.sqrt(self.items)))
        accumulated_resources = np.zeros([self.dim])
        for start in range(0, self.items, rcl_size):
            end = min(self.items, start + rcl_size)
            block = np.ascontiguousarray(order[start:end].copy())
            np.random.shuffle(block)
            for j in block:
                candidate_resources = accumulated_resources + self.weights[j]
                if np.all(candidate_resources <= self.capacities):
                    accumulated_resources = candidate_resources
                    self.pop_sol[row, j] = 1

    def initial_pop(self) -> None:
        self.pop_sol = np.zeros([self.pop_size, self.items])
        if not self.mixed_init_enabled:
            for i in range(self.pop_size):
                self._fill_initial_random_greedy_row(i)
                self._finish_initial_row(i)
            return

        deterministic_count = min(self.pop_size, max(1, int(math.ceil(self.pop_size * 0.10))))
        lp_count = min(self.pop_size - deterministic_count, int(math.ceil(self.pop_size * 0.20)))
        rcl_count = min(self.pop_size - deterministic_count - lp_count, int(math.ceil(self.pop_size * 0.40)))
        thresholds = (0.35, 0.50, 0.65, 0.80)
        row = 0
        for _ in range(deterministic_count):
            self._fill_initial_deterministic_greedy_row(row)
            self._finish_initial_row(row)
            row += 1
        for k in range(lp_count):
            self._fill_initial_lp_rounding_row(row, thresholds[k % len(thresholds)])
            self._finish_initial_row(row)
            row += 1
        for _ in range(rcl_count):
            self._fill_initial_rcl_greedy_row(row)
            self._finish_initial_row(row)
            row += 1
        while row < self.pop_size:
            self._fill_initial_random_greedy_row(row)
            self._finish_initial_row(row)
            row += 1

    def sort_pop_with_ids(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        pop_sol = np.zeros([self.pop_size, self.items])
        pop_fit = np.zeros([self.pop_size], dtype=int)
        sorted_indices = _argsort_pop_fit_desc_deterministic(self.pop_fit, self.pop_size)
        individual_ids = np.zeros([self.pop_size], dtype=np.int64)
        for i in range(self.pop_size):
            source = sorted_indices[i]
            pop_sol[i] = self.pop_sol[source]
            pop_fit[i] = self.pop_fit[source]
            individual_ids[i] = self.individual_ids[source]
        return pop_sol, pop_fit, individual_ids

    def run(self) -> tuple[np.ndarray, int]:
        np.random.seed(self.seed)
        (
            self.pop_sol,
            self.pop_fit,
            self.individual_ids,
        ) = self.sort_pop_with_ids()
        pop_sol = np.ascontiguousarray(self.pop_sol, dtype=np.float64)
        pop_fit = np.ascontiguousarray(self.pop_fit, dtype=np.float64)
        individual_best_sol = np.ascontiguousarray(self.individual_best_sol, dtype=np.float64)
        individual_best_fit = np.ascontiguousarray(self.individual_best_fit, dtype=np.float64)
        individual_ids = np.ascontiguousarray(self.individual_ids.astype(np.int64))
        q_table = np.ascontiguousarray(self.q_table.astype(np.float64))
        action_counts = np.ascontiguousarray(self.action_counts.astype(np.int64))
        ps, it, dm = self.pop_size, self.items, self.dim
        W = np.empty((ps, it), dtype=np.float64)
        tmp_sol = np.empty((ps, it), dtype=np.float64)
        tmp_fit = np.empty(ps, dtype=np.float64)
        tmp_ids = np.empty(ps, dtype=np.int64)
        tmp_hamming = np.empty(ps, dtype=np.float64)
        idx_work = np.empty(ps, dtype=np.int64)
        ones_count = np.empty(it, dtype=np.int64)
        avg_bits = np.empty(it, dtype=np.float64)
        row_hamming = np.empty(ps, dtype=np.float64)
        old_row = np.empty(it, dtype=np.float64)
        sqrt_lookup = np.sqrt(np.arange(it + 1, dtype=np.float64))
        acc_res = np.zeros(dm, dtype=np.float64)
        gbest_sol = np.empty(it, dtype=np.float64)
        repair_stats = np.zeros(1, dtype=np.int64)
        restart_stats = np.zeros(2, dtype=np.int64)
        bucket = np.ascontiguousarray(np.asarray(self.item_eval_payload["bucket"], dtype=np.int64))
        guidance_values = self.item_eval_payload.get("guided_x", self.item_eval_payload["x_lp"])
        x_lp = np.ascontiguousarray(np.asarray(guidance_values, dtype=np.float64))
        ls_work_row = np.empty(it, dtype=np.float64)
        ls_stats = np.zeros(4, dtype=np.int64)
        pr_stats = np.zeros(3, dtype=np.int64)
        archive_size = max(2, int(self.archive_size))
        archive_sol = np.zeros((archive_size, it), dtype=np.float64)
        archive_fit = np.zeros(archive_size, dtype=np.float64)
        archive_count = np.zeros(1, dtype=np.int64)
        pr_sol = np.zeros((1, it), dtype=np.float64)
        pr_fit = np.zeros(1, dtype=np.float64)
        restart_rows = int(math.ceil(self.pop_size * self.restart_ratio)) if self.restart_enabled else 0
        if self.restart_enabled and restart_rows < 1:
            restart_rows = 1
        if restart_rows > self.pop_size:
            restart_rows = self.pop_size
        rng_seed = int(self.seed) if self.seed is not None else 0

        gfit = _bscasma_rl_main_loop_numba(
            pop_sol,
            pop_fit,
            individual_best_sol,
            individual_best_fit,
            individual_ids,
            q_table,
            action_counts,
            self.values,
            self.weights,
            self.capacities,
            self.cp_list,
            W,
            ps,
            it,
            dm,
            self.a,
            self.z,
            self.alpha,
            self.gamma,
            int(self.glbal_best),
            self.max_iter,
            rng_seed,
            tmp_sol,
            tmp_fit,
            tmp_ids,
            tmp_hamming,
            idx_work,
            ones_count,
            avg_bits,
            row_hamming,
            old_row,
            sqrt_lookup,
            acc_res,
            gbest_sol,
            self.ctf_id,
            int(self.repair_passes),
            int(self.repair_swap_limit),
            repair_stats,
            bucket,
            x_lp,
            bool(self.guided_binary_enabled),
            float(self.guided_lambda_lp),
            float(self.guided_lambda_bucket),
            float(self.guided_lambda_slack),
            bool(self.local_search_enabled),
            int(self.ls_budget_per_run),
            int(self.ls_max_passes),
            int(self.ls_cooldown),
            int(self.ls_add_cap),
            int(self.ls_drop_cap),
            ls_work_row,
            ls_stats,
            bool(self.archive_pr_enabled),
            int(archive_size),
            int(self.pr_interval),
            int(self.pr_max_steps),
            bool(self.pr_core_only),
            archive_sol,
            archive_fit,
            archive_count,
            pr_sol,
            pr_fit,
            pr_stats,
            bool(self.restart_enabled),
            int(self.restart_window),
            int(restart_rows),
            float(self.restart_strong_p),
            float(self.restart_core_p),
            float(self.restart_weak_p),
            restart_stats,
        )

        self.individual_ids = np.asarray(individual_ids)
        self.q_table = np.asarray(q_table)
        self.action_counts = np.asarray(action_counts)
        self.repair_swap_accepts = int(repair_stats[0])
        self.restart_count = int(restart_stats[0])
        self.restart_rows = int(restart_stats[1])
        self.local_search_calls = int(ls_stats[0])
        self.local_search_moves = int(ls_stats[1])
        self.local_search_improvements = int(ls_stats[2])
        self.ls_obj_evals = int(ls_stats[3])
        self.pr_calls = int(pr_stats[0])
        self.pr_steps = int(pr_stats[1])
        self.pr_improvements = int(pr_stats[2])
        out = np.empty(it, dtype=np.int64)
        for j in range(it):
            out[j] = 1 if gbest_sol[j] >= 0.5 else 0
        return out, int(gfit)


@dataclass
class BRLSMASCARLRCNumbaSolver:
    def solve(self, problem: ProblemModel, config: dict[str, Any], rng: np.random.Generator) -> SolveResult:
        stop_condition = config.get("stop_condition", {})
        if stop_condition.get("type") != "max_iterations":
            raise ValueError("brlsmasca_rl_rc_numba only supports stop_condition.type=max_iterations")
        max_iterations = int(stop_condition.get("max_iterations", 0))
        if max_iterations <= 0:
            raise ValueError("max_iterations must be > 0")

        raw_params = config.get("params", {})
        if not isinstance(raw_params, dict):
            raise ValueError("params must be a mapping when present")
        pop_size = int(raw_params.get("pop_size", 20))
        a = float(raw_params.get("a", 2))
        z = float(raw_params.get("z", 0.03))
        alpha = float(raw_params.get("alpha", 0.1))
        gamma = float(raw_params.get("gamma", 0.9))
        eval_group_decimals = int(raw_params.get("eval_group_decimals", 1))
        eval_group_shuffle = _coerce_bool_param(
            raw_params.get("eval_group_shuffle", False),
            name="eval_group_shuffle",
        )
        eval_rc_eps = float(raw_params.get("eval_rc_eps", 1.0e-9))
        eval_x_eps = float(raw_params.get("eval_x_eps", 1.0e-9))
        item_eval_method = str(raw_params.get("item_eval_method", "lp_rc_ordered"))
        core_w_x_lp = float(raw_params.get("core_w_x_lp", 0.40))
        core_w_rc = float(raw_params.get("core_w_rc", 0.25))
        core_w_eff = float(raw_params.get("core_w_eff", 0.20))
        core_w_bucket = float(raw_params.get("core_w_bucket", 0.15))
        freq_cp_noise = float(raw_params.get("freq_cp_noise", 0.03))
        freq_elite_ratio = float(raw_params.get("freq_elite_ratio", 0.995))
        freq_quality_power = float(raw_params.get("freq_quality_power", 4.0))
        freq_samples_dim5 = int(raw_params.get("freq_samples_dim5", 16))
        freq_samples_dim10 = int(raw_params.get("freq_samples_dim10", 32))
        freq_samples_dim30 = int(raw_params.get("freq_samples_dim30", 48))
        freq_blend_rho_dim5 = float(raw_params.get("freq_blend_rho_dim5", 0.50))
        freq_blend_rho_dim10 = float(raw_params.get("freq_blend_rho_dim10", 0.70))
        freq_blend_rho_dim30 = float(raw_params.get("freq_blend_rho_dim30", 0.75))
        freq_gate_probe_margin = float(raw_params.get("freq_gate_probe_margin", 0.0002))
        freq_gate_min_elites = int(raw_params.get("freq_gate_min_elites", 2))
        freq_gate_min_std = float(raw_params.get("freq_gate_min_std", 0.08))
        freq_gate_min_topk_overlap = float(raw_params.get("freq_gate_min_topk_overlap", 0.65))
        repair_passes = int(raw_params.get("repair_passes", 1))
        repair_swap_limit = int(raw_params.get("repair_swap_limit", 0))
        mixed_init_enabled = _coerce_bool_param(
            raw_params.get("mixed_init_enabled", False),
            name="mixed_init_enabled",
        )
        restart_enabled = _coerce_bool_param(
            raw_params.get("restart_enabled", False),
            name="restart_enabled",
        )
        restart_window = int(raw_params.get("restart_window", 40))
        restart_ratio = float(raw_params.get("restart_ratio", 0.25))
        restart_strong_p = float(raw_params.get("restart_strong_p", 0.85))
        restart_core_p = float(raw_params.get("restart_core_p", 0.50))
        restart_weak_p = float(raw_params.get("restart_weak_p", 0.15))
        guided_binary_enabled = _coerce_bool_param(
            raw_params.get("guided_binary_enabled", False),
            name="guided_binary_enabled",
        )
        if item_eval_method == "freq_gated_v2_gbc":
            guided_binary_enabled = True
        guided_lambda_lp_default = 0.10 if item_eval_method == "freq_gated_v2_gbc" else 0.30
        guided_lambda_bucket_default = 0.05 if item_eval_method == "freq_gated_v2_gbc" else 0.08
        guided_lambda_slack_default = 0.05 if item_eval_method == "freq_gated_v2_gbc" else 0.10
        guided_lambda_lp = float(raw_params.get("guided_lambda_lp", guided_lambda_lp_default))
        guided_lambda_bucket = float(raw_params.get("guided_lambda_bucket", guided_lambda_bucket_default))
        guided_lambda_slack = float(raw_params.get("guided_lambda_slack", guided_lambda_slack_default))
        local_search_enabled = _coerce_bool_param(
            raw_params.get("local_search_enabled", False),
            name="local_search_enabled",
        )
        ls_budget_per_run = int(raw_params.get("ls_budget_per_run", 1500))
        ls_max_passes = int(raw_params.get("ls_max_passes", 2))
        ls_cooldown = int(raw_params.get("ls_cooldown", 10))
        ls_add_cap = int(raw_params.get("ls_add_cap", 80))
        ls_drop_cap = int(raw_params.get("ls_drop_cap", 80))
        archive_pr_enabled = _coerce_bool_param(
            raw_params.get("archive_pr_enabled", False),
            name="archive_pr_enabled",
        )
        archive_size = int(raw_params.get("archive_size", 8))
        pr_interval = int(raw_params.get("pr_interval", 15))
        pr_max_steps = int(raw_params.get("pr_max_steps", 15))
        pr_core_only = _coerce_bool_param(
            raw_params.get("pr_core_only", True),
            name="pr_core_only",
        )
        if pop_size < 3:
            raise ValueError("params.pop_size must be >= 3")
        if a <= 0:
            raise ValueError("params.a must be > 0")
        if not (0.0 < z <= 1.0):
            raise ValueError("params.z must satisfy 0 < z <= 1")
        if not (0.0 < alpha <= 1.0):
            raise ValueError("params.alpha must satisfy 0 < alpha <= 1")
        if not (0.0 <= gamma <= 1.0):
            raise ValueError("params.gamma must satisfy 0 <= gamma <= 1")
        if eval_group_decimals < 0:
            raise ValueError("params.eval_group_decimals must be >= 0")
        if eval_rc_eps < 0.0:
            raise ValueError("params.eval_rc_eps must be >= 0")
        if eval_x_eps < 0.0:
            raise ValueError("params.eval_x_eps must be >= 0")
        if item_eval_method not in {
            "lp_rc_ordered",
            "lp_rc_groups",
            "core_score_cp",
            "freq_gated_v2",
            "freq_gated_v2_gbc",
        }:
            raise ValueError("params.item_eval_method is unsupported")
        for name, value in (
            ("core_w_x_lp", core_w_x_lp),
            ("core_w_rc", core_w_rc),
            ("core_w_eff", core_w_eff),
            ("core_w_bucket", core_w_bucket),
        ):
            if value < 0.0:
                raise ValueError(f"params.{name} must be >= 0")
        if core_w_x_lp + core_w_rc + core_w_eff + core_w_bucket <= 0.0:
            raise ValueError("params.core score weights must sum to > 0")
        if freq_cp_noise < 0.0:
            raise ValueError("params.freq_cp_noise must be >= 0")
        if not (0.0 < freq_elite_ratio <= 1.0):
            raise ValueError("params.freq_elite_ratio must satisfy 0 < freq_elite_ratio <= 1")
        if freq_quality_power <= 0.0:
            raise ValueError("params.freq_quality_power must be > 0")
        for name, value in (
            ("freq_samples_dim5", freq_samples_dim5),
            ("freq_samples_dim10", freq_samples_dim10),
            ("freq_samples_dim30", freq_samples_dim30),
        ):
            if value < 1:
                raise ValueError(f"params.{name} must be >= 1")
        for name, value in (
            ("freq_blend_rho_dim5", freq_blend_rho_dim5),
            ("freq_blend_rho_dim10", freq_blend_rho_dim10),
            ("freq_blend_rho_dim30", freq_blend_rho_dim30),
        ):
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"params.{name} must satisfy 0 <= {name} <= 1")
        if freq_gate_probe_margin < 0.0:
            raise ValueError("params.freq_gate_probe_margin must be >= 0")
        if freq_gate_min_elites < 1:
            raise ValueError("params.freq_gate_min_elites must be >= 1")
        if freq_gate_min_std < 0.0:
            raise ValueError("params.freq_gate_min_std must be >= 0")
        if not (0.0 <= freq_gate_min_topk_overlap <= 1.0):
            raise ValueError("params.freq_gate_min_topk_overlap must satisfy 0 <= value <= 1")
        if repair_passes < 1:
            raise ValueError("params.repair_passes must be >= 1")
        if repair_swap_limit < 0:
            raise ValueError("params.repair_swap_limit must be >= 0")
        if restart_window < 1:
            raise ValueError("params.restart_window must be >= 1")
        if not (0.0 < restart_ratio <= 1.0):
            raise ValueError("params.restart_ratio must satisfy 0 < restart_ratio <= 1")
        for name, value in (
            ("restart_strong_p", restart_strong_p),
            ("restart_core_p", restart_core_p),
            ("restart_weak_p", restart_weak_p),
        ):
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"params.{name} must satisfy 0 <= {name} <= 1")
        for name, value in (
            ("guided_lambda_lp", guided_lambda_lp),
            ("guided_lambda_bucket", guided_lambda_bucket),
            ("guided_lambda_slack", guided_lambda_slack),
        ):
            if value < 0.0:
                raise ValueError(f"params.{name} must be >= 0")
        if ls_budget_per_run < 0:
            raise ValueError("params.ls_budget_per_run must be >= 0")
        if ls_max_passes < 1:
            raise ValueError("params.ls_max_passes must be >= 1")
        if ls_cooldown < 0:
            raise ValueError("params.ls_cooldown must be >= 0")
        if ls_add_cap < 1:
            raise ValueError("params.ls_add_cap must be >= 1")
        if ls_drop_cap < 1:
            raise ValueError("params.ls_drop_cap must be >= 1")
        if archive_size < 2:
            raise ValueError("params.archive_size must be >= 2")
        if pr_interval < 1:
            raise ValueError("params.pr_interval must be >= 1")
        if pr_max_steps < 1:
            raise ValueError("params.pr_max_steps must be >= 1")

        _, ctf_id = parse_ctf_kind(raw_params)
        run_seed = int(config.get("run_seed", rng.integers(0, np.iinfo(np.int32).max)))
        np.random.seed(run_seed)
        t_alg0 = time.perf_counter()
        core = BRLSMASCARLRCNumbaCore(
            problem.items,
            problem.dim,
            problem.best_known,
            problem.values,
            problem.weights,
            problem.capacities,
            seed=run_seed,
            pop_size=pop_size,
            a=a,
            z=z,
            max_iter=int(max_iterations),
            alpha=alpha,
            gamma=gamma,
            ctf_id=ctf_id,
            eval_group_decimals=eval_group_decimals,
            eval_group_shuffle=eval_group_shuffle,
            eval_rc_eps=eval_rc_eps,
            eval_x_eps=eval_x_eps,
            item_eval_method=item_eval_method,
            core_w_x_lp=core_w_x_lp,
            core_w_rc=core_w_rc,
            core_w_eff=core_w_eff,
            core_w_bucket=core_w_bucket,
            freq_cp_noise=freq_cp_noise,
            freq_elite_ratio=freq_elite_ratio,
            freq_quality_power=freq_quality_power,
            freq_samples_dim5=freq_samples_dim5,
            freq_samples_dim10=freq_samples_dim10,
            freq_samples_dim30=freq_samples_dim30,
            freq_blend_rho_dim5=freq_blend_rho_dim5,
            freq_blend_rho_dim10=freq_blend_rho_dim10,
            freq_blend_rho_dim30=freq_blend_rho_dim30,
            freq_gate_probe_margin=freq_gate_probe_margin,
            freq_gate_min_elites=freq_gate_min_elites,
            freq_gate_min_std=freq_gate_min_std,
            freq_gate_min_topk_overlap=freq_gate_min_topk_overlap,
            repair_passes=repair_passes,
            repair_swap_limit=repair_swap_limit,
            mixed_init_enabled=mixed_init_enabled,
            restart_enabled=restart_enabled,
            restart_window=restart_window,
            restart_ratio=restart_ratio,
            restart_strong_p=restart_strong_p,
            restart_core_p=restart_core_p,
            restart_weak_p=restart_weak_p,
            guided_binary_enabled=guided_binary_enabled,
            guided_lambda_lp=guided_lambda_lp,
            guided_lambda_bucket=guided_lambda_bucket,
            guided_lambda_slack=guided_lambda_slack,
            local_search_enabled=local_search_enabled,
            ls_budget_per_run=ls_budget_per_run,
            ls_max_passes=ls_max_passes,
            ls_cooldown=ls_cooldown,
            ls_add_cap=ls_add_cap,
            ls_drop_cap=ls_drop_cap,
            archive_pr_enabled=archive_pr_enabled,
            archive_size=archive_size,
            pr_interval=pr_interval,
            pr_max_steps=pr_max_steps,
            pr_core_only=pr_core_only,
        )
        best_sol, best_fit = core.run()
        algorithm_runtime = time.perf_counter() - t_alg0
        evaluation_count = int(core.pop_size + max_iterations * core.pop_size)
        total_obj_eval_count = evaluation_count + int(core.ls_obj_evals) + int(core.pr_steps)
        stop_reason = "best_known_reached" if int(best_fit) == int(problem.best_known) else "max_iterations_reached"
        action_counts = np.asarray(core.action_counts, dtype=np.int64)

        return SolveResult(
            problem_id=problem.problem_id,
            solver_id=str(config.get("solver_id", "brlsmasca_rl_rc_numba")),
            run_seed=run_seed,
            best_solution=np.asarray(best_sol, dtype=np.int64),
            best_objective=int(best_fit),
            feasible=True,
            evaluation_count=evaluation_count,
            stop_reason=stop_reason,
            runtime=algorithm_runtime,
            linprog_runtime=float(core.linprog_runtime),
            error=None,
            metadata={
                "linprog_runtime": float(core.linprog_runtime),
                "cp_list_cache_hit": bool(core.cp_list_cache_hit),
                "item_eval_method": str(core.item_eval_method),
                "item_eval_fallback": bool(core.item_eval_fallback),
                "eval_group_decimals": int(core.eval_group_decimals),
                "eval_group_shuffle": bool(core.eval_group_shuffle),
                "eval_rc_eps": float(core.eval_rc_eps),
                "eval_x_eps": float(core.eval_x_eps),
                "requested_item_eval_method": str(core.requested_item_eval_method),
                "core_w_x_lp": float(core.core_w_x_lp),
                "core_w_rc": float(core.core_w_rc),
                "core_w_eff": float(core.core_w_eff),
                "core_w_bucket": float(core.core_w_bucket),
                "freq_cp_noise": float(core.freq_cp_noise),
                "freq_elite_ratio": float(core.freq_elite_ratio),
                "freq_quality_power": float(core.freq_quality_power),
                "freq_samples": int(core.freq_samples),
                "freq_rho": float(core.freq_rho),
                "freq_elite_count": int(core.freq_elite_count),
                "freq_best_probe_fit": int(core.freq_best_probe_fit),
                "freq_core_greedy_fit": int(core.freq_core_greedy_fit),
                "freq_topk_overlap": float(core.freq_topk_overlap),
                "freq_score_std": float(core.freq_score_std),
                "freq_fallback": bool(core.freq_fallback),
                "freq_fallback_reason": str(core.freq_fallback_reason),
                "guided_mode": str(core.guided_mode),
                "repair_passes": int(core.repair_passes),
                "repair_swap_limit": int(core.repair_swap_limit),
                "repair_swap_accepts": int(core.repair_swap_accepts),
                "mixed_init_enabled": bool(core.mixed_init_enabled),
                "restart_enabled": bool(core.restart_enabled),
                "restart_window": int(core.restart_window),
                "restart_ratio": float(core.restart_ratio),
                "restart_count": int(core.restart_count),
                "restart_rows": int(core.restart_rows),
                "guided_binary_enabled": bool(core.guided_binary_enabled),
                "guided_lambda_lp": float(core.guided_lambda_lp),
                "guided_lambda_bucket": float(core.guided_lambda_bucket),
                "guided_lambda_slack": float(core.guided_lambda_slack),
                "local_search_enabled": bool(core.local_search_enabled),
                "ls_budget_per_run": int(core.ls_budget_per_run),
                "ls_max_passes": int(core.ls_max_passes),
                "ls_cooldown": int(core.ls_cooldown),
                "ls_add_cap": int(core.ls_add_cap),
                "ls_drop_cap": int(core.ls_drop_cap),
                "local_search_calls": int(core.local_search_calls),
                "local_search_moves": int(core.local_search_moves),
                "local_search_improvements": int(core.local_search_improvements),
                "ls_obj_evals": int(core.ls_obj_evals),
                "archive_pr_enabled": bool(core.archive_pr_enabled),
                "archive_size": int(core.archive_size),
                "pr_interval": int(core.pr_interval),
                "pr_max_steps": int(core.pr_max_steps),
                "pr_core_only": bool(core.pr_core_only),
                "pr_calls": int(core.pr_calls),
                "pr_steps": int(core.pr_steps),
                "pr_improvements": int(core.pr_improvements),
                "total_obj_eval_count": int(total_obj_eval_count),
                "lp_fractional_count": int(core.lp_fractional_count),
                "eff_group_count": int(core.eff_group_count),
                "numba": True,
                "rl": True,
                "z": float(z),
                "alpha": float(alpha),
                "gamma": float(gamma),
                "q_table_nonzero": int(np.count_nonzero(core.q_table)),
                "action_counts": action_counts.sum(axis=0).astype(int).tolist(),
            },
        )
