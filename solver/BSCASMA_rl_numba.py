"""BRLSMASCA RL/Q-learning Numba solver.

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
            for d in range(dim):
                acc_res[d] += weights[jj, d]
            ok = True
            for d in range(dim):
                if acc_res[d] > capacities[d]:
                    ok = False
                    break
            if ok:
                pop_sol[row, jj] = 1.0


@njit(cache=True)
def _sma_local_row(
    pop_sol: np.ndarray,
    pop_fit: np.ndarray,
    row: int,
    gbest_fit: float,
    gbest_sol: np.ndarray,
    W: np.ndarray,
    local_a: float,
    local_b: float,
    pop_size: int,
    items: int,
    ctf_id: int,
) -> None:
    p = math.tanh(abs(pop_fit[row] - gbest_fit))
    local_a_span = 2.0 * local_a
    local_b_span = 2.0 * local_b
    for j in range(items):
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
        if np.random.random() < _ctf_flip_probability_fast(ctf_id, pop_sol[row, j]):
            pop_sol[row, j] = 1.0
        else:
            pop_sol[row, j] = 0.0


@njit(cache=True)
def _sca_sin_row(
    pop_sol: np.ndarray,
    individual_best_sol: np.ndarray,
    row: int,
    individual_id: int,
    gbest_sol: np.ndarray,
    r1: float,
    items: int,
    two_pi: float,
    ctf_id: int,
) -> None:
    for j in range(items):
        r2 = two_pi * np.random.random()
        r3 = 2.0 * np.random.random()
        pop_sol[row, j] = individual_best_sol[individual_id, j] + (
            r1 * math.sin(r2) * abs(r3 * gbest_sol[j] - individual_best_sol[individual_id, j])
        )
        if np.random.random() < _ctf_flip_probability_fast(ctf_id, pop_sol[row, j]):
            pop_sol[row, j] = 1.0
        else:
            pop_sol[row, j] = 0.0


@njit(cache=True)
def _sca_cos_row(
    pop_sol: np.ndarray,
    individual_best_sol: np.ndarray,
    row: int,
    individual_id: int,
    gbest_sol: np.ndarray,
    r1: float,
    items: int,
    two_pi: float,
    ctf_id: int,
) -> None:
    for j in range(items):
        r2 = two_pi * np.random.random()
        r3 = 2.0 * np.random.random()
        pop_sol[row, j] = individual_best_sol[individual_id, j] + (
            r1 * math.cos(r2) * abs(r3 * gbest_sol[j] - individual_best_sol[individual_id, j])
        )
        if np.random.random() < _ctf_flip_probability_fast(ctf_id, pop_sol[row, j]):
            pop_sol[row, j] = 1.0
        else:
            pop_sol[row, j] = 0.0


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

    for iter_idx in range(max_iter):
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
                    local_a,
                    local_b,
                    pop_size,
                    items,
                    ctf_id,
                )
            elif action == 2:
                _sca_sin_row(
                    pop_sol, individual_best_sol, row, individual_id, gbest_sol, r1, items, two_pi, ctf_id
                )
            elif action == 3:
                _sca_cos_row(
                    pop_sol, individual_best_sol, row, individual_id, gbest_sol, r1, items, two_pi, ctf_id
                )

            _repair_bscasma_row_inplace(
                pop_sol, row, pop_fit, values, weights, capacities, cp_list, acc_res, items, dim
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
    return gbest_fit


class BRLSMASCARLNumbaCore:
    _cp_list_cache: dict[Any, np.ndarray] = {}

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
    ) -> None:
        self.items = items
        self.dim = dim
        self.glbal_best = glbal_best
        self.values, self.weights, self.capacities = _expect_mkp_problem_tensors(values, weights, capacities)
        self.seed = seed
        self.linprog_runtime = 0.0
        self.cp_list_cache_hit = False

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
        cache_key = _cp_list_cache_key(self.values, self.weights, self.capacities)
        cached = type(self)._cp_list_cache.get(cache_key)
        if cached is not None:
            self.cp_list_cache_hit = True
            self.linprog_runtime = 0.0
            return cached.copy()

        self.cp_list_cache_hit = False
        constraints = np.concatenate((self.capacities, np.ones(self.items)))
        i_weight = -np.concatenate((self.weights, np.eye(self.items)), axis=1)
        i_profit = self.values * -1
        t_lp0 = time.perf_counter()
        result = linprog(constraints, i_weight, i_profit)
        self.linprog_runtime = time.perf_counter() - t_lp0
        shadow_price = result.x[: len(self.capacities)]
        denom = np.matmul(shadow_price.T, self.weights.T)
        with np.errstate(divide="ignore", invalid="ignore"):
            pseudo_utilities = (-i_profit).T / denom
        x = (-np.asarray(pseudo_utilities, dtype=np.float64)).ravel()
        cp_list = np.ascontiguousarray(np.argsort(x, kind="stable").astype(np.int64))
        type(self)._cp_list_cache[cache_key] = cp_list.copy()
        return cp_list

    def initial_pop(self) -> None:
        self.pop_sol = np.zeros([self.pop_size, self.items])
        for i in range(self.pop_size):
            accumulated_resources = np.zeros([self.dim])
            for j in self.cp_list:
                if np.random.random() < 0.5:
                    accumulated_resources += self.weights[j]
                    if np.all(accumulated_resources <= self.capacities):
                        self.pop_sol[i, j] = 1
            self.pop_fit[i] = np.sum(np.multiply(self.values, self.pop_sol[i]))
            self.individual_best_sol[i] = self.pop_sol[i]
            self.individual_best_fit[i] = self.pop_fit[i]

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
        )

        self.individual_ids = np.asarray(individual_ids)
        self.q_table = np.asarray(q_table)
        self.action_counts = np.asarray(action_counts)
        out = np.empty(it, dtype=np.int64)
        for j in range(it):
            out[j] = 1 if gbest_sol[j] >= 0.5 else 0
        return out, int(gfit)


@dataclass
class BRLSMASCARLNumbaSolver:
    def solve(self, problem: ProblemModel, config: dict[str, Any], rng: np.random.Generator) -> SolveResult:
        stop_condition = config.get("stop_condition", {})
        if stop_condition.get("type") != "max_iterations":
            raise ValueError("brlsmasca_rl_numba only supports stop_condition.type=max_iterations")
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

        _, ctf_id = parse_ctf_kind(raw_params)
        run_seed = int(config.get("run_seed", rng.integers(0, np.iinfo(np.int32).max)))
        np.random.seed(run_seed)
        t_alg0 = time.perf_counter()
        core = BRLSMASCARLNumbaCore(
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
        )
        best_sol, best_fit = core.run()
        algorithm_runtime = time.perf_counter() - t_alg0
        evaluation_count = int(core.pop_size + max_iterations * core.pop_size)
        stop_reason = "best_known_reached" if int(best_fit) == int(problem.best_known) else "max_iterations_reached"
        action_counts = np.asarray(core.action_counts, dtype=np.int64)

        return SolveResult(
            problem_id=problem.problem_id,
            solver_id=str(config.get("solver_id", "brlsmasca_rl_numba")),
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
                "numba": True,
                "rl": True,
                "z": float(z),
                "alpha": float(alpha),
                "gamma": float(gamma),
                "q_table_nonzero": int(np.count_nonzero(core.q_table)),
                "action_counts": action_counts.sum(axis=0).astype(int).tolist(),
            },
        )
