from __future__ import annotations

import copy as copy
import math
import random
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.optimize import linprog

from ..engine.models import ProblemModel, SolveResult


class BRLSMASCA2V100320050TestCore:
    """與 old/BSCASMA.py::BRLSMASCA2_V1_003_20_050_test 相同邏輯（不 import old，供驗證與除錯對照）。

    Notes:
        - bit-identical 對齊：完整保留原版的 dead code 與「未使用屬性」（cp_list_old、prob_arr 80 長度、exe_time、update_prob、update_sma_weight 中對 S=0 未保護等），這些路徑不影響 RNG 流動但對照舊版。
        - 只移除原版 `if iter % 50 == 0: print(...)` 的執行期 print（與 BSMA 同樣處理，已驗證不影響 RNG 路徑）。
    """

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
        pop_size: int = 20,
        a: float = 2,
        z: float = 0.03,
        prob_arr: tuple[float, ...] | list[float] = (0.04, 0.46, 0.25, 0.25),
    ) -> None:
        self.items = items
        self.dim = dim
        self.glbal_best = glbal_best
        self.values = values
        self.weights = weights
        self.capacities = capacities
        self.seed = seed
        self.linprog_runtime = 0.0

        self.pop_size = int(pop_size)
        self.max_iter = 5000
        self.cp_list = self.pseudo_utility()
        self.cp_list_old = self.cp_list
        # 與 old _test 版一致：以 self.items * 0.15 為 std（舊版 dead code 保留）
        self.std = int(self.items * 0.15)

        # SMA 參數
        self.z = float(z)
        self.W = np.zeros([self.pop_size, self.items])
        self.b = None

        # SCA 參數
        self.a = float(a)
        self.p = 0.5
        self.r1: float | None = None

        # 算法變數
        self.pop_fit = np.zeros([self.pop_size], dtype=int)
        self.pop_fit_new = np.zeros([self.pop_size], dtype=int)
        self.pop_sol: np.ndarray | None = None

        # 個體最佳表現
        self.individual_best_sol = np.zeros([self.pop_size, self.items], dtype=int)
        self.individual_best_fit = np.zeros([self.pop_size], dtype=int)

        self.Gbest_sol: np.ndarray | None = None
        self.Gbest_fit: int | None = None
        self.initial_pop()

        # 強化學習參數（保留 80 長度 1D 陣列，與 old _test 版完全一致；非 RNG 影響因素）
        self._prob_arr_template = tuple(float(x) for x in prob_arr)
        self.prob_arr = np.array(list(self._prob_arr_template) * self.pop_size)
        self.exe_time = np.zeros([self.pop_size, 4], dtype=int)
        self.best_method = self.init_best_method()

    def init_best_method(self) -> np.ndarray:
        # 維持原版預設機率分布；prob_arr 是 self.prob_arr_template 但 init_best_method 在原版用 literal
        probabilities = list(self._prob_arr_template)
        elements = [0, 1, 2, 3]
        random_selection = np.random.choice(elements, size=self.pop_size, p=probabilities)
        return random_selection

    def pseudo_utility(self) -> np.ndarray:
        constraints = np.concatenate((self.capacities, np.ones(self.items)))
        i_weight = -np.concatenate((self.weights, np.eye(self.items)), axis=1)
        i_profit = self.values * -1
        t_lp0 = time.perf_counter()
        result = linprog(constraints, i_weight, i_profit)
        self.linprog_runtime = time.perf_counter() - t_lp0
        shadow_price = result.x[: len(self.capacities)]
        pseudo_utilities = (-i_profit).T / (np.matmul(shadow_price.T, self.weights.T))
        return (-pseudo_utilities).argsort()

    def initial_pop(self) -> None:
        self.pop_sol = np.zeros([self.pop_size, self.items])
        for i in range(self.pop_size):
            accumulated_resources = np.zeros([self.dim])
            for j in self.cp_list:
                if random.uniform(0, 1) < 0.5:
                    accumulated_resources += self.weights[j]
                    if np.all(accumulated_resources <= self.capacities):
                        self.pop_sol[i, j] = 1

            self.pop_fit[i] = np.sum(np.multiply(self.values, self.pop_sol[i]))

            self.individual_best_sol[i] = self.pop_sol[i]
            self.individual_best_fit[i] = self.pop_fit[i]

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
        return trial_sol, trial_fit

    def sort_pop(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        pop_sol = np.zeros([self.pop_size, self.items], dtype=int)
        pop_fit = np.zeros([self.pop_size], dtype=int)
        sorted_indices = np.argsort(self.pop_fit)[::-1]

        individual_best_sol = np.zeros([self.pop_size, self.items], dtype=int)
        individual_best_fit = np.zeros([self.pop_size], dtype=int)

        for i in range(self.pop_size):
            pop_sol[i] = self.pop_sol[sorted_indices[i]]
            pop_fit[i] = self.pop_fit[sorted_indices[i]]

            individual_best_sol[i] = self.individual_best_sol[sorted_indices[i]]
            individual_best_fit[i] = self.individual_best_fit[sorted_indices[i]]

        return pop_sol, pop_fit, individual_best_sol, individual_best_fit

    def policy(self, i: int) -> int:
        r = random.uniform(0, 1)
        if r < 0.9:
            action = self.best_method[i]
        else:
            array = [0, 1, 2, 3]
            filtered_array = [x for x in array if x != self.best_method[i]]
            action = random.choice(filtered_array)
        return int(action)

    def update_sma_weight(self) -> None:
        # 與舊版完全一致；S=0 時除以 0 行為亦保留（log10(0+1)=0，不會 NaN，但 fitness 全相等時實際上 S 會是 0）
        self.W = np.zeros([self.pop_size, self.items])
        worst_fit = self.pop_fit[-1]
        best_fit = self.pop_fit[0]
        S = best_fit - worst_fit

        for i in range(self.pop_size):
            if i < self.pop_size / 2:
                self.W[i, :] = 1 + np.random.random([self.items]) * np.log10((best_fit - self.pop_fit[i]) / (S) + 1)
            else:
                self.W[i, :] = 1 - np.random.random([self.items]) * np.log10((best_fit - self.pop_fit[i]) / (S) + 1)

    def sma_global(self, i: int) -> None:
        self.pop_sol[i] = np.zeros(self.items)
        accumulated_resources = np.zeros([self.dim])
        for j in self.cp_list:
            if random.uniform(0, 1) < 0.5:
                accumulated_resources += self.weights[j]
                if np.all(accumulated_resources <= self.capacities):
                    self.pop_sol[i, j] = 1

        self.exe_time[i, 0] += 1

    def sma_local(self, i: int, iter: int) -> None:
        a = np.arctanh(-1 * ((iter + 1) / self.max_iter) + 1)
        b = 1 - (iter + 1) / self.max_iter

        p = np.tanh(abs(self.pop_fit[i] - self.Gbest_fit))
        vb = np.random.uniform(-a, a, self.items)
        vc = np.random.uniform(-b, b, self.items)

        for j in range(self.items):
            r = np.random.random()
            a_idx, b_idx = np.random.choice(list(set(range(0, self.pop_size)) - {i}), 2, replace=False)
            if r < p:
                self.pop_sol[i, j] = self.Gbest_sol[j] + vb[j] * (
                    self.W[i, j] * self.pop_sol[a_idx, j] - self.pop_sol[b_idx, j]
                )
            else:
                self.pop_sol[i, j] = vc[j] * self.pop_sol[i, j]

            if random.uniform(0, 1) < np.abs(np.tanh(self.pop_sol[i, j])):
                self.pop_sol[i, j] = 1
            else:
                self.pop_sol[i, j] = 0

        self.exe_time[i, 1] += 1

    def sca_sin(self, i: int) -> None:
        for j in range(self.items):
            r2 = math.pi * random.uniform(0.0, 2.0)
            r3 = random.uniform(0.0, 2.0)

            self.pop_sol[i, j] = self.individual_best_sol[i, j] + (
                self.r1 * math.sin(r2) * abs(r3 * self.Gbest_sol[j] - self.individual_best_sol[i, j])
            )

            if random.uniform(0, 1) < np.abs(np.tanh(self.pop_sol[i, j])):
                self.pop_sol[i, j] = 1
            else:
                self.pop_sol[i, j] = 0

        self.exe_time[i, 2] += 1

    def sca_cos(self, i: int) -> None:
        for j in range(self.items):
            r2 = math.pi * random.uniform(0.0, 2.0)
            r3 = random.uniform(0.0, 2.0)

            self.pop_sol[i, j] = self.individual_best_sol[i, j] + (
                self.r1 * math.cos(r2) * abs(r3 * self.Gbest_sol[j] - self.individual_best_sol[i, j])
            )

            if random.uniform(0, 1) < np.abs(np.tanh(self.pop_sol[i, j])):
                self.pop_sol[i, j] = 1
            else:
                self.pop_sol[i, j] = 0

        self.exe_time[i, 3] += 1

    def update_prob(self, index: int, policy: int) -> None:
        # 與舊版一致的 dead code（run() 中未呼叫；引用未定義屬性 sma_exe/sca_exe）；保留以維持 fidelity
        self.pop_fit[index]
        self.sma_exe  # type: ignore[attr-defined]
        self.sca_exe  # type: ignore[attr-defined]

        step = 0.001  # noqa: F841 - 與舊版一致，保留未使用本機變數
        temp = (self.pop_fit_new[index] - self.pop_fit[index]) / self.pop_fit[index]

        if temp > 0:
            if policy == 0:
                self.prob_arr[index, 0] = min(self.prob_arr[index, 0] + temp, 1)
                self.prob_arr[index, 1] = 1 - self.prob_arr[index, 0]

            if policy == 1:
                self.prob_arr[index, 1] = min(self.prob_arr[index, 1] + temp, 1)
                self.prob_arr[index, 0] = 1 - self.prob_arr[index, 1]

    def run(self) -> tuple[np.ndarray, int]:
        random.seed(self.seed)
        np.random.seed(self.seed)

        self.pop_sol, self.pop_fit, self.individual_best_sol, self.individual_best_fit = self.sort_pop()
        self.Gbest_sol = copy.deepcopy(self.pop_sol[0])
        self.Gbest_fit = copy.deepcopy(self.pop_fit[0])

        for iter in range(self.max_iter):
            self.update_sma_weight()
            self.r1 = self.a - self.a * (iter / self.max_iter)

            for i in range(self.pop_size):
                action = self.policy(i)

                if action == 0:
                    self.sma_global(i)
                elif action == 1:
                    self.sma_local(i, iter)
                elif action == 2:
                    self.sca_sin(i)
                elif action == 3:
                    self.sca_cos(i)
                else:
                    # 與舊版一致：fallback 路徑（policy 範圍 0..3 不可能進來）
                    pass

                self.pop_fit[i] = np.sum(np.multiply(self.values, self.pop_sol[i]))
                self.pop_sol[i], self.pop_fit[i] = self.repair(self.pop_sol[i], self.pop_fit[i])
                (
                    self.pop_sol,
                    self.pop_fit,
                    self.individual_best_sol,
                    self.individual_best_fit,
                ) = self.sort_pop()

                if self.pop_fit[i] > self.individual_best_fit[i]:
                    self.individual_best_sol[i] = copy.deepcopy(self.pop_sol[0])
                    self.individual_best_fit[i] = copy.deepcopy(self.pop_fit[0])
                    self.best_method[i] = action

                if self.pop_fit[0] > self.Gbest_fit:
                    self.Gbest_sol = copy.deepcopy(self.pop_sol[0])
                    self.Gbest_fit = copy.deepcopy(self.pop_fit[0])

                if self.Gbest_fit == self.glbal_best:
                    return self.Gbest_sol, self.Gbest_fit

        return self.Gbest_sol, self.Gbest_fit


@dataclass
class BRLSMASCA2V100320050TestSolver:
    """BRLSMASCA2 v1.003 (test policy)：內建與 old/BSCASMA::BRLSMASCA2_V1_003_20_050_test 相同演算法本體。"""

    def solve(self, problem: ProblemModel, config: dict[str, Any], rng: np.random.Generator) -> SolveResult:
        stop_condition = config.get("stop_condition", {})
        if stop_condition.get("type") != "max_iterations":
            raise ValueError("brlsmasca2_v1_003_20_050_test only supports stop_condition.type=max_iterations")

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
            raise ValueError("params.prob_arr must be a list/tuple of length 4 (probabilities for sma_global / sma_local / sca_sin / sca_cos)")
        prob_arr = tuple(float(x) for x in prob_arr_raw)
        if any(x < 0 for x in prob_arr) or abs(sum(prob_arr) - 1.0) > 1e-9:
            raise ValueError("params.prob_arr must be non-negative and sum to 1.0")

        if pop_size <= 0:
            raise ValueError("params.pop_size must be > 0")
        if a <= 0:
            raise ValueError("params.a must be > 0")
        if not (0.0 < z <= 1.0):
            raise ValueError("params.z must satisfy 0 < z <= 1")

        run_seed = int(config.get("run_seed", rng.integers(0, np.iinfo(np.int32).max)))

        random.seed(run_seed)
        np.random.seed(run_seed)

        t_alg0 = time.perf_counter()
        core = BRLSMASCA2V100320050TestCore(
            problem.items,
            problem.dim,
            problem.best_known,
            np.asarray(problem.values, dtype=int),
            np.asarray(problem.weights, dtype=int),
            np.asarray(problem.capacities, dtype=int),
            seed=run_seed,
            pop_size=pop_size,
            a=a,
            z=z,
            prob_arr=prob_arr,
        )
        core.max_iter = int(max_iterations)
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
            solver_id=str(config.get("solver_id", "brlsmasca2_v1_003_20_050_test")),
            seed=run_seed,
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
