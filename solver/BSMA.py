from __future__ import annotations

import copy as copy
import hashlib
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.optimize import linprog

from ..engine.models import SolveResult
from ..problem import ProblemModel
from ..tools.continuous_to_binary import flip_probability, parse_ctf_kind

# 這邊要改成 可以提交狀態(SolveResult.addAct(狀態, 編碼, extend))、對外暴露過程(extend 物件)


# 摘要化浮點數陣列
def _digest_float_prefix(vec: np.ndarray, count: int = 8) -> str:
    flat = np.asarray(vec, dtype=np.float64).ravel()[:count]
    return hashlib.sha256(flat.tobytes()).hexdigest()[:16]


def _argsort_pop_fit_desc_deterministic(pop_fit: np.ndarray, pop_size: int) -> np.ndarray:
    """回傳長度 ``pop_size`` 的列索引：依 ``pop_fit`` **非遞增**；同適配值時**列索引較小者在前**。

    用於取代 ``np.argsort(pop_fit)[::-1]``：NumPy 預設 ``argsort`` 在同值時的相對順序未定義，
    且與 Numba 內建 ``argsort`` 可能不一致。``BSMA_numba`` 主迴圈排序須與此函式邏輯相同（njit 複製）。"""
    idx = np.arange(pop_size, dtype=np.int64)
    for i in range(pop_size):
        bi = i
        for j in range(i + 1, pop_size):
            ia = int(idx[j])
            ib = int(idx[bi])
            fa = float(pop_fit[ia])
            fb = float(pop_fit[ib])
            if fa > fb or (fa == fb and ia < ib):
                bi = j
        idx[i], idx[bi] = idx[bi], idx[i]
    return idx


class BSMACore:
    """與 old/BSMA.py::BSMA 相同邏輯（不 import old，供驗證與除錯對照）。"""

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
        ctf_kind: str = "tanh_abs",
    ) -> None:
        self.items = items
        self.dim = dim
        self.glbal_best = glbal_best
        self.values = values
        self.weights = weights
        self.capacities = capacities
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
        self.ctf_kind = str(ctf_kind)
        self.cp_list = self.pseudo_utility()
        self.z = float(z)
        self.W = np.zeros([self.pop_size, self.items])

        self.pop_fit = np.zeros([self.pop_size], dtype=int)
        self.pop_sol = self.initial_pop()
        self.Gbest_sol = copy.deepcopy(self.pop_sol[0])
        self.Gbest_fit = copy.deepcopy(self.pop_fit[0])
        # 除錯用：每個外層迭代一筆摘要（p / vb / vc / W）；預設 None 不影響行為
        self._loop_trace: list[dict[str, Any]] | None = None

        # 狀態緩存
        # 鬆弛變數狀態緩存
        # 初始解


    # 評估效用值
    def pseudo_utility(self) -> np.ndarray:
        constraints = np.concatenate((self.capacities, np.ones(self.items)))
        i_weight = -np.concatenate((self.weights, np.eye(self.items)), axis=1)
        i_profit = self.values * -1
        t_lp0 = time.perf_counter()
        result = linprog(constraints, i_weight, i_profit)
        self.linprog_runtime = time.perf_counter() - t_lp0
        shadow_price = result.x[: len(self.capacities)]
        denom = np.matmul(shadow_price.T, self.weights.T)
        # linprog 退化時分母可能為 0（舊 BSMA 同一公式）；除法仍產生 inf/nan，僅抑制已知 RuntimeWarning
        with np.errstate(divide="ignore", invalid="ignore"):
            pseudo_utilities = (-i_profit).T / denom
        return np.ascontiguousarray((-pseudo_utilities).argsort().astype(np.int64))

    # 初始化種群
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

    # 修復操作
    def repair(self, trial_sol: np.ndarray, trial_fit: int) -> tuple[np.ndarray, int]:
        resource_consumption = np.sum(np.multiply(self.weights.T, trial_sol), axis=1)
        for i in np.flip(self.cp_list):
            if np.any(resource_consumption > self.capacities):
                if trial_sol[i] == 1:
                    trial_sol[i] = 0
                    resource_consumption -= self.weights[i]
                    trial_fit -= self.values[i]
            else:
                break

        for i in self.cp_list:
            if trial_sol[i] == 0:
                if np.all(resource_consumption + self.weights[i] <= self.capacities):
                    trial_sol[i] = 1
                    resource_consumption += self.weights[i]
                    trial_fit += self.values[i]
                else:
                    break
        return trial_sol, trial_fit

    # 排序操作
    def sort_pop(self) -> tuple[np.ndarray, np.ndarray]:
        pop_sol = np.zeros([self.pop_size, self.items])
        pop_fit = np.zeros([self.pop_size])
        sorted_indices = _argsort_pop_fit_desc_deterministic(self.pop_fit, self.pop_size)
        for i in range(self.pop_size):
            pop_sol[i] = self.pop_sol[sorted_indices[i]]
            pop_fit[i] = self.pop_fit[sorted_indices[i]]
        return pop_sol, pop_fit

    # 執行求解
    def run(self) -> tuple[np.ndarray, int]:
        np.random.seed(self.seed)

        self.pop_sol, self.pop_fit = self.sort_pop()
        # 須與改進分支一致使用 ``deepcopy``：若與 ``pop_sol[0]`` 共用視圖，則在 ``i == 0`` 局部搜尋內層
        # ``j`` 迴圈中 ``Gbest_sol[j]`` 會隨 ``pop_sol[0, j]`` 即時變動，與 Numba 版（獨立 ``gbest_sol`` 緩衝）無法對齊。
        self.Gbest_sol = copy.deepcopy(self.pop_sol[0])
        self.Gbest_fit = copy.deepcopy(self.pop_fit[0])

        for iter in range(self.max_iter):
            self.W = np.zeros([self.pop_size, self.items])
            worst_fit = self.pop_fit[-1]
            best_fit = self.pop_fit[0]
            s_val = best_fit - worst_fit if best_fit - worst_fit > 0 else 0.0001
            for i in range(self.pop_size):
                if i < self.pop_size / 2:
                    self.W[i, :] = 1 + np.random.random([self.items]) * np.log10((best_fit - self.pop_fit[i]) / (s_val) + 1)
                else:
                    self.W[i, :] = 1 - np.random.random([self.items]) * np.log10((best_fit - self.pop_fit[i]) / (s_val) + 1)

            a = np.arctanh(-1 * ((iter + 1) / self.max_iter) + 1)
            b = 1 - (iter + 1) / self.max_iter

            loop_snap: dict[str, Any] | None = None
            if self._loop_trace is not None:
                loop_snap = {
                    "iter": int(iter),
                    "a": float(a),
                    "b": float(b),
                    "W0_digest": _digest_float_prefix(self.W[0]),
                }

            for i in range(self.pop_size):
                if np.random.random() < self.z:
                    self.pop_sol[i] = np.zeros(self.items)
                    accumulated_resources = np.zeros([self.dim])
                    for j in self.cp_list:
                        if np.random.uniform(0.0, 1.0) < 0.5:
                            accumulated_resources += self.weights[j]
                            if np.all(accumulated_resources <= self.capacities):
                                self.pop_sol[i, j] = 1
                    if loop_snap is not None and i == 0:
                        loop_snap["branch_i0"] = "z_global"
                else:
                    p = np.tanh(abs(self.pop_fit[i] - self.Gbest_fit))
                    vb = np.random.uniform(-a, a, self.items)
                    vc = np.random.uniform(-b, b, self.items)
                    if loop_snap is not None and i == 0:
                        loop_snap["branch_i0"] = "local"
                        loop_snap["p_i0"] = float(p)
                        loop_snap["vb0_digest"] = _digest_float_prefix(vb)
                        loop_snap["vc0_digest"] = _digest_float_prefix(vc)
                    # 局部搜索
                    for j in range(self.items):
                        r = np.random.random()
                        a_idx, b_idx = np.random.choice(list(set(range(0, self.pop_size)) - {i}), 2, replace=False)
                        if r < p:
                            self.pop_sol[i, j] = self.Gbest_sol[j] + vb[j] * (
                                self.W[i, j] * self.pop_sol[a_idx, j] - self.pop_sol[b_idx, j]
                            )
                        else:
                            self.pop_sol[i, j] = vc[j] * self.pop_sol[i, j]
                        if np.random.uniform(0.0, 1.0) < flip_probability(
                            float(self.pop_sol[i, j]), self.ctf_kind
                        ):
                            self.pop_sol[i, j] = 1
                        else:
                            self.pop_sol[i, j] = 0

                self.pop_fit[i] = np.sum(np.multiply(self.values, self.pop_sol[i]))
                self.pop_sol[i], self.pop_fit[i] = self.repair(self.pop_sol[i], self.pop_fit[i])

            self.pop_sol, self.pop_fit = self.sort_pop()
            if self._loop_trace is not None and loop_snap is not None:
                loop_snap["best_after_sort"] = int(self.pop_fit[0])
                self._loop_trace.append(loop_snap)
            if self.pop_fit[0] > self.Gbest_fit:
                self.Gbest_sol = copy.deepcopy(self.pop_sol[0])
                self.Gbest_fit = copy.deepcopy(self.pop_fit[0])
            if self.Gbest_fit == self.glbal_best:
                return self.Gbest_sol, self.Gbest_fit
        return self.Gbest_sol, self.Gbest_fit


@dataclass
class BSMASolver:
    """BSMA：內建與 old/BSMA 相同演算法本體（BSMACore），不使用 import old。"""

    def solve(self, problem: ProblemModel, config: dict[str, Any], rng: np.random.Generator) -> SolveResult:
        stop_condition = config.get("stop_condition", {})
        if stop_condition.get("type") != "max_iterations":
            raise ValueError("bsma only supports stop_condition.type=max_iterations")

        max_iterations = int(stop_condition.get("max_iterations", 0))
        if max_iterations <= 0:
            raise ValueError("max_iterations must be > 0")

        raw_params = config.get("params", {})
        if not isinstance(raw_params, dict):
            raise ValueError("params must be a mapping when present")
        pop_size = int(raw_params.get("pop_size", 20))
        z = float(raw_params.get("z", 0.08))
        ctf_kind, _ = parse_ctf_kind(raw_params)
        if pop_size <= 0:
            raise ValueError("params.pop_size must be > 0")
        if not (0.0 < z <= 1.0):
            raise ValueError("params.z must satisfy 0 < z <= 1")

        run_seed = int(config.get("run_seed", rng.integers(0, np.iinfo(np.int32).max)))

        # 與舊版一致：在建立族群前即固定 numpy 全域亂數（對照驗證時亦先 seed 再 __init__）
        np.random.seed(run_seed)

        t_alg0 = time.perf_counter()
        core = BSMACore(
            problem.items,                             # 物品數量
            problem.dim,                               # 限制維度數量
            problem.best_known,                        # 最佳已知解
            problem.values,
            problem.weights,
            problem.capacities,
            seed=run_seed,
            pop_size=pop_size,
            z=z,
            max_iter=int(max_iterations),
            ctf_kind=ctf_kind,
        )
        best_sol, best_fit = core.run() # 執行求解
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
            solver_id=str(config.get("solver_id", "bsma")),
            run_seed=run_seed,
            best_solution=np.asarray(best_sol, dtype=int),
            best_objective=int(best_fit),
            feasible=True,
            evaluation_count=evaluation_count,
            stop_reason=stop_reason,
            runtime=algorithm_runtime,
            linprog_runtime=float(core.linprog_runtime),
            error=None,
            metadata={"linprog_runtime": float(core.linprog_runtime)},
        )
