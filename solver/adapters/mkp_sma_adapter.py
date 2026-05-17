from __future__ import annotations

import time

import numpy as np
from scipy.optimize import linprog

from ...problem import MKPProblem


class MKPSMAAdapter:
    direction = "max"

    def __init__(self, problem: MKPProblem) -> None:
        self.problem = problem
        self.dim_position = problem.items
        self.linprog_runtime = 0.0
        self.cp_list = self._pseudo_utility()

    def _pseudo_utility(self) -> np.ndarray:
        constraints = np.concatenate((self.problem.capacities, np.ones(self.problem.items)))
        i_weight = -np.concatenate((self.problem.weights, np.eye(self.problem.items)), axis=1)
        i_profit = self.problem.values * -1
        t_lp0 = time.perf_counter()
        result = linprog(constraints, i_weight, i_profit)
        self.linprog_runtime = time.perf_counter() - t_lp0
        shadow_price = result.x[: len(self.problem.capacities)]
        denom = np.matmul(shadow_price.T, self.problem.weights.T)
        with np.errstate(divide="ignore", invalid="ignore"):
            pseudo_utilities = (-i_profit).T / denom
        return (-pseudo_utilities).argsort()

    def initial_position(self, rng: np.random.Generator, pop_size: int) -> np.ndarray:
        population = np.zeros((pop_size, self.problem.items), dtype=float)
        for i in range(pop_size):
            accumulated = np.zeros(self.problem.dim)
            for j in self.cp_list:
                if rng.uniform(0.0, 1.0) < 0.5:
                    accumulated += self.problem.weights[j]
                    if np.all(accumulated <= self.problem.capacities):
                        population[i, j] = 1.0
        return population

    def random_position(self, rng: np.random.Generator) -> np.ndarray:
        return self.initial_position(rng, 1)[0]

    def normalize_position(self, position: np.ndarray, rng: np.random.Generator) -> np.ndarray:
        normalized = np.zeros(self.problem.items, dtype=float)
        probs = np.abs(np.tanh(position))
        normalized[rng.random(self.problem.items) < probs] = 1.0
        return normalized

    def decode_and_evaluate(self, position: np.ndarray) -> tuple[np.ndarray, int]:
        solution = np.asarray(position >= 0.5, dtype=int)
        fit = int(np.dot(self.problem.values, solution))
        repaired, repaired_fit = self._repair(solution, fit)
        return repaired, int(repaired_fit)

    def _repair(self, trial_sol: np.ndarray, trial_fit: int) -> tuple[np.ndarray, int]:
        resource_consumption = np.sum(np.multiply(self.problem.weights.T, trial_sol), axis=1)
        for i in np.flip(self.cp_list):
            if np.any(resource_consumption > self.problem.capacities):
                if trial_sol[i] == 1:
                    trial_sol[i] = 0
                    resource_consumption -= self.problem.weights[i]
                    trial_fit -= int(self.problem.values[i])
            else:
                break

        for i in self.cp_list:
            if trial_sol[i] == 0 and np.all(resource_consumption + self.problem.weights[i] <= self.problem.capacities):
                trial_sol[i] = 1
                resource_consumption += self.problem.weights[i]
                trial_fit += int(self.problem.values[i])
        return trial_sol, trial_fit

    def early_stop(self, objective: int | float) -> bool:
        return objective >= int(self.problem.best_known)
