"""BSMA Numba variant with LP reduced-cost item evaluation and Repair 2.0."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
from numba import njit

from ..engine.models import SolveResult
from ..problem import ProblemModel
from ..tools.continuous_to_binary import parse_ctf_kind
from .BSCASMA_rl_rc_numba import (
    _build_lp_rc_item_eval_payload,
    _coerce_bool_param,
    _item_eval_cache_key,
    _repair_bscasma_row_v2_inplace,
    _restart_bscasma_bucket_biased_row_inplace,
    _shuffle_efficiency_groups,
)
from .BSMA import _argsort_pop_fit_desc_deterministic
from .BSMA_numba import (
    _ctf_flip_probability_fast,
    _expect_mkp_problem_tensors,
    _select_two_distinct_indices_excluding,
    _sort_pop_desc_deterministic_inplace,
)


@njit(cache=True)
def _bsma_rc_global_row(
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
def _bsma_rc_main_loop_numba(
    pop_sol: np.ndarray,
    pop_fit: np.ndarray,
    values: np.ndarray,
    weights: np.ndarray,
    capacities: np.ndarray,
    cp_list: np.ndarray,
    W: np.ndarray,
    pop_size: int,
    items: int,
    dim: int,
    z: float,
    glbal_best: float,
    max_iter: int,
    rng_seed: int,
    acc_res: np.ndarray,
    tmp_sol: np.ndarray,
    tmp_fit: np.ndarray,
    idx_work: np.ndarray,
    gbest_sol: np.ndarray,
    ctf_id: int,
    repair_passes: int,
    repair_swap_limit: int,
    repair_stats: np.ndarray,
    repair_drop_mode: int,
    drop_score: np.ndarray,
    bucket: np.ndarray,
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
    stagnation_iters = 0

    for iter_idx in range(max_iter):
        worst_fit = pop_fit[pop_size - 1]
        best_fit = pop_fit[0]
        s_val = best_fit - worst_fit
        if s_val <= 0.0:
            s_val = 0.0001

        for i in range(pop_size):
            ratio = (best_fit - pop_fit[i]) / s_val + 1.0
            logr = math.log10(ratio)
            if i < pop_size / 2:
                for j in range(items):
                    W[i, j] = 1.0 + np.random.random() * logr
            else:
                for j in range(items):
                    W[i, j] = 1.0 - np.random.random() * logr

        a = np.arctanh(-1.0 * ((iter_idx + 1) / max_iter) + 1.0)
        b = 1.0 - (iter_idx + 1) / max_iter
        a_span = 2.0 * a
        b_span = 2.0 * b

        for i in range(pop_size):
            if np.random.random() < z:
                _bsma_rc_global_row(pop_sol, i, weights, capacities, cp_list, acc_res, items, dim)
            else:
                p = math.tanh(abs(pop_fit[i] - gbest_fit))
                for j in range(items):
                    r = np.random.random()
                    vb_j = -a + a_span * np.random.random()
                    vc_j = -b + b_span * np.random.random()
                    a_idx, b_idx = _select_two_distinct_indices_excluding(pop_size, i)
                    if r < p:
                        pop_sol[i, j] = gbest_sol[j] + vb_j * (
                            W[i, j] * pop_sol[a_idx, j] - pop_sol[b_idx, j]
                        )
                    else:
                        pop_sol[i, j] = vc_j * pop_sol[i, j]
                    if np.random.random() < _ctf_flip_probability_fast(ctf_id, pop_sol[i, j]):
                        pop_sol[i, j] = 1.0
                    else:
                        pop_sol[i, j] = 0.0

            _repair_bscasma_row_v2_inplace(
                pop_sol,
                i,
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
                repair_drop_mode,
                drop_score,
            )

        _sort_pop_desc_deterministic_inplace(
            pop_sol, pop_fit, tmp_sol, tmp_fit, idx_work, pop_size, items
        )
        if pop_fit[0] > gbest_fit:
            gbest_fit = pop_fit[0]
            for j in range(items):
                gbest_sol[j] = pop_sol[0, j]
            stagnation_iters = 0
        else:
            stagnation_iters += 1
        if gbest_fit == glbal_best:
            return gbest_fit

        if restart_enabled and stagnation_iters >= restart_window:
            first_restart_row = pop_size - restart_rows
            if first_restart_row < 0:
                first_restart_row = 0
            for row in range(first_restart_row, pop_size):
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
                    repair_drop_mode,
                    drop_score,
                )
                if pop_fit[row] > gbest_fit:
                    gbest_fit = pop_fit[row]
                    for j in range(items):
                        gbest_sol[j] = pop_sol[row, j]
            restart_stats[0] += 1
            restart_stats[1] += pop_size - first_restart_row
            stagnation_iters = 0
            if gbest_fit == glbal_best:
                return gbest_fit
            _sort_pop_desc_deterministic_inplace(
                pop_sol, pop_fit, tmp_sol, tmp_fit, idx_work, pop_size, items
            )

    return gbest_fit


class BSMARCNumbaCore:
    _item_eval_cache: dict[Any, dict[str, Any]] = {}

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
        z: float,
        max_iter: int,
        ctf_id: int = 0,
        eval_group_decimals: int = 1,
        eval_group_shuffle: bool = False,
        eval_rc_eps: float = 1.0e-9,
        eval_x_eps: float = 1.0e-9,
        repair_passes: int = 1,
        repair_swap_limit: int = 0,
        mixed_init_enabled: bool = False,
        restart_enabled: bool = False,
        restart_window: int = 40,
        restart_ratio: float = 0.25,
        restart_strong_p: float = 0.85,
        restart_core_p: float = 0.50,
        restart_weak_p: float = 0.15,
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
        self.item_eval_method = "lp_rc_groups" if self.eval_group_shuffle else "lp_rc_ordered"
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
        self.lp_fractional_count = 0
        self.eff_group_count = 0
        self.item_eval_payload: dict[str, Any] = {}

        if max_iter <= 0:
            raise ValueError("max_iter must be > 0")
        if pop_size < 3:
            raise ValueError("pop_size must be >= 3")
        if not (0.0 < z <= 1.0):
            raise ValueError("z must satisfy 0 < z <= 1")
        if self.eval_group_decimals < 0:
            raise ValueError("eval_group_decimals must be >= 0")
        if self.eval_rc_eps < 0.0:
            raise ValueError("eval_rc_eps must be >= 0")
        if self.eval_x_eps < 0.0:
            raise ValueError("eval_x_eps must be >= 0")
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

        self.ctf_id = int(ctf_id)
        self.pop_size = int(pop_size)
        self.max_iter = int(max_iter)
        self.cp_list = self.pseudo_utility()
        self.z = float(z)
        self.W = np.zeros([self.pop_size, self.items])
        self.pop_fit = np.zeros([self.pop_size], dtype=int)
        self.pop_sol = self.initial_pop()
        self.Gbest_sol = self.pop_sol[0].copy()
        self.Gbest_fit = int(self.pop_fit[0])

    def pseudo_utility(self) -> np.ndarray:
        cache_key = _item_eval_cache_key(
            self.values,
            self.weights,
            self.capacities,
            eval_group_decimals=self.eval_group_decimals,
            eval_rc_eps=self.eval_rc_eps,
            eval_x_eps=self.eval_x_eps,
        )
        cached = type(self)._item_eval_cache.get(cache_key)
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
            self.linprog_runtime = time.perf_counter() - t_lp0
            type(self)._item_eval_cache[cache_key] = payload

        if self.eval_group_shuffle:
            cp_list, group_count = _shuffle_efficiency_groups(
                np.asarray(payload["base_order"], dtype=np.int64),
                np.asarray(payload["bucket"], dtype=np.int64),
                np.asarray(payload["rounded_efficiency"], dtype=np.float64),
            )
        else:
            cp_list = np.ascontiguousarray(np.asarray(payload["base_order"], dtype=np.int64).copy())
            group_count = int(payload["eff_group_count"])
        self.item_eval_payload = payload
        self.item_eval_fallback = bool(payload["fallback"])
        self.lp_fractional_count = int(payload["lp_fractional_count"])
        self.eff_group_count = int(group_count)
        return cp_list

    def _finish_initial_row(self, population: np.ndarray, row: int) -> None:
        self.pop_fit[row] = np.sum(np.multiply(self.values, population[row]))

    def _fill_initial_random_greedy_row(self, population: np.ndarray, row: int) -> None:
        accumulated_resources = np.zeros([self.dim])
        for j in self.cp_list:
            if np.random.random() < 0.5:
                candidate_resources = accumulated_resources + self.weights[j]
                if np.all(candidate_resources <= self.capacities):
                    accumulated_resources = candidate_resources
                    population[row, j] = 1

    def _fill_initial_deterministic_greedy_row(self, population: np.ndarray, row: int) -> None:
        accumulated_resources = np.zeros([self.dim])
        for j in self.cp_list:
            candidate_resources = accumulated_resources + self.weights[j]
            if np.all(candidate_resources <= self.capacities):
                accumulated_resources = candidate_resources
                population[row, j] = 1

    def _fill_initial_lp_rounding_row(self, population: np.ndarray, row: int, threshold: float) -> None:
        x_lp = np.asarray(self.item_eval_payload.get("x_lp", np.zeros(self.items)), dtype=np.float64)
        accumulated_resources = np.zeros([self.dim])
        for j in self.cp_list:
            if x_lp[j] >= threshold:
                candidate_resources = accumulated_resources + self.weights[j]
                if np.all(candidate_resources <= self.capacities):
                    accumulated_resources = candidate_resources
                    population[row, j] = 1

    def _fill_initial_rcl_greedy_row(self, population: np.ndarray, row: int) -> None:
        rcl_size = max(2, int(math.sqrt(self.items)))
        accumulated_resources = np.zeros([self.dim])
        for start in range(0, self.items, rcl_size):
            end = min(self.items, start + rcl_size)
            block = np.ascontiguousarray(self.cp_list[start:end].copy())
            np.random.shuffle(block)
            for j in block:
                candidate_resources = accumulated_resources + self.weights[j]
                if np.all(candidate_resources <= self.capacities):
                    accumulated_resources = candidate_resources
                    population[row, j] = 1

    def initial_pop(self) -> np.ndarray:
        population = np.zeros([self.pop_size, self.items])
        if not self.mixed_init_enabled:
            for row in range(self.pop_size):
                self._fill_initial_random_greedy_row(population, row)
                self._finish_initial_row(population, row)
            return population

        deterministic_count = min(self.pop_size, max(1, int(math.ceil(self.pop_size * 0.10))))
        lp_count = min(self.pop_size - deterministic_count, int(math.ceil(self.pop_size * 0.20)))
        rcl_count = min(self.pop_size - deterministic_count - lp_count, int(math.ceil(self.pop_size * 0.40)))
        thresholds = (0.35, 0.50, 0.65, 0.80)
        row = 0
        for _ in range(deterministic_count):
            self._fill_initial_deterministic_greedy_row(population, row)
            self._finish_initial_row(population, row)
            row += 1
        for k in range(lp_count):
            self._fill_initial_lp_rounding_row(population, row, thresholds[k % len(thresholds)])
            self._finish_initial_row(population, row)
            row += 1
        for _ in range(rcl_count):
            self._fill_initial_rcl_greedy_row(population, row)
            self._finish_initial_row(population, row)
            row += 1
        while row < self.pop_size:
            self._fill_initial_random_greedy_row(population, row)
            self._finish_initial_row(population, row)
            row += 1
        return population

    def sort_pop(self) -> tuple[np.ndarray, np.ndarray]:
        pop_sol = np.zeros([self.pop_size, self.items])
        pop_fit = np.zeros([self.pop_size])
        sorted_indices = _argsort_pop_fit_desc_deterministic(self.pop_fit, self.pop_size)
        for i in range(self.pop_size):
            pop_sol[i] = self.pop_sol[sorted_indices[i]]
            pop_fit[i] = self.pop_fit[sorted_indices[i]]
        return pop_sol, pop_fit

    def run(self) -> tuple[np.ndarray, int]:
        np.random.seed(self.seed)
        self.pop_sol, self.pop_fit = self.sort_pop()
        pop_sol = np.ascontiguousarray(self.pop_sol, dtype=np.float64)
        pop_fit = np.ascontiguousarray(self.pop_fit, dtype=np.float64)
        ps, it, dm = self.pop_size, self.items, self.dim
        W = np.empty((ps, it), dtype=np.float64)
        acc_res = np.zeros(dm, dtype=np.float64)
        tmp_sol = np.empty((ps, it), dtype=np.float64)
        tmp_fit = np.empty(ps, dtype=np.float64)
        idx_work = np.empty(ps, dtype=np.int64)
        gbest_sol = np.empty(it, dtype=np.float64)
        repair_stats = np.zeros(1, dtype=np.int64)
        drop_score = np.ones(it, dtype=np.float64)
        restart_stats = np.zeros(2, dtype=np.int64)
        bucket = np.ascontiguousarray(np.asarray(self.item_eval_payload["bucket"], dtype=np.int64))
        restart_rows = int(math.ceil(self.pop_size * self.restart_ratio)) if self.restart_enabled else 0
        if self.restart_enabled and restart_rows < 1:
            restart_rows = 1
        if restart_rows > self.pop_size:
            restart_rows = self.pop_size
        rng_seed = int(self.seed) if self.seed is not None else 0

        gfit = _bsma_rc_main_loop_numba(
            pop_sol,
            pop_fit,
            self.values,
            self.weights,
            self.capacities,
            self.cp_list,
            W,
            ps,
            it,
            dm,
            self.z,
            float(self.glbal_best),
            self.max_iter,
            rng_seed,
            acc_res,
            tmp_sol,
            tmp_fit,
            idx_work,
            gbest_sol,
            self.ctf_id,
            int(self.repair_passes),
            int(self.repair_swap_limit),
            repair_stats,
            0,
            drop_score,
            bucket,
            bool(self.restart_enabled),
            int(self.restart_window),
            int(restart_rows),
            float(self.restart_strong_p),
            float(self.restart_core_p),
            float(self.restart_weak_p),
            restart_stats,
        )

        self.repair_swap_accepts = int(repair_stats[0])
        self.restart_count = int(restart_stats[0])
        self.restart_rows = int(restart_stats[1])
        out = np.empty(it, dtype=np.int64)
        for j in range(it):
            out[j] = 1 if gbest_sol[j] >= 0.5 else 0
        return out, int(gfit)


@dataclass
class BSMARCNumbaSolver:
    def solve(self, problem: ProblemModel, config: dict[str, Any], rng: np.random.Generator) -> SolveResult:
        stop_condition = config.get("stop_condition", {})
        if stop_condition.get("type") != "max_iterations":
            raise ValueError("bsma_rc_numba only supports stop_condition.type=max_iterations")
        max_iterations = int(stop_condition.get("max_iterations", 0))
        if max_iterations <= 0:
            raise ValueError("max_iterations must be > 0")

        raw_params = config.get("params", {})
        if not isinstance(raw_params, dict):
            raise ValueError("params must be a mapping when present")
        pop_size = int(raw_params.get("pop_size", 20))
        z = float(raw_params.get("z", 0.08))
        eval_group_decimals = int(raw_params.get("eval_group_decimals", 1))
        eval_group_shuffle = _coerce_bool_param(
            raw_params.get("eval_group_shuffle", False),
            name="eval_group_shuffle",
        )
        eval_rc_eps = float(raw_params.get("eval_rc_eps", 1.0e-9))
        eval_x_eps = float(raw_params.get("eval_x_eps", 1.0e-9))
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
        if pop_size < 3:
            raise ValueError("params.pop_size must be >= 3")
        if not (0.0 < z <= 1.0):
            raise ValueError("params.z must satisfy 0 < z <= 1")
        if eval_group_decimals < 0:
            raise ValueError("params.eval_group_decimals must be >= 0")
        if eval_rc_eps < 0.0:
            raise ValueError("params.eval_rc_eps must be >= 0")
        if eval_x_eps < 0.0:
            raise ValueError("params.eval_x_eps must be >= 0")
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

        _, ctf_id = parse_ctf_kind(raw_params)
        run_seed = int(config.get("run_seed", rng.integers(0, np.iinfo(np.int32).max)))
        np.random.seed(run_seed)
        t_alg0 = time.perf_counter()
        core = BSMARCNumbaCore(
            problem.items,
            problem.dim,
            problem.best_known,
            problem.values,
            problem.weights,
            problem.capacities,
            seed=run_seed,
            pop_size=pop_size,
            z=z,
            max_iter=int(max_iterations),
            ctf_id=ctf_id,
            eval_group_decimals=eval_group_decimals,
            eval_group_shuffle=eval_group_shuffle,
            eval_rc_eps=eval_rc_eps,
            eval_x_eps=eval_x_eps,
            repair_passes=repair_passes,
            repair_swap_limit=repair_swap_limit,
            mixed_init_enabled=mixed_init_enabled,
            restart_enabled=restart_enabled,
            restart_window=restart_window,
            restart_ratio=restart_ratio,
            restart_strong_p=restart_strong_p,
            restart_core_p=restart_core_p,
            restart_weak_p=restart_weak_p,
        )
        best_sol, best_fit = core.run()
        algorithm_runtime = time.perf_counter() - t_alg0
        evaluation_count = int(core.pop_size + max_iterations * core.pop_size)
        stop_reason = "best_known_reached" if int(best_fit) == int(problem.best_known) else "max_iterations_reached"

        return SolveResult(
            problem_id=problem.problem_id,
            solver_id=str(config.get("solver_id", "bsma_rc_numba")),
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
                "repair_passes": int(core.repair_passes),
                "repair_swap_limit": int(core.repair_swap_limit),
                "repair_swap_accepts": int(core.repair_swap_accepts),
                "mixed_init_enabled": bool(core.mixed_init_enabled),
                "restart_enabled": bool(core.restart_enabled),
                "restart_window": int(core.restart_window),
                "restart_ratio": float(core.restart_ratio),
                "restart_count": int(core.restart_count),
                "restart_rows": int(core.restart_rows),
                "lp_fractional_count": int(core.lp_fractional_count),
                "eff_group_count": int(core.eff_group_count),
                "numba": True,
                "rc": True,
                "z": float(z),
            },
        )
