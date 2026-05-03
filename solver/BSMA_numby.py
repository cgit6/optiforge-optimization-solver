"""BSMA 的 Numba 加速版：與 [solver/BSMA.py](BSMA.py) 的 ``BSMACore`` 主迴圈數值行為對齊。

需安裝 ``numba``（例如 ``pip install numba``）。``linprog`` / ``pseudo_utility`` 仍在 Python。

主迴圈為**單一** ``@njit``（開頭於 njit 內 ``np.random.seed``，Numba RNG 不中斷）。
族群排序使用與 ``BSMA._argsort_pop_fit_desc_deterministic`` 相同的**決定性**規則（純 njit）：
適配值非遞增，同值則列索引較小者在前。
"""

from __future__ import annotations

import copy as copy
import hashlib
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
from numba import njit
from scipy.optimize import linprog

from ..engine.models import ProblemModel, SolveResult
from .BSMA import _argsort_pop_fit_desc_deterministic


def _expect_mkp_problem_tensors(
    values: np.ndarray,
    weights: np.ndarray,
    capacities: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """``ProblemModel`` 已保證 int64 C-contiguous；此處只驗證契約。"""
    for name, a in (("values", values), ("weights", weights), ("capacities", capacities)):
        if a.dtype != np.int64:
            raise TypeError(f"{name}: expected np.int64 from ProblemModel, got {a.dtype}")
        if not a.flags.c_contiguous:
            raise ValueError(f"{name}: must be C-contiguous")
    return values, weights, capacities


def _digest_float_prefix(vec: np.ndarray, count: int = 8) -> str:
    flat = np.asarray(vec, dtype=np.float64).ravel()[:count]
    return hashlib.sha256(flat.tobytes()).hexdigest()[:16]


@njit(cache=True)
def _repair_row_inplace(
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
    """等同 ``BSMACore.repair``：資源為 ``weights.T @ trial_sol``（``trial_sol`` 可為浮點）。"""
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
            else:
                break
    # 與 ``BSMACore.repair`` 一致：最終解為 0/1，適配值應為整數和（避免 float 累加誤差影響後續比較與排序）
    fi = 0.0
    for j in range(items):
        if pop_sol[row, j] >= 0.5:
            fi += float(values[j])
    pop_fit[row] = fi


@njit(cache=True)
def _sort_pop_desc_deterministic_inplace(
    pop_sol: np.ndarray,
    pop_fit: np.ndarray,
    tmp_sol: np.ndarray,
    tmp_fit: np.ndarray,
    idx_work: np.ndarray,
    pop_size: int,
    items: int,
) -> None:
    """與 ``BSMA._argsort_pop_fit_desc_deterministic`` 相同規則，就地重排 ``pop_sol`` / ``pop_fit``。"""
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
    for i in range(pop_size):
        for j in range(items):
            pop_sol[i, j] = tmp_sol[i, j]
        pop_fit[i] = tmp_fit[i]


@njit(cache=True)
def _fitness_row(pop_sol: np.ndarray, row: int, values: np.ndarray, items: int) -> float:
    """等同 ``np.sum(values * pop_sol[row])``（與參考 ``BSMACore.run`` 每代更新 fitness 一致）。"""
    s = 0.0
    for j in range(items):
        s += float(values[j]) * pop_sol[row, j]
    return s


@njit(cache=True)
def _bsma_main_loop_numba(
    pop_sol: np.ndarray,
    pop_fit: np.ndarray,
    values: np.ndarray,
    weights: np.ndarray,
    capacities: np.ndarray,
    cp_list: np.ndarray,
    pop_size: int,
    items: int,
    dim: int,
    z: float,
    glbal_best: float,
    max_iter: int,
    rng_seed: int,
    W: np.ndarray,
    acc_res: np.ndarray,
    vb: np.ndarray,
    vc: np.ndarray,
    pool: np.ndarray,
    tmp_sol: np.ndarray,
    tmp_fit: np.ndarray,
    idx_work: np.ndarray,
    gbest_sol: np.ndarray,
) -> float:
    """整段主迴圈單一 njit：開頭 ``np.random.seed`` 一次，Numba RNG 連續；每代決定性排序。

    ``gbest_sol`` / ``gbest_fit`` 語意與 ``BSMACore.run`` 一致（僅在 ``pop_fit[0] > gbest_fit`` 時更新）。
    """
    np.random.seed(rng_seed)
    gbest_fit = pop_fit[0]
    for j in range(items):
        gbest_sol[j] = pop_sol[0, j]

    for iter_idx in range(max_iter):
        for ii in range(pop_size):
            for jj in range(items):
                W[ii, jj] = 0.0

        worst_fit = pop_fit[pop_size - 1]
        best_fit = pop_fit[0]
        s_val = best_fit - worst_fit
        if s_val <= 0.0:
            s_val = 0.0001

        for i in range(pop_size):
            ratio = (best_fit - pop_fit[i]) / s_val + 1.0
            if i < pop_size / 2:
                W[i, :] = 1.0 + np.random.random(items) * np.log10(ratio)
            else:
                W[i, :] = 1.0 - np.random.random(items) * np.log10(ratio)

        a = np.arctanh(-1.0 * ((iter_idx + 1) / max_iter) + 1.0)
        b = 1.0 - (iter_idx + 1) / max_iter

        for i in range(pop_size):
            if np.random.random() < z:
                for jj in range(items):
                    pop_sol[i, jj] = 0.0
                for d in range(dim):
                    acc_res[d] = 0.0
                for pos in range(items):
                    jj = int(cp_list[pos])
                    if np.random.uniform(0.0, 1.0) < 0.5:
                        for d in range(dim):
                            acc_res[d] += weights[jj, d]
                        ok = True
                        for d in range(dim):
                            if acc_res[d] > capacities[d]:
                                ok = False
                                break
                        if ok:
                            pop_sol[i, jj] = 1.0
                pop_fit[i] = _fitness_row(pop_sol, i, values, items)
                _repair_row_inplace(
                    pop_sol, i, pop_fit, values, weights, capacities, cp_list, acc_res, items, dim
                )
            else:
                p = np.tanh(abs(pop_fit[i] - gbest_fit))
                vb[:] = np.random.uniform(-a, a, items)
                vc[:] = np.random.uniform(-b, b, items)
                for j in range(items):
                    r = np.random.random()
                    k = 0
                    for jj2 in range(pop_size):
                        if jj2 != i:
                            pool[k] = jj2
                            k += 1
                    pair = np.random.choice(pool[: pop_size - 1], 2, replace=False)
                    a_idx = int(pair[0])
                    b_idx = int(pair[1])
                    if r < p:
                        pop_sol[i, j] = gbest_sol[j] + vb[j] * (
                            W[i, j] * pop_sol[a_idx, j] - pop_sol[b_idx, j]
                        )
                    else:
                        pop_sol[i, j] = vc[j] * pop_sol[i, j]
                    if np.random.uniform(0.0, 1.0) < abs(np.tanh(pop_sol[i, j])):
                        pop_sol[i, j] = 1.0
                    else:
                        pop_sol[i, j] = 0.0
                pop_fit[i] = _fitness_row(pop_sol, i, values, items)
                _repair_row_inplace(
                    pop_sol, i, pop_fit, values, weights, capacities, cp_list, acc_res, items, dim
                )

        _sort_pop_desc_deterministic_inplace(
            pop_sol, pop_fit, tmp_sol, tmp_fit, idx_work, pop_size, items
        )
        if pop_fit[0] > gbest_fit:
            gbest_fit = pop_fit[0]
            for j in range(items):
                gbest_sol[j] = pop_sol[0, j]
        if gbest_fit == glbal_best:
            break

    return gbest_fit


class BSMANumbaCore:
    """與 ``BSMACore`` 相同前置；主迭代交給 Numba。"""

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
        if not (0.0 < z <= 1.0):
            raise ValueError("z must satisfy 0 < z <= 1")

        self.pop_size = int(pop_size)
        self.max_iter = int(max_iter)
        self.cp_list = self.pseudo_utility()
        self.z = float(z)
        self.W = np.zeros([self.pop_size, self.items])

        self.pop_fit = np.zeros([self.pop_size], dtype=int)
        self.pop_sol = self.initial_pop()
        self.Gbest_sol = copy.deepcopy(self.pop_sol[0])
        self.Gbest_fit = copy.deepcopy(self.pop_fit[0])
        self._loop_trace: list[dict[str, Any]] | None = None

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

        # 與 BSMACore.run 相同：sort 後再進 Numba 主迴圈（此時 RNG 狀態已與參考對齊）
        pop_sol = np.ascontiguousarray(self.pop_sol, dtype=np.float64)
        pop_fit = np.ascontiguousarray(self.pop_fit, dtype=np.float64)
        values = self.values
        weights = self.weights
        capacities = self.capacities
        cp_list = self.cp_list

        ps, it, dm = self.pop_size, self.items, self.dim
        W = np.zeros((ps, it), dtype=np.float64)
        acc_res = np.zeros(dm, dtype=np.float64)
        vb = np.empty(it, dtype=np.float64)
        vc = np.empty(it, dtype=np.float64)
        pool = np.empty(ps - 1, dtype=np.int64)
        tmp_sol = np.zeros((ps, it), dtype=np.float64)
        tmp_fit = np.zeros(ps, dtype=np.float64)
        idx_work = np.empty(ps, dtype=np.int64)
        gbest_sol = np.empty(it, dtype=np.float64)
        rng_seed = int(self.seed) if self.seed is not None else 0

        gfit = _bsma_main_loop_numba(
            pop_sol,
            pop_fit,
            values,
            weights,
            capacities,
            cp_list,
            ps,
            it,
            dm,
            self.z,
            float(self.glbal_best),
            self.max_iter,
            rng_seed,
            W,
            acc_res,
            vb,
            vc,
            pool,
            tmp_sol,
            tmp_fit,
            idx_work,
            gbest_sol,
        )

        out = np.empty(it, dtype=np.int64)
        for j in range(it):
            out[j] = 1 if gbest_sol[j] >= 0.5 else 0
        return out, int(gfit)


@dataclass
class BSMANumbaSolver:
    """BSMA Numba 變體；solver_id 預設 ``bsma_numba``。"""

    def solve(self, problem: ProblemModel, config: dict[str, Any], rng: np.random.Generator) -> SolveResult:
        stop_condition = config.get("stop_condition", {})
        if stop_condition.get("type") != "max_iterations":
            raise ValueError("bsma_numba only supports stop_condition.type=max_iterations")

        max_iterations = int(stop_condition.get("max_iterations", 0))
        if max_iterations <= 0:
            raise ValueError("max_iterations must be > 0")

        raw_params = config.get("params", {})
        if not isinstance(raw_params, dict):
            raise ValueError("params must be a mapping when present")
        pop_size = int(raw_params.get("pop_size", 20))
        z = float(raw_params.get("z", 0.08))
        if pop_size <= 0:
            raise ValueError("params.pop_size must be > 0")
        if not (0.0 < z <= 1.0):
            raise ValueError("params.z must satisfy 0 < z <= 1")

        run_seed = int(config.get("run_seed", rng.integers(0, np.iinfo(np.int32).max)))

        np.random.seed(run_seed)

        t_alg0 = time.perf_counter()
        core = BSMANumbaCore(
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
            solver_id=str(config.get("solver_id", "bsma_numba")),
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
