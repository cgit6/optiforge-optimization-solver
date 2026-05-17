from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import numpy as np

from ..engine.models import SolveResult
from ..problem import TSPProblem


@dataclass
class NearestNeighborTSPSolver:
    def solve(self, problem: TSPProblem, config: dict[str, Any], rng: np.random.Generator) -> SolveResult:
        if not isinstance(problem, TSPProblem):
            raise TypeError("nn_tsp_v1 only supports TSPProblem")
        t0 = time.perf_counter()
        start = int(config.get("params", {}).get("start_city", 0))
        unvisited = set(range(problem.n_cities))
        tour = [start]
        unvisited.remove(start)
        while unvisited:
            current = tour[-1]
            next_city = min(unvisited, key=lambda city: (int(problem.distance_matrix[current, city]), city))
            tour.append(next_city)
            unvisited.remove(next_city)
        tour_arr = np.asarray(tour, dtype=int)
        cost = int(
            sum(
                int(problem.distance_matrix[tour_arr[i], tour_arr[(i + 1) % problem.n_cities]])
                for i in range(problem.n_cities)
            )
        )
        stop_reason = (
            "best_known_reached"
            if problem.best_known is not None and float(cost) <= float(problem.best_known)
            else "nearest_neighbor_completed"
        )
        return SolveResult(
            problem_id=problem.problem_id,
            solver_id=str(config.get("solver_id", "nn_tsp_v1")),
            seed=int(config.get("run_seed", 0)),
            best_solution=tour_arr,
            best_objective=cost,
            feasible=True,
            evaluation_count=problem.n_cities,
            stop_reason=stop_reason,
            runtime=time.perf_counter() - t0,
            error=None,
            metadata={"start_city": start},
        )
