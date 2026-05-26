"""BRLSMASCA test-policy Numba solver.

This file is intentionally independent from ``BSCASMA_rl_numba.py``. Shared
Numba kernels are duplicated so the test-policy and RL variants can evolve
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
def _sort_bscasma_desc_deterministic_inplace(
    pop_sol: np.ndarray,
    pop_fit: np.ndarray,
    individual_ids: np.ndarray,
    tmp_sol: np.ndarray,
    tmp_fit: np.ndarray,
    tmp_ids: np.ndarray,
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
    for i in range(pop_size):
        for j in range(items):
            pop_sol[i, j] = tmp_sol[i, j]
        pop_fit[i] = tmp_fit[i]
        individual_ids[i] = tmp_ids[i]


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
def _policy_action(best_method: np.ndarray, i: int) -> int:
    r = np.random.random()
    if r < 0.9:
        return int(best_method[i])
    bm = int(best_method[i])
    pick = np.random.randint(0, 3)
    if pick >= bm:
        return pick + 1
    return pick


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
def _bscasma_test_main_loop_numba(
    pop_sol: np.ndarray,
    pop_fit: np.ndarray,
    individual_best_sol: np.ndarray,
    individual_best_fit: np.ndarray,
    individual_ids: np.ndarray,
    best_method: np.ndarray,
    exe_time: np.ndarray,
    values: np.ndarray,
    weights: np.ndarray,
    capacities: np.ndarray,
    cp_list: np.ndarray,
    W: np.ndarray,
    pop_size: int,
    items: int,
    dim: int,
    a: float,
    glbal_best: int,
    max_iter: int,
    rng_seed: int,
    tmp_sol: np.ndarray,
    tmp_fit: np.ndarray,
    tmp_ids: np.ndarray,
    idx_work: np.ndarray,
    acc_res: np.ndarray,
    gbest_sol: np.ndarray,
    ctf_id: int,
) -> float:
    np.random.seed(rng_seed)
    gbest_fit = pop_fit[0]
    for j in range(items):
        gbest_sol[j] = pop_sol[0, j]

    mf = float(max_iter)
    two_pi = 2.0 * math.pi
    for iter_idx in range(max_iter):
        _update_sma_weight_inplace(W, pop_fit, pop_size, items)
        r1 = a - a * (float(iter_idx) / mf)
        local_a = np.arctanh(-1.0 * ((iter_idx + 1) / mf) + 1.0)
        local_b = 1.0 - (iter_idx + 1) / mf

        for row in range(pop_size):
            individual_id = int(individual_ids[row])
            action = _policy_action(best_method, individual_id)

            if action == 0:
                _sma_global_row(pop_sol, row, weights, capacities, cp_list, acc_res, items, dim)
                exe_time[individual_id, 0] += 1
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
                exe_time[individual_id, 1] += 1
            elif action == 2:
                _sca_sin_row(
                    pop_sol, individual_best_sol, row, individual_id, gbest_sol, r1, items, two_pi, ctf_id
                )
                exe_time[individual_id, 2] += 1
            elif action == 3:
                _sca_cos_row(
                    pop_sol, individual_best_sol, row, individual_id, gbest_sol, r1, items, two_pi, ctf_id
                )
                exe_time[individual_id, 3] += 1

            _repair_bscasma_row_inplace(
                pop_sol, row, pop_fit, values, weights, capacities, cp_list, acc_res, items, dim
            )

            if pop_fit[row] > individual_best_fit[individual_id]:
                for j in range(items):
                    individual_best_sol[individual_id, j] = pop_sol[row, j]
                individual_best_fit[individual_id] = pop_fit[row]
                best_method[individual_id] = action

            if pop_fit[row] > gbest_fit:
                gbest_fit = pop_fit[row]
                for j in range(items):
                    gbest_sol[j] = pop_sol[row, j]

            if gbest_fit == float(glbal_best):
                return gbest_fit

        _sort_bscasma_desc_deterministic_inplace(
            pop_sol,
            pop_fit,
            individual_ids,
            tmp_sol,
            tmp_fit,
            tmp_ids,
            idx_work,
            pop_size,
            items,
        )

    return gbest_fit


class BRLSMASCATestNumbaCore:
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
        max_iter: int,
        prob_arr: tuple[float, ...] | list[float] = (0.04, 0.46, 0.25, 0.25),
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
        if pop_size <= 0:
            raise ValueError("pop_size must be > 0")
        if a <= 0:
            raise ValueError("a must be > 0")

        self.ctf_id = int(ctf_id)
        self.pop_size = int(pop_size)
        self.max_iter = int(max_iter)
        self.cp_list = self.pseudo_utility()
        self.cp_list_old = self.cp_list
        self.std = int(self.items * 0.15)
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
        self._prob_arr_template = tuple(float(x) for x in prob_arr)
        self.prob_arr = np.array(list(self._prob_arr_template) * self.pop_size)
        self.exe_time = np.zeros([self.pop_size, 4], dtype=int)
        self.best_method = self.init_best_method()

    def init_best_method(self) -> np.ndarray:
        thresholds = np.cumsum(np.asarray(self._prob_arr_template, dtype=np.float64))
        random_selection = np.empty(self.pop_size, dtype=np.int64)
        for i in range(self.pop_size):
            r = np.random.random()
            if r < thresholds[0]:
                random_selection[i] = 0
            elif r < thresholds[1]:
                random_selection[i] = 1
            elif r < thresholds[2]:
                random_selection[i] = 2
            else:
                random_selection[i] = 3
        return random_selection

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
        self.pop_sol, self.pop_fit, self.individual_ids = self.sort_pop_with_ids()
        pop_sol = np.ascontiguousarray(self.pop_sol, dtype=np.float64)
        pop_fit = np.ascontiguousarray(self.pop_fit, dtype=np.float64)
        individual_best_sol = np.ascontiguousarray(self.individual_best_sol, dtype=np.float64)
        individual_best_fit = np.ascontiguousarray(self.individual_best_fit, dtype=np.float64)
        individual_ids = np.ascontiguousarray(self.individual_ids.astype(np.int64))
        best_method = np.ascontiguousarray(self.best_method.astype(np.int64))
        exe_time = np.ascontiguousarray(self.exe_time.astype(np.int64))
        ps, it, dm = self.pop_size, self.items, self.dim
        W = np.empty((ps, it), dtype=np.float64)
        tmp_sol = np.empty((ps, it), dtype=np.float64)
        tmp_fit = np.empty(ps, dtype=np.float64)
        tmp_ids = np.empty(ps, dtype=np.int64)
        idx_work = np.empty(ps, dtype=np.int64)
        acc_res = np.zeros(dm, dtype=np.float64)
        gbest_sol = np.empty(it, dtype=np.float64)
        rng_seed = int(self.seed) if self.seed is not None else 0

        gfit = _bscasma_test_main_loop_numba(
            pop_sol,
            pop_fit,
            individual_best_sol,
            individual_best_fit,
            individual_ids,
            best_method,
            exe_time,
            self.values,
            self.weights,
            self.capacities,
            self.cp_list,
            W,
            ps,
            it,
            dm,
            self.a,
            int(self.glbal_best),
            self.max_iter,
            rng_seed,
            tmp_sol,
            tmp_fit,
            tmp_ids,
            idx_work,
            acc_res,
            gbest_sol,
            self.ctf_id,
        )

        self.individual_ids = np.asarray(individual_ids)
        self.exe_time = np.asarray(exe_time)
        self.best_method = np.asarray(best_method)
        out = np.empty(it, dtype=np.int64)
        for j in range(it):
            out[j] = 1 if gbest_sol[j] >= 0.5 else 0
        return out, int(gfit)


@dataclass
class BRLSMASCATestNumbaSolver:
    def solve(self, problem: ProblemModel, config: dict[str, Any], rng: np.random.Generator) -> SolveResult:
        stop_condition = config.get("stop_condition", {})
        if stop_condition.get("type") != "max_iterations":
            raise ValueError("brlsmasca_test_numba only supports stop_condition.type=max_iterations")
        max_iterations = int(stop_condition.get("max_iterations", 0))
        if max_iterations <= 0:
            raise ValueError("max_iterations must be > 0")

        raw_params = config.get("params", {})
        if not isinstance(raw_params, dict):
            raise ValueError("params must be a mapping when present")
        pop_size = int(raw_params.get("pop_size", 20))
        a = float(raw_params.get("a", 2))
        prob_arr_raw = raw_params.get("prob_arr", [0.04, 0.46, 0.25, 0.25])
        if not isinstance(prob_arr_raw, (list, tuple)) or len(prob_arr_raw) != 4:
            raise ValueError(
                "params.prob_arr must be a list/tuple of length 4 (probabilities for sma_global / sma_local / sca_sin / sca_cos)"
            )
        prob_arr = tuple(float(x) for x in prob_arr_raw)
        if any(x < 0 for x in prob_arr) or abs(sum(prob_arr) - 1.0) > 1e-9:
            raise ValueError("params.prob_arr must be non-negative and sum to 1.0")
        if pop_size <= 0:
            raise ValueError("params.pop_size must be > 0")
        if a <= 0:
            raise ValueError("params.a must be > 0")

        _, ctf_id = parse_ctf_kind(raw_params)
        run_seed = int(config.get("run_seed", rng.integers(0, np.iinfo(np.int32).max)))
        np.random.seed(run_seed)

        t_alg0 = time.perf_counter()
        core = BRLSMASCATestNumbaCore(
            problem.items,
            problem.dim,
            problem.best_known,
            problem.values,
            problem.weights,
            problem.capacities,
            seed=run_seed,
            pop_size=pop_size,
            a=a,
            max_iter=int(max_iterations),
            prob_arr=prob_arr,
            ctf_id=ctf_id,
        )
        best_sol, best_fit = core.run()
        algorithm_runtime = time.perf_counter() - t_alg0
        evaluation_count = int(core.pop_size + max_iterations * core.pop_size)
        stop_reason = "best_known_reached" if int(best_fit) == int(problem.best_known) else "max_iterations_reached"

        return SolveResult(
            problem_id=problem.problem_id,
            solver_id=str(config.get("solver_id", "brlsmasca_test_numba")),
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
                "rl": False,
            },
        )
