from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .contracts import ProblemModel, RunResult


@dataclass(frozen=True)
class ValidationReport:
    is_feasible: bool
    feasibility_violations: tuple[int, ...]
    objective_valid: bool
    recomputed_objective: int
    objective_mismatch: bool
    best_known_reached: bool
    best_known_gap: int


class Validator:
    """MKP-specific validator for one run result."""

    def validate(self, problem: ProblemModel, run_result: RunResult) -> ValidationReport:
        solution = np.asarray(run_result.best_solution, dtype=int)

        violations = self._check_feasibility(problem, solution)
        is_feasible = len(violations) == 0

        recomputed_objective = int(np.dot(problem.values, solution))
        objective_valid = recomputed_objective == int(run_result.best_objective)
        objective_mismatch = not objective_valid

        best_known_gap = int(problem.best_known) - int(run_result.best_objective)
        best_known_reached = int(run_result.best_objective) >= int(problem.best_known)

        return ValidationReport(
            is_feasible=is_feasible,
            feasibility_violations=violations,
            objective_valid=objective_valid,
            recomputed_objective=recomputed_objective,
            objective_mismatch=objective_mismatch,
            best_known_reached=best_known_reached,
            best_known_gap=best_known_gap,
        )

    def _check_feasibility(self, problem: ProblemModel, solution: np.ndarray) -> tuple[int, ...]:
        if solution.shape != (problem.items,):
            raise ValueError("best_solution shape must equal problem.items")

        violations: list[int] = []
        for dim_idx in range(problem.dim):
            used = int(np.dot(problem.weights[:, dim_idx], solution))
            capacity = int(problem.capacities[dim_idx])
            if used > capacity:
                violations.append(dim_idx)

        return tuple(violations)
