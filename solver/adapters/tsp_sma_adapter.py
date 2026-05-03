from __future__ import annotations

import numpy as np

from ...engine.models import TSPProblem


class TSPSMAAdapter:
    direction = "min"

    def __init__(self, problem: TSPProblem) -> None:
        self.problem = problem
        self.dim_position = problem.n_cities

    def initial_position(self, rng: np.random.Generator, pop_size: int) -> np.ndarray:
        return rng.uniform(0.0, 1.0, (pop_size, self.problem.n_cities))

    def random_position(self, rng: np.random.Generator) -> np.ndarray:
        return rng.uniform(0.0, 1.0, self.problem.n_cities)

    def normalize_position(self, position: np.ndarray, rng: np.random.Generator) -> np.ndarray:
        return np.clip(position, 0.0, 1.0)

    def decode_and_evaluate(self, position: np.ndarray) -> tuple[np.ndarray, int]:
        tour = np.argsort(position).astype(int)
        cost = int(
            sum(
                int(self.problem.distance_matrix[tour[i], tour[(i + 1) % self.problem.n_cities]])
                for i in range(self.problem.n_cities)
            )
        )
        return tour, cost

    def early_stop(self, objective: int | float) -> bool:
        if self.problem.best_known is None:
            return False
        return float(objective) <= float(self.problem.best_known)
