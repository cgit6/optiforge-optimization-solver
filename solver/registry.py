from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol

import numpy as np

from ..engine.models import BaseProblem, MKPProblem, SolveResult


class Solver(Protocol):
    def solve(self, problem: BaseProblem, config: dict[str, Any], rng: np.random.Generator) -> SolveResult:
        """Solve one problem instance and return standardized SolveResult."""


SolverBuilder = Callable[[], Solver]


class SolverRegistry:
    """Registry for solver builders."""

    def __init__(self) -> None:
        self._builders: dict[str, SolverBuilder] = {}

    # 註冊求解器
    def register(self, solver_id: str, builder: SolverBuilder) -> None:
        if not solver_id.strip():
            raise ValueError("solver_id cannot be empty.")
        if solver_id in self._builders:
            raise ValueError(f"Solver already registered: {solver_id}")
        self._builders[solver_id] = builder

    def get(self, solver_id: str) -> SolverBuilder:
        try:
            return self._builders[solver_id]
        except KeyError as exc:
            raise KeyError(f"Solver is not registered: {solver_id}") from exc

    def create(self, solver_id: str) -> Solver:
        return self.get(solver_id)()


@dataclass(frozen=True)
class StubMaxIterationsSolver:
    """Simple solver for contract tests."""

    def solve(self, problem: BaseProblem, config: dict[str, Any], rng: np.random.Generator) -> SolveResult:
        if not isinstance(problem, MKPProblem):
            raise TypeError("StubMaxIterationsSolver only supports MKPProblem")
        stop_condition = config.get("stop_condition", {})
        if stop_condition.get("type") != "max_iterations":
            raise ValueError("StubMaxIterationsSolver only supports stop_condition.type=max_iterations")

        max_iterations = int(stop_condition.get("max_iterations", 0))
        if max_iterations <= 0:
            raise ValueError("max_iterations must be > 0")

        best_solution = np.zeros(problem.items, dtype=int)
        best_objective = 0
        return SolveResult(
            problem_id=problem.problem_id,
            solver_id=str(config.get("solver_id", "stub_solver")),
            seed=int(rng.integers(0, np.iinfo(np.int32).max)),
            best_solution=best_solution,
            best_objective=best_objective,
            feasible=True,
            evaluation_count=max_iterations,
            stop_reason="max_iterations_reached",
            runtime=0.0,
            linprog_runtime=0.0,
            error=None,
        )
