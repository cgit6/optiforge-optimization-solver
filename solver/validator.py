from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import numpy as np

from ..engine.models import SolveResult
from ..problem import Problem


@dataclass(frozen=True)
class ValidationReport:
    is_feasible: bool
    feasibility_violations: tuple[int, ...]
    objective_valid: bool
    recomputed_objective: int | float
    objective_mismatch: bool
    best_known_reached: bool
    best_known_gap: int | float | None
    problem_type: str
    encoding: str
    direction: str
    best_known: int | float | None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", dict(self.metadata))


class Validator:
    def validate(self, problem: Problem, solve_result: SolveResult) -> ValidationReport:
        solution = np.asarray(solve_result.best_solution, dtype=int)
        violates_constraints = problem.violates_constraints(solution)
        is_feasible = not violates_constraints
        violations = (0,) if violates_constraints else tuple()

        if is_feasible:
            recomputed_objective = problem.fitness(solution)
            objective_valid = recomputed_objective == solve_result.best_objective
        else:
            recomputed_objective = 0
            objective_valid = False

        objective_mismatch = not objective_valid
        if problem.best_known is None:
            best_known_gap = None
            best_known_reached = False
        elif problem.direction == "max":
            best_known_gap = float(problem.best_known) - float(solve_result.best_objective)
            if isinstance(problem.best_known, int) and isinstance(solve_result.best_objective, int):
                best_known_gap = int(best_known_gap)
            best_known_reached = float(solve_result.best_objective) >= float(problem.best_known)
        else:
            best_known_gap = float(solve_result.best_objective) - float(problem.best_known)
            if isinstance(problem.best_known, int) and isinstance(solve_result.best_objective, int):
                best_known_gap = int(best_known_gap)
            best_known_reached = float(solve_result.best_objective) <= float(problem.best_known)

        return ValidationReport(
            is_feasible=is_feasible,
            feasibility_violations=violations,
            objective_valid=objective_valid,
            recomputed_objective=recomputed_objective,
            objective_mismatch=objective_mismatch,
            best_known_reached=best_known_reached,
            best_known_gap=best_known_gap,
            problem_type=problem.problem_type,
            encoding=problem.encoding,
            direction=problem.direction,
            best_known=problem.best_known,
        )
