from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from ..engine.models import Direction


class SMAAdapter(Protocol):
    direction: Direction
    dim_position: int

    def initial_position(self, rng: np.random.Generator, pop_size: int) -> np.ndarray: ...
    def random_position(self, rng: np.random.Generator) -> np.ndarray: ...
    def normalize_position(self, position: np.ndarray, rng: np.random.Generator) -> np.ndarray: ...
    def decode_and_evaluate(self, position: np.ndarray) -> tuple[np.ndarray, int | float]: ...
    def early_stop(self, objective: int | float) -> bool: ...


@dataclass(frozen=True)
class SMACore:
    dim_position: int
    pop_size: int
    max_iter: int
    z: float

    def run(self, adapter: SMAAdapter, rng: np.random.Generator) -> tuple[np.ndarray, int | float, dict[str, int]]:
        if self.pop_size <= 1:
            raise ValueError("pop_size must be > 1")
        if self.max_iter <= 0:
            raise ValueError("max_iter must be > 0")
        if not (0.0 < self.z <= 1.0):
            raise ValueError("z must satisfy 0 < z <= 1")

        positions = adapter.initial_position(rng, self.pop_size)
        decoded: list[np.ndarray] = []
        fitness = np.zeros(self.pop_size, dtype=float)
        for i in range(self.pop_size):
            solution, objective = adapter.decode_and_evaluate(positions[i])
            decoded.append(solution)
            fitness[i] = float(objective)

        evaluation_count = self.pop_size
        positions, fitness, decoded = self._sort(adapter.direction, positions, fitness, decoded)
        gbest_position = positions[0].copy()
        gbest_solution = decoded[0].copy()
        gbest_objective = fitness[0]

        for iteration in range(self.max_iter):
            worst_fit = fitness[-1]
            best_fit = fitness[0]
            spread = abs(best_fit - worst_fit) or 0.0001
            weights = np.zeros((self.pop_size, self.dim_position), dtype=float)
            for i in range(self.pop_size):
                sign = 1 if i < self.pop_size / 2 else -1
                weights[i, :] = 1 + sign * rng.random(self.dim_position) * np.log10(
                    abs(best_fit - fitness[i]) / spread + 1
                )

            a = np.arctanh(-1 * ((iteration + 1) / self.max_iter) + 1)
            b = 1 - (iteration + 1) / self.max_iter

            for i in range(self.pop_size):
                if rng.random() < self.z:
                    candidate = adapter.random_position(rng)
                else:
                    p = np.tanh(abs(fitness[i] - gbest_objective))
                    vb = rng.uniform(-a, a, self.dim_position)
                    vc = rng.uniform(-b, b, self.dim_position)
                    candidate = positions[i].copy()
                    others = [idx for idx in range(self.pop_size) if idx != i]
                    for j in range(self.dim_position):
                        a_idx, b_idx = rng.choice(others, 2, replace=False)
                        if rng.random() < p:
                            candidate[j] = gbest_position[j] + vb[j] * (
                                weights[i, j] * positions[a_idx, j] - positions[b_idx, j]
                            )
                        else:
                            candidate[j] = vc[j] * candidate[j]
                positions[i] = adapter.normalize_position(candidate, rng)
                solution, objective = adapter.decode_and_evaluate(positions[i])
                decoded[i] = solution
                fitness[i] = float(objective)
                evaluation_count += 1

            positions, fitness, decoded = self._sort(adapter.direction, positions, fitness, decoded)
            if self._is_better(adapter.direction, fitness[0], gbest_objective):
                gbest_position = positions[0].copy()
                gbest_solution = decoded[0].copy()
                gbest_objective = fitness[0]
            if adapter.early_stop(gbest_objective):
                break

        objective: int | float
        objective = int(gbest_objective) if float(gbest_objective).is_integer() else float(gbest_objective)
        return gbest_solution, objective, {"evaluation_count": evaluation_count}

    def _sort(
        self,
        direction: Direction,
        positions: np.ndarray,
        fitness: np.ndarray,
        decoded: list[np.ndarray],
    ) -> tuple[np.ndarray, np.ndarray, list[np.ndarray]]:
        order = np.argsort(fitness)
        if direction == "max":
            order = order[::-1]
        return positions[order], fitness[order], [decoded[int(i)] for i in order]

    def _is_better(self, direction: Direction, candidate: float, incumbent: float) -> bool:
        return candidate > incumbent if direction == "max" else candidate < incumbent
