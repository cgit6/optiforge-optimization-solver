"""BRLSMASCA test 版的 Numba 加速版：與 ``BRLSMASCATestCore`` 主迴圈對齊。

為 **BSMA + BSCA** 混合體，對齊時須同時遵守兩邊慣例：

- **BSMA 段**：``update_sma_weight`` 每列使用 ``np.random.random(items)`` 一次取向量（不可逐格 ``random()``）；
  ``sma_local`` 的 ``vb`` / ``vc`` 用 ``np.random.uniform(..., size=items)``；``pool`` 在每個物品維度內重填後 ``choice``（與 ``BSMA_numba`` 相同）。
- **BSCA 段**：``sca_sin`` / ``sca_cos`` 用 ``math.pi``、``math.sin`` / ``math.cos``（與 ``BSCA`` 參考版一致）。
- **族群 dtype**：``sort_pop`` 產出之 ``pop_sol`` / ``individual_best_sol`` 須為 **float64**（與 ``BSMA.sort_pop`` 一致）；若為 ``int``，SCA 浮點中間值寫入會被 NumPy 截斷，與本檔全程 float 的 njit 版會分叉。

``linprog`` / ``pseudo_utility`` / ``init_best_method`` 仍在 Python。主迴圈單一 ``@njit``（開頭 ``np.random.seed`` 一次）。
``repair`` 第二段無 ``else: break``（與 ``BRLSMASCATestCore.repair`` 相同），沿用 ``BSCA_numba._repair_bsca_row_inplace``。
"""

from __future__ import annotations

import copy as copy
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
from .BSCA_numba import _fitness_row_bsca, _repair_bsca_row_inplace
from .BSMA_numba import _expect_mkp_problem_tensors


_POLICY_MODE_RL_BEST_METHOD = 0
_POLICY_MODE_RANDOM_FAMILY_50_50 = 1
_POLICY_MODE_IDS = {
    "rl_best_method": _POLICY_MODE_RL_BEST_METHOD,
    "random_family_50_50": _POLICY_MODE_RANDOM_FAMILY_50_50,
}


@njit(cache=True)
def _sort_bscasma_desc_deterministic_inplace(
    pop_sol: np.ndarray,
    pop_fit: np.ndarray,
    individual_best_sol: np.ndarray,
    individual_best_fit: np.ndarray,
    tmp_sol: np.ndarray,
    tmp_fit: np.ndarray,
    tmp_ibs: np.ndarray,
    tmp_ibf: np.ndarray,
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
            tmp_ibs[i, j] = individual_best_sol[si, j]
        tmp_fit[i] = pop_fit[si]
        tmp_ibf[i] = individual_best_fit[si]
    for i in range(pop_size):
        for j in range(items):
            pop_sol[i, j] = tmp_sol[i, j]
            individual_best_sol[i, j] = tmp_ibs[i, j]
        pop_fit[i] = tmp_fit[i]
        individual_best_fit[i] = tmp_ibf[i]


@njit(cache=True)
def _update_sma_weight_inplace(W: np.ndarray, pop_fit: np.ndarray, pop_size: int, items: int) -> None:
    """與 ``BSMA_numba._bsma_main_loop_numba`` 內權重段及 ``BRLSMASCATestCore.update_sma_weight`` 相同：
    每列一次 ``np.random.random(items)``（不可改成逐格 random，否則與 NumPy RNG 序列不一致）。
    """
    worst_fit = pop_fit[pop_size - 1]
    best_fit = pop_fit[0]
    S = best_fit - worst_fit
    if S <= 0.0:
        S = 0.0001
    for i in range(pop_size):
        ratio = (best_fit - pop_fit[i]) / S + 1.0
        logr = np.log10(ratio)
        if i < pop_size / 2:
            W[i, :] = 1.0 + np.random.random(items) * logr
        else:
            W[i, :] = 1.0 - np.random.random(items) * logr


@njit(cache=True)
def _policy_action(
    best_method: np.ndarray,
    i: int,
    policy_mode_id: int,
    sma_global_ratio: float,
    sca_sin_ratio: float,
) -> int:
    if policy_mode_id == _POLICY_MODE_RANDOM_FAMILY_50_50:
        if np.random.uniform(0.0, 1.0) < 0.5:
            return 0 if np.random.uniform(0.0, 1.0) < sma_global_ratio else 1
        return 2 if np.random.uniform(0.0, 1.0) < sca_sin_ratio else 3

    r = np.random.uniform(0.0, 1.0)
    if r < 0.9:
        return int(best_method[i])
    bm = int(best_method[i])
    k = 0
    small = np.empty(3, dtype=np.int64)
    for a in range(4):
        if a != bm:
            small[k] = a
            k += 1
    return int(np.random.choice(small))


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
        if np.random.uniform(0.0, 1.0) < 0.5:
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
    iter_idx: int,
    max_iter: int,
    pop_size: int,
    items: int,
    pool: np.ndarray,
    vb: np.ndarray,
    vc: np.ndarray,
    ctf_id: int,
) -> None:
    mf = float(max_iter)
    a = np.arctanh(-1.0 * ((iter_idx + 1) / mf) + 1.0)
    b = 1.0 - (iter_idx + 1) / mf
    p = np.tanh(abs(pop_fit[row] - gbest_fit))
    # 與 ``BSMA_numba`` / ``BRLSMASCATestCore.sma_local`` 相同：一次取向量 uniform
    vb[:] = np.random.uniform(-a, a, items)
    vc[:] = np.random.uniform(-b, b, items)
    # 與 ``BSMA_numba`` 相同：每個物品維度內重填 ``pool`` 再 ``choice``（不消耗額外 RNG，但與 njit 編譯路徑一致）
    for j in range(items):
        r = np.random.random()
        k = 0
        for kk in range(pop_size):
            if kk != row:
                pool[k] = kk
                k += 1
        pair = np.random.choice(pool[: pop_size - 1], 2, replace=False)
        a_idx = int(pair[0])
        b_idx = int(pair[1])
        if r < p:
            pop_sol[row, j] = gbest_sol[j] + vb[j] * (
                W[row, j] * pop_sol[a_idx, j] - pop_sol[b_idx, j]
            )
        else:
            pop_sol[row, j] = vc[j] * pop_sol[row, j]
        if np.random.uniform(0.0, 1.0) < ctf_flip_probability(ctf_id, pop_sol[row, j]):
            pop_sol[row, j] = 1.0
        else:
            pop_sol[row, j] = 0.0


@njit(cache=True)
def _sca_sin_row(
    pop_sol: np.ndarray,
    individual_best_sol: np.ndarray,
    row: int,
    gbest_sol: np.ndarray,
    r1: float,
    items: int,
    ctf_id: int,
) -> None:
    for j in range(items):
        r2 = math.pi * np.random.uniform(0.0, 2.0)
        r3 = np.random.uniform(0.0, 2.0)
        pop_sol[row, j] = individual_best_sol[row, j] + (
            r1 * math.sin(r2) * abs(r3 * gbest_sol[j] - individual_best_sol[row, j])
        )
        if np.random.uniform(0.0, 1.0) < ctf_flip_probability(ctf_id, pop_sol[row, j]):
            pop_sol[row, j] = 1.0
        else:
            pop_sol[row, j] = 0.0


@njit(cache=True)
def _sca_cos_row(
    pop_sol: np.ndarray,
    individual_best_sol: np.ndarray,
    row: int,
    gbest_sol: np.ndarray,
    r1: float,
    items: int,
    ctf_id: int,
) -> None:
    for j in range(items):
        r2 = math.pi * np.random.uniform(0.0, 2.0)
        r3 = np.random.uniform(0.0, 2.0)
        pop_sol[row, j] = individual_best_sol[row, j] + (
            r1 * math.cos(r2) * abs(r3 * gbest_sol[j] - individual_best_sol[row, j])
        )
        if np.random.uniform(0.0, 1.0) < ctf_flip_probability(ctf_id, pop_sol[row, j]):
            pop_sol[row, j] = 1.0
        else:
            pop_sol[row, j] = 0.0


@njit(cache=True)
def _bscasma_main_loop_numba(
    pop_sol: np.ndarray,
    pop_fit: np.ndarray,
    individual_best_sol: np.ndarray,
    individual_best_fit: np.ndarray,
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
    tmp_ibs: np.ndarray,
    tmp_ibf: np.ndarray,
    idx_work: np.ndarray,
    acc_res: np.ndarray,
    gbest_sol: np.ndarray,
    pool: np.ndarray,
    vb: np.ndarray,
    vc: np.ndarray,
    ctf_id: int,
    policy_mode_id: int,
    sma_global_ratio: float,
    sca_sin_ratio: float,
) -> float:
    np.random.seed(rng_seed)
    gbest_fit = pop_fit[0]
    for j in range(items):
        gbest_sol[j] = pop_sol[0, j]

    mf = float(max_iter)
    for iter_idx in range(max_iter):
        _update_sma_weight_inplace(W, pop_fit, pop_size, items)
        r1 = a - a * (float(iter_idx) / mf)

        for i in range(pop_size):
            action = _policy_action(best_method, i, policy_mode_id, sma_global_ratio, sca_sin_ratio)

            if action == 0:
                _sma_global_row(pop_sol, i, weights, capacities, cp_list, acc_res, items, dim)
                exe_time[i, 0] += 1
            elif action == 1:
                _sma_local_row(
                    pop_sol,
                    pop_fit,
                    i,
                    gbest_fit,
                    gbest_sol,
                    W,
                    iter_idx,
                    max_iter,
                    pop_size,
                    items,
                    pool,
                    vb,
                    vc,
                    ctf_id,
                )
                exe_time[i, 1] += 1
            elif action == 2:
                _sca_sin_row(pop_sol, individual_best_sol, i, gbest_sol, r1, items, ctf_id)
                exe_time[i, 2] += 1
            elif action == 3:
                _sca_cos_row(pop_sol, individual_best_sol, i, gbest_sol, r1, items, ctf_id)
                exe_time[i, 3] += 1

            pop_fit[i] = _fitness_row_bsca(pop_sol, i, values, items)
            _repair_bsca_row_inplace(
                pop_sol, i, pop_fit, values, weights, capacities, cp_list, acc_res, items, dim
            )

            _sort_bscasma_desc_deterministic_inplace(
                pop_sol,
                pop_fit,
                individual_best_sol,
                individual_best_fit,
                tmp_sol,
                tmp_fit,
                tmp_ibs,
                tmp_ibf,
                idx_work,
                pop_size,
                items,
            )

            if pop_fit[i] > individual_best_fit[i]:
                for j in range(items):
                    individual_best_sol[i, j] = pop_sol[0, j]
                individual_best_fit[i] = pop_fit[0]
                best_method[i] = action

            if pop_fit[0] > gbest_fit:
                gbest_fit = pop_fit[0]
                for j in range(items):
                    gbest_sol[j] = pop_sol[0, j]

            if gbest_fit == float(glbal_best):
                return gbest_fit

    return gbest_fit


class BRLSMASCATestNumbaCore:
    """與 ``BRLSMASCATestCore`` 相同前置；主迭代交給 Numba。"""

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
        prob_arr: tuple[float, ...] | list[float] = (0.04, 0.46, 0.25, 0.25),
        ctf_id: int = 0,
        policy_mode_id: int = _POLICY_MODE_RL_BEST_METHOD,
        sma_global_ratio: float = 0.5,
        sca_sin_ratio: float = 0.5,
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
        if not (0.0 < z <= 1.0):
            raise ValueError("z must satisfy 0 < z <= 1")

        self.ctf_id = int(ctf_id)
        self.policy_mode_id = int(policy_mode_id)
        self.sma_global_ratio = float(sma_global_ratio)
        self.sca_sin_ratio = float(sca_sin_ratio)

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

        self.Gbest_sol: np.ndarray | None = None
        self.Gbest_fit: int | None = None
        self.initial_pop()

        self._prob_arr_template = tuple(float(x) for x in prob_arr)
        self.prob_arr = np.array(list(self._prob_arr_template) * self.pop_size)
        self.exe_time = np.zeros([self.pop_size, 4], dtype=int)
        self.best_method = self.init_best_method()

    def init_best_method(self) -> np.ndarray:
        probabilities = list(self._prob_arr_template)
        elements = [0, 1, 2, 3]
        random_selection = np.random.choice(elements, size=self.pop_size, p=probabilities)
        return np.asarray(random_selection, dtype=np.int64)

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
        x = (-np.asarray(pseudo_utilities, dtype=np.float64)).ravel()
        return np.ascontiguousarray(np.argsort(x, kind="stable").astype(np.int64))

    def initial_pop(self) -> None:
        self.pop_sol = np.zeros([self.pop_size, self.items])
        for i in range(self.pop_size):
            accumulated_resources = np.zeros([self.dim])
            for j in self.cp_list:
                if np.random.uniform(0.0, 1.0) < 0.5:
                    accumulated_resources += self.weights[j]
                    if np.all(accumulated_resources <= self.capacities):
                        self.pop_sol[i, j] = 1

            self.pop_fit[i] = np.sum(np.multiply(self.values, self.pop_sol[i]))

            self.individual_best_sol[i] = self.pop_sol[i]
            self.individual_best_fit[i] = self.pop_fit[i]

    def sort_pop(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        pop_sol = np.zeros([self.pop_size, self.items])
        pop_fit = np.zeros([self.pop_size], dtype=int)
        sorted_indices = _argsort_pop_fit_desc_deterministic(self.pop_fit, self.pop_size)

        individual_best_sol = np.zeros([self.pop_size, self.items])
        individual_best_fit = np.zeros([self.pop_size], dtype=int)

        for i in range(self.pop_size):
            pop_sol[i] = self.pop_sol[sorted_indices[i]]
            pop_fit[i] = self.pop_fit[sorted_indices[i]]

            individual_best_sol[i] = self.individual_best_sol[sorted_indices[i]]
            individual_best_fit[i] = self.individual_best_fit[sorted_indices[i]]

        return pop_sol, pop_fit, individual_best_sol, individual_best_fit

    def run(self) -> tuple[np.ndarray, int]:
        np.random.seed(self.seed)

        self.pop_sol, self.pop_fit, self.individual_best_sol, self.individual_best_fit = self.sort_pop()

        pop_sol = np.ascontiguousarray(self.pop_sol, dtype=np.float64)
        pop_fit = np.ascontiguousarray(self.pop_fit, dtype=np.float64)
        individual_best_sol = np.ascontiguousarray(self.individual_best_sol, dtype=np.float64)
        individual_best_fit = np.ascontiguousarray(self.individual_best_fit, dtype=np.float64)
        best_method = np.ascontiguousarray(self.best_method.astype(np.int64))
        exe_time = np.ascontiguousarray(self.exe_time.astype(np.int64))

        values = self.values
        weights = self.weights
        capacities = self.capacities
        cp_list = self.cp_list

        ps, it, dm = self.pop_size, self.items, self.dim
        W = np.zeros((ps, it), dtype=np.float64)
        tmp_sol = np.zeros((ps, it), dtype=np.float64)
        tmp_fit = np.zeros(ps, dtype=np.float64)
        tmp_ibs = np.zeros((ps, it), dtype=np.float64)
        tmp_ibf = np.zeros(ps, dtype=np.float64)
        idx_work = np.empty(ps, dtype=np.int64)
        acc_res = np.zeros(dm, dtype=np.float64)
        gbest_sol = np.empty(it, dtype=np.float64)
        pool = np.empty(max(1, ps - 1), dtype=np.int64)
        vb = np.empty(it, dtype=np.float64)
        vc = np.empty(it, dtype=np.float64)
        rng_seed = int(self.seed) if self.seed is not None else 0

        gfit = _bscasma_main_loop_numba(
            pop_sol,
            pop_fit,
            individual_best_sol,
            individual_best_fit,
            best_method,
            exe_time,
            values,
            weights,
            capacities,
            cp_list,
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
            tmp_ibs,
            tmp_ibf,
            idx_work,
            acc_res,
            gbest_sol,
            pool,
            vb,
            vc,
            self.ctf_id,
            self.policy_mode_id,
            self.sma_global_ratio,
            self.sca_sin_ratio,
        )

        self.exe_time = np.asarray(exe_time)
        self.best_method = np.asarray(best_method)

        out = np.empty(it, dtype=np.int64)
        for j in range(it):
            out[j] = 1 if gbest_sol[j] >= 0.5 else 0
        return out, int(gfit)


@dataclass
class BRLSMASCATestNumbaSolver:
    """BRLSMASCA Numba 變體；solver_id 預設 ``brlsmasca_numba``。"""

    def solve(self, problem: ProblemModel, config: dict[str, Any], rng: np.random.Generator) -> SolveResult:
        stop_condition = config.get("stop_condition", {})
        if stop_condition.get("type") != "max_iterations":
            raise ValueError("brlsmasca_numba only supports stop_condition.type=max_iterations")

        max_iterations = int(stop_condition.get("max_iterations", 0))
        if max_iterations <= 0:
            raise ValueError("max_iterations must be > 0")

        raw_params = config.get("params", {})
        if not isinstance(raw_params, dict):
            raise ValueError("params must be a mapping when present")
        pop_size = int(raw_params.get("pop_size", 20))
        a = float(raw_params.get("a", 2))
        z = float(raw_params.get("z", 0.03))
        prob_arr_raw = raw_params.get("prob_arr", [0.04, 0.46, 0.25, 0.25])
        if not isinstance(prob_arr_raw, (list, tuple)) or len(prob_arr_raw) != 4:
            raise ValueError(
                "params.prob_arr must be a list/tuple of length 4 (probabilities for sma_global / sma_local / sca_sin / sca_cos)"
            )
        prob_arr = tuple(float(x) for x in prob_arr_raw)
        if any(x < 0 for x in prob_arr) or abs(sum(prob_arr) - 1.0) > 1e-9:
            raise ValueError("params.prob_arr must be non-negative and sum to 1.0")
        policy_mode_raw = raw_params.get("policy_mode", "rl_best_method")
        policy_mode_id, sma_global_ratio, sca_sin_ratio = _policy_mode_settings(policy_mode_raw, prob_arr)

        if pop_size <= 0:
            raise ValueError("params.pop_size must be > 0")
        if a <= 0:
            raise ValueError("params.a must be > 0")
        if not (0.0 < z <= 1.0):
            raise ValueError("params.z must satisfy 0 < z <= 1")

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
            z=z,
            max_iter=int(max_iterations),
            prob_arr=prob_arr,
            ctf_id=ctf_id,
            policy_mode_id=policy_mode_id,
            sma_global_ratio=sma_global_ratio,
            sca_sin_ratio=sca_sin_ratio,
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
            solver_id=str(config.get("solver_id", "brlsmasca_numba")),
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
                "policy_mode": str(policy_mode_raw),
            },
        )


def _policy_mode_settings(
    policy_mode: Any,
    prob_arr: tuple[float, float, float, float],
) -> tuple[int, float, float]:
    if not isinstance(policy_mode, str):
        raise ValueError("params.policy_mode must be a string when present")
    parsed = policy_mode.strip()
    if parsed not in _POLICY_MODE_IDS:
        legal = ", ".join(sorted(_POLICY_MODE_IDS))
        raise ValueError(f"params.policy_mode must be one of: {legal}")

    if parsed == "rl_best_method":
        return (_POLICY_MODE_IDS[parsed], 0.5, 0.5)

    sma_total = float(prob_arr[0] + prob_arr[1])
    sca_total = float(prob_arr[2] + prob_arr[3])
    if sma_total <= 0.0 or sca_total <= 0.0:
        raise ValueError(
            "params.prob_arr must allocate positive probability to both SMA and SCA families "
            "when policy_mode=random_family_50_50"
        )
    return (
        _POLICY_MODE_IDS[parsed],
        float(prob_arr[0] / sma_total),
        float(prob_arr[2] / sca_total),
    )
