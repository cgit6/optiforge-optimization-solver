from __future__ import annotations

import copy as copy
import math
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.optimize import linprog

from ..engine.models import ProblemModel, SolveResult
from ..tools.continuous_to_binary import flip_probability, parse_ctf_kind
from .BSMA import _argsort_pop_fit_desc_deterministic


class BSCA2V120Core:
    """與 old/BSCA1.py::BSCA2_V1_20 相同邏輯（不 import old，供驗證與除錯對照）。"""

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
        if a <= 0:
            raise ValueError("a must be > 0")

        self.pop_size = int(pop_size)
        self.max_iter = int(max_iter)
        self.ctf_kind = str(ctf_kind)
        self.cp_list = self.pseudo_utility()

        # SCA 振幅參數，舊版 BSCA2_V1_20 預設 2.0
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
        self.Gbest_sol = copy.deepcopy(self.pop_sol[0])
        self.Gbest_fit = copy.deepcopy(self.pop_fit[0])

        for iter in range(self.max_iter):
            for i in range(self.pop_size):
                r1 = self.a - self.a * (iter / self.max_iter)

                for j in range(self.items):
                    r2 = math.pi * np.random.uniform(0.0, 2.0)
                    r3 = np.random.uniform(0.0, 2.0)
                    r4 = np.random.uniform(0.0, 1.0)

                    # 維持 BSCA2_V1_20 原本 abs/括號位置：abs(r1*sin(r2)) * r3 * Gbest - sol
                    if r4 < 0.5:
                        self.pop_sol[i, j] = self.pop_sol[i, j] + (
                            abs(r1 * math.sin(r2)) * r3 * self.Gbest_sol[j] - self.pop_sol[i, j]
                        )
                    else:
                        self.pop_sol[i, j] = self.pop_sol[i, j] + (
                            abs(r1 * math.cos(r2)) * r3 * self.Gbest_sol[j] - self.pop_sol[i, j]
                        )

                    if np.random.uniform(0.0, 1.0) < flip_probability(
                        float(self.pop_sol[i, j]), self.ctf_kind
                    ):
                        self.pop_sol[i, j] = 1
                    else:
                        self.pop_sol[i, j] = 0

                self.pop_fit[i] = np.sum(np.multiply(self.values, self.pop_sol[i]))
                self.pop_sol[i], self.pop_fit[i] = self.repair(self.pop_sol[i], self.pop_fit[i])
                self.pop_sol, self.pop_fit = self.sort_pop()

                if self.pop_fit[0] > self.Gbest_fit:
                    self.Gbest_sol = copy.deepcopy(self.pop_sol[0])
                    self.Gbest_fit = copy.deepcopy(self.pop_fit[0])

                if self.Gbest_fit == self.glbal_best:
                    return self.Gbest_sol, self.Gbest_fit

        return self.Gbest_sol, self.Gbest_fit


@dataclass
class BSCA2V120Solver:
    """BSCA2 V1.20：內建與 old/BSCA1::BSCA2_V1_20 相同演算法本體（BSCA2V120Core），不使用 import old。"""

    def solve(self, problem: ProblemModel, config: dict[str, Any], rng: np.random.Generator) -> SolveResult:
        stop_condition = config.get("stop_condition", {})
        if stop_condition.get("type") != "max_iterations":
            raise ValueError("bsca2_v1_20 only supports stop_condition.type=max_iterations")

        max_iterations = int(stop_condition.get("max_iterations", 0))
        if max_iterations <= 0:
            raise ValueError("max_iterations must be > 0")

        raw_params = config.get("params", {})
        if not isinstance(raw_params, dict):
            raise ValueError("params must be a mapping when present")
        pop_size = int(raw_params.get("pop_size", 20))
        a = float(raw_params.get("a", 2.0))
        ctf_kind, _ = parse_ctf_kind(raw_params)
        if pop_size <= 0:
            raise ValueError("params.pop_size must be > 0")
        if a <= 0:
            raise ValueError("params.a must be > 0")

        run_seed = int(config.get("run_seed", rng.integers(0, np.iinfo(np.int32).max)))

        np.random.seed(run_seed)

        t_alg0 = time.perf_counter()
        core = BSCA2V120Core(
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
            ctf_kind=ctf_kind,
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
            solver_id=str(config.get("solver_id", "bsca2_v1_20")),
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
