from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import numpy as np

from ..engine.models import BaseProblem, MKPProblem, SolveResult, TSPProblem


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
    def validate(self, problem: BaseProblem, solve_result: SolveResult) -> ValidationReport:
        if isinstance(problem, MKPProblem):
            return MKPValidator().validate(problem, solve_result)
        if isinstance(problem, TSPProblem):
            return TSPValidator().validate(problem, solve_result)
        raise TypeError(f"Unsupported problem type for validation: {type(problem).__name__}")


class MKPValidator:
    def validate(self, problem: MKPProblem, solve_result: SolveResult) -> ValidationReport:
        solution = np.asarray(solve_result.best_solution, dtype=int)

        violations = self._check_feasibility(problem, solution)
        is_feasible = len(violations) == 0

        recomputed_objective = int(np.dot(problem.values, solution))
        objective_valid = recomputed_objective == int(solve_result.best_objective)
        objective_mismatch = not objective_valid

        best_known_gap = int(problem.best_known) - int(solve_result.best_objective)
        best_known_reached = int(solve_result.best_objective) >= int(problem.best_known)

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

    def _check_feasibility(self, problem: MKPProblem, solution: np.ndarray) -> tuple[int, ...]:
        if solution.shape != (problem.items,):
            raise ValueError("best_solution shape must equal problem.items")

        violations: list[int] = []
        for dim_idx in range(problem.dim):
            used = int(np.dot(problem.weights[:, dim_idx], solution))
            capacity = int(problem.capacities[dim_idx])
            if used > capacity:
                violations.append(dim_idx)
        return tuple(violations)


class TSPValidator:
    def validate(self, problem: TSPProblem, solve_result: SolveResult) -> ValidationReport:
        solution = np.asarray(solve_result.best_solution, dtype=int)
        is_valid_permutation = self._is_valid_permutation(solution, problem.n_cities)
        violations = tuple() if is_valid_permutation else (0,)

        if is_valid_permutation:
            recomputed_objective = int(
                sum(
                    int(problem.distance_matrix[solution[i], solution[(i + 1) % problem.n_cities]])
                    for i in range(problem.n_cities)
                )
            )
            objective_valid = recomputed_objective == int(solve_result.best_objective)
        else:
            recomputed_objective = 0
            objective_valid = False

        objective_mismatch = not objective_valid
        if problem.best_known is None:
            best_known_gap = None
            best_known_reached = False
        else:
            best_known_gap = float(solve_result.best_objective) - float(problem.best_known)
            if isinstance(problem.best_known, int) and isinstance(solve_result.best_objective, int):
                best_known_gap = int(best_known_gap)
            best_known_reached = float(solve_result.best_objective) <= float(problem.best_known)

        return ValidationReport(
            is_feasible=is_valid_permutation,
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
            metadata={
                "tour_length": recomputed_objective if is_valid_permutation else None,
                "is_valid_permutation": is_valid_permutation,
            },
        )

    def _is_valid_permutation(self, solution: np.ndarray, n_cities: int) -> bool:
        if solution.shape != (n_cities,):
            return False
        return set(int(x) for x in solution.tolist()) == set(range(n_cities))
