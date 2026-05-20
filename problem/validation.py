from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, Mapping

import numpy as np

if TYPE_CHECKING:
    from ..engine.models import SolveResult
    from .interface import Problem

DirectionAtom = Literal["max", "min"]
DirectionSpec = DirectionAtom | tuple[DirectionAtom, ...]
ScalarObjective = int | float
ObjectiveValue = ScalarObjective | tuple[ScalarObjective, ...]
ObjectiveGap = ScalarObjective | tuple[ScalarObjective, ...] | None


def _is_numeric_scalar(value: Any) -> bool:
    return isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, bool)


def normalize_scalar_objective(value: Any, *, name: str) -> ScalarObjective:
    if not _is_numeric_scalar(value):
        raise ValueError(f"{name} must be numeric.")
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return value


def normalize_objective_value(value: Any, *, name: str) -> ObjectiveValue:
    if isinstance(value, (tuple, list)):
        if not value:
            raise ValueError(f"{name} cannot be empty.")
        return tuple(normalize_scalar_objective(v, name=name) for v in value)
    return normalize_scalar_objective(value, name=name)


def normalize_direction_spec(value: Any) -> DirectionSpec:
    if isinstance(value, str):
        if value not in ("max", "min"):
            raise ValueError("direction must be 'max' or 'min'.")
        return value
    if isinstance(value, (tuple, list)):
        if not value:
            raise ValueError("direction cannot be empty.")
        directions = tuple(str(v) for v in value)
        if not set(directions).issubset({"max", "min"}):
            raise ValueError("direction values must be 'max' or 'min'.")
        return directions  # type: ignore[return-value]
    raise ValueError("direction must be 'max', 'min', or a sequence of those values.")


def is_scalar_objective(value: ObjectiveValue | ObjectiveGap | None) -> bool:
    return value is not None and not isinstance(value, tuple)


def objective_values_equal(left: ObjectiveValue, right: ObjectiveValue) -> bool:
    left = normalize_objective_value(left, name="objective")
    right = normalize_objective_value(right, name="objective")
    left_values = _objective_tuple(left)
    right_values = _objective_tuple(right)
    if len(left_values) != len(right_values):
        return False
    return all(_scalar_objectives_equal(a, b) for a, b in zip(left_values, right_values, strict=True))


def best_known_status_and_gap(
    *,
    best_known: ObjectiveValue | None,
    objective: ObjectiveValue,
    direction: DirectionSpec,
) -> tuple[bool, ObjectiveGap]:
    if best_known is None:
        return False, None

    objective = normalize_objective_value(objective, name="best_objective")
    best_known = normalize_objective_value(best_known, name="best_known")
    directions = _direction_tuple(direction, objective)
    objective_values = _objective_tuple(objective)
    best_known_values = _objective_tuple(best_known)
    if len(best_known_values) != len(objective_values):
        raise ValueError("best_known dimension must match objective dimension.")

    gaps: list[ScalarObjective] = []
    reached: list[bool] = []
    for known, actual, objective_direction in zip(best_known_values, objective_values, directions, strict=True):
        gap = _best_known_gap(known, actual, objective_direction)
        gaps.append(gap)
        if objective_direction == "max":
            reached.append(float(actual) >= float(known))
        else:
            reached.append(float(actual) <= float(known))

    if len(gaps) == 1 and not isinstance(best_known, tuple) and not isinstance(objective, tuple):
        return all(reached), gaps[0]
    return all(reached), tuple(gaps)


def build_validation_report(
    problem: Problem,
    solve_result: SolveResult,
    *,
    solution: np.ndarray,
    metadata: Mapping[str, Any] | None = None,
) -> ValidationReport:
    violates_constraints = problem.violates_constraints(solution)
    is_feasible = not violates_constraints
    violations = (0,) if violates_constraints else tuple()

    if is_feasible:
        recomputed_objective = normalize_objective_value(problem.fitness(solution), name="recomputed_objective")
        objective_valid = objective_values_equal(recomputed_objective, solve_result.best_objective)
    else:
        recomputed_objective = 0
        objective_valid = False

    objective_mismatch = not objective_valid
    best_known_reached, best_known_gap = best_known_status_and_gap(
        best_known=problem.best_known,
        objective=solve_result.best_objective,
        direction=problem.direction,
    )

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
        metadata={} if metadata is None else metadata,
    )


@dataclass(frozen=True)
class ValidationReport:
    is_feasible: bool
    feasibility_violations: tuple[int, ...]
    objective_valid: bool
    recomputed_objective: ObjectiveValue
    objective_mismatch: bool
    best_known_reached: bool
    best_known_gap: ObjectiveGap
    problem_type: str
    encoding: str
    direction: DirectionSpec
    best_known: ObjectiveValue | None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "recomputed_objective", normalize_objective_value(
            self.recomputed_objective,
            name="recomputed_objective",
        ))
        if self.best_known is not None:
            object.__setattr__(self, "best_known", normalize_objective_value(self.best_known, name="best_known"))
        if self.best_known_gap is not None:
            object.__setattr__(self, "best_known_gap", normalize_objective_value(
                self.best_known_gap,
                name="best_known_gap",
            ))
        object.__setattr__(self, "direction", normalize_direction_spec(self.direction))
        object.__setattr__(self, "metadata", dict(self.metadata))


def _objective_tuple(value: ObjectiveValue) -> tuple[ScalarObjective, ...]:
    return value if isinstance(value, tuple) else (value,)


def _direction_tuple(direction: DirectionSpec, objective: ObjectiveValue) -> tuple[DirectionAtom, ...]:
    direction = normalize_direction_spec(direction)
    objective_len = len(_objective_tuple(objective))
    if isinstance(direction, tuple):
        if len(direction) != objective_len:
            raise ValueError("direction dimension must match objective dimension.")
        return direction
    return tuple(direction for _ in range(objective_len))


def _scalar_objectives_equal(left: ScalarObjective, right: ScalarObjective) -> bool:
    if isinstance(left, int) and isinstance(right, int):
        return left == right
    return bool(np.allclose(float(left), float(right), rtol=1e-9, atol=1e-12))


def _best_known_gap(
    best_known: ScalarObjective,
    objective: ScalarObjective,
    direction: DirectionAtom,
) -> ScalarObjective:
    gap = float(best_known) - float(objective) if direction == "max" else float(objective) - float(best_known)
    if isinstance(best_known, int) and isinstance(objective, int):
        return int(gap)
    return gap
