"""BSCA2 V1.20 的 Numba 加速版：與 ``BSCA2V120Core`` 主迴圈數值行為對齊。

需安裝 ``numba``。``linprog`` / ``pseudo_utility`` 仍在 Python。
主迴圈為單一 ``@njit``（開頭 ``np.random.seed`` 一次）。
排序規則與 ``BSMA._argsort_pop_fit_desc_deterministic`` 相同（自 ``BSMA_numby`` 重用就地排序）。
``repair`` 第二段與 ``BSCA2V120Core.repair`` 一致：無法加入某物品時**不** ``break``，繼續掃完 ``cp_list``。
"""

from __future__ import annotations

import copy as copy
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
from numba import njit
from scipy.optimize import linprog

from ..engine.models import ProblemModel, SolveResult
from .BSMA import _argsort_pop_fit_desc_deterministic
from .BSMA_numby import _expect_mkp_problem_tensors, _sort_pop_desc_deterministic_inplace


@njit(cache=True)
def _repair_bsca2_row_inplace(
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
    """等同 ``BSCA2V120Core.repair``（第二段不加 ``else: break``）。"""
    trial_fit = pop_fit[row]
    for d in range(dim):
        resource[d] = 0.0
    for jj in range(items):
        x = pop_sol[row, jj]
        for d in range(dim):
            resource[d] += weights[jj, d] * x

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
            for d in range(dim):
                resource[d] -= weights[jj, d]
            trial_fit -= float(values[jj])

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
                for d in range(dim):
                    resource[d] += weights[jj, d]
                trial_fit += float(values[jj])

    fi = 0.0
    for j in range(items):
        if pop_sol[row, j] >= 0.5:
            fi += float(values[j])
    pop_fit[row] = fi


@njit(cache=True)
def _fitness_row_bsca2(pop_sol: np.ndarray, row: int, values: np.ndarray, items: int) -> float:
    s = 0.0
    for j in range(items):
        s += float(values[j]) * pop_sol[row, j]
    return s


@njit(cache=True)
def _bsca2_main_loop_numba(
    pop_sol: np.ndarray,
    pop_fit: np.ndarray,
    values: np.ndarray,
    weights: np.ndarray,
    capacities: np.ndarray,
    cp_list: np.ndarray,
    pop_size: int,
    items: int,
    dim: int,
    a: float,
    glbal_best: int,
    max_iter: int,
    rng_seed: int,
    tmp_sol: np.ndarray,
    tmp_fit: np.ndarray,
    idx_work: np.ndarray,
    acc_res: np.ndarray,
    gbest_sol: np.ndarray,
) -> float:
    np.random.seed(rng_seed)
    gbest_fit = pop_fit[0]
    for j in range(items):
        gbest_sol[j] = pop_sol[0, j]

    mf = float(max_iter)
    for iter_idx in range(max_iter):
        for i in range(pop_size):
            r1 = a - a * (float(iter_idx) / mf)

            for j in range(items):
                r2 = np.pi * np.random.uniform(0.0, 2.0)
                r3 = np.random.uniform(0.0, 2.0)
                r4 = np.random.uniform(0.0, 1.0)

                if r4 < 0.5:
                    pop_sol[i, j] = pop_sol[i, j] + (
                        abs(r1 * np.sin(r2)) * r3 * gbest_sol[j] - pop_sol[i, j]
                    )
                else:
                    pop_sol[i, j] = pop_sol[i, j] + (
                        abs(r1 * np.cos(r2)) * r3 * gbest_sol[j] - pop_sol[i, j]
                    )

                if np.random.uniform(0.0, 1.0) < abs(np.tanh(pop_sol[i, j])):
                    pop_sol[i, j] = 1.0
                else:
                    pop_sol[i, j] = 0.0

            pop_fit[i] = _fitness_row_bsca2(pop_sol, i, values, items)
            _repair_bsca2_row_inplace(
                pop_sol, i, pop_fit, values, weights, capacities, cp_list, acc_res, items, dim
            )

            _sort_pop_desc_deterministic_inplace(
                pop_sol, pop_fit, tmp_sol, tmp_fit, idx_work, pop_size, items
            )

            if pop_fit[0] > gbest_fit:
                gbest_fit = pop_fit[0]
                for j in range(items):
                    gbest_sol[j] = pop_sol[0, j]
            if gbest_fit == float(glbal_best):
                return gbest_fit

    return gbest_fit


class BSCA2V120NumbaCore:
    """與 ``BSCA2V120Core`` 相同前置；主迭代交給 Numba。"""

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
    ) -> None:
        self.items = items
        self.dim = dim
        self.glbal_best = glbal_best
        self.values, self.weights, self.capacities = _expect_mkp_problem_tensors(values, weights, capacities)
        self.seed = seed
        self.linprog_runtime = 0.0

        if max_iter <= 0:
            raise ValueError("max_iter must be > 0")
        if pop_size <= 0:
            raise ValueError("pop_size must be > 0")
        if a <= 0:
            raise ValueError("a must be > 0")

        self.pop_size = int(pop_size)
        self.max_iter = int(max_iter)
        self.cp_list = self.pseudo_utility()
        self.a = float(a)

        self.pop_fit = np.zeros([self.pop_size], dtype=int)
        self.pop_sol = self.initial_pop()
        self.Gbest_sol = copy.deepcopy(self.pop_sol[0])
        self.Gbest_fit = copy.deepcopy(self.pop_fit[0])

    def pseudo_utility(self) -> np.ndarray:
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
        return np.ascontiguousarray((-pseudo_utilities).argsort().astype(np.int64))

    def initial_pop(self) -> np.ndarray:
        population = np.zeros([self.pop_size, self.items])
        for i in range(self.pop_size):
            accumulated_resources = np.zeros([self.dim])
            for j in self.cp_list:
                if np.random.uniform(0.0, 1.0) < 0.5:
                    accumulated_resources += self.weights[j]
                    if np.all(accumulated_resources <= self.capacities):
                        population[i, j] = 1
            self.pop_fit[i] = np.sum(np.multiply(self.values, population[i]))
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
        values = self.values
        weights = self.weights
        capacities = self.capacities
        cp_list = self.cp_list

        ps, it, dm = self.pop_size, self.items, self.dim
        tmp_sol = np.zeros((ps, it), dtype=np.float64)
        tmp_fit = np.zeros(ps, dtype=np.float64)
        idx_work = np.empty(ps, dtype=np.int64)
        acc_res = np.zeros(dm, dtype=np.float64)
        gbest_sol = np.empty(it, dtype=np.float64)
        rng_seed = int(self.seed) if self.seed is not None else 0

        gfit = _bsca2_main_loop_numba(
            pop_sol,
            pop_fit,
            values,
            weights,
            capacities,
            cp_list,
            ps,
            it,
            dm,
            self.a,
            int(self.glbal_best),
            self.max_iter,
            rng_seed,
            tmp_sol,
            tmp_fit,
            idx_work,
            acc_res,
            gbest_sol,
        )

        out = np.empty(it, dtype=np.int64)
        for j in range(it):
            out[j] = 1 if gbest_sol[j] >= 0.5 else 0
        return out, int(gfit)


@dataclass
class BSCA2V120NumbaSolver:
    """BSCA2 Numba 變體；solver_id 預設 ``bsca2_numba``。"""

    def solve(self, problem: ProblemModel, config: dict[str, Any], rng: np.random.Generator) -> SolveResult:
        stop_condition = config.get("stop_condition", {})
        if stop_condition.get("type") != "max_iterations":
            raise ValueError("bsca2_numba only supports stop_condition.type=max_iterations")

        max_iterations = int(stop_condition.get("max_iterations", 0))
        if max_iterations <= 0:
            raise ValueError("max_iterations must be > 0")

        raw_params = config.get("params", {})
        if not isinstance(raw_params, dict):
            raise ValueError("params must be a mapping when present")
        pop_size = int(raw_params.get("pop_size", 20))
        a = float(raw_params.get("a", 2.0))
        if pop_size <= 0:
            raise ValueError("params.pop_size must be > 0")
        if a <= 0:
            raise ValueError("params.a must be > 0")

        run_seed = int(config.get("run_seed", rng.integers(0, np.iinfo(np.int32).max)))

        np.random.seed(run_seed)

        t_alg0 = time.perf_counter()
        core = BSCA2V120NumbaCore(
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
        )
        best_sol, best_fit = core.run()
        algorithm_runtime = time.perf_counter() - t_alg0

        pop_size = int(core.pop_size)
        evaluation_count = int(pop_size + max_iterations * pop_size)
        stop_reason = (
            "best_known_reached"
            if int(best_fit) == int(problem.best_known)
            else "max_iterations_reached"
        )

        return SolveResult(
            problem_id=problem.problem_id,
            solver_id=str(config.get("solver_id", "bsca2_numba")),
            seed=run_seed,
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
                "numba": True,
            },
        )
