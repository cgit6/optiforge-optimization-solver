from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import numpy as np

from ..engine.models import SolveResult
from ..problem import TSPProblem
from .adapters.tsp_sma_adapter import TSPSMAAdapter
from .sma_core import SMACore


@dataclass
class SMATSPModularV1Solver:
    def solve(self, problem: TSPProblem, config: dict[str, Any], rng: np.random.Generator) -> SolveResult:
        if not isinstance(problem, TSPProblem):
            raise TypeError("sma_tsp_modular_v1 only supports TSPProblem")
        stop_condition = config.get("stop_condition", {})
        if stop_condition.get("type") != "max_iterations":
            raise ValueError("sma_tsp_modular_v1 only supports stop_condition.type=max_iterations")
        max_iterations = int(stop_condition.get("max_iterations", 0))
        if max_iterations <= 0:
            raise ValueError("max_iterations must be > 0")
        params = config.get("params", {})
        pop_size = int(params.get("pop_size", 30))
        z = float(params.get("z", 0.08))
        run_seed = int(config.get("run_seed", rng.integers(0, np.iinfo(np.int32).max)))
        local_rng = np.random.default_rng(run_seed)

        t0 = time.perf_counter()
        adapter = TSPSMAAdapter(problem)
        core = SMACore(dim_position=adapter.dim_position, pop_size=pop_size, max_iter=max_iterations, z=z)
        best_solution, best_objective, meta = core.run(adapter, local_rng)
        runtime = time.perf_counter() - t0
        stop_reason = (
            "best_known_reached"
            if problem.best_known is not None and float(best_objective) <= float(problem.best_known)
            else "max_iterations_reached"
        )
        return SolveResult(
            problem_id=problem.problem_id,
            solver_id=str(config.get("solver_id", "sma_tsp_modular_v1")),
            seed=run_seed,
            best_solution=np.asarray(best_solution, dtype=int),
            best_objective=int(best_objective),
            feasible=True,
            evaluation_count=int(meta["evaluation_count"]),
            stop_reason=stop_reason,
            runtime=runtime,
            error=None,
            metadata=dict(meta),
        )
