from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from .validation import (
    DirectionAtom,
    DirectionSpec,
    ObjectiveValue,
    ValidationReport,
    normalize_direction_spec,
    normalize_objective_value,
)

if TYPE_CHECKING:
    from ..engine.models import SolveResult

Direction = DirectionAtom


def as_int_array(name: str, data: np.ndarray | list[int]) -> np.ndarray:
    """Normalize to int64 C-contiguous 1D array."""
    arr = np.ascontiguousarray(np.asarray(data, dtype=np.int64))
    if arr.ndim != 1:
        raise ValueError(f"{name} must be a 1D integer array.")
    return arr


def as_int_matrix(name: str, data: np.ndarray | list[list[int]]) -> np.ndarray:
    """Normalize to int64 C-contiguous 2D matrix."""
    arr = np.ascontiguousarray(np.asarray(data, dtype=np.int64))
    if arr.ndim != 2:
        raise ValueError(f"{name} must be a 2D integer matrix.")
    return arr


def normalize_best_known(value: ObjectiveValue | None, *, allow_none: bool) -> ObjectiveValue | None:
    if value is None:
        if allow_none:
            return None
        raise ValueError("best_known must be a positive integer.")
    normalized = normalize_objective_value(value, name="best_known")
    values = normalized if isinstance(normalized, tuple) else (normalized,)
    for item in values:
        if isinstance(item, float) and item.is_integer():
            item = int(item)
        elif isinstance(item, float) and not allow_none:
            raise ValueError("best_known must be a positive integer.")
        if item <= 0:
            raise ValueError("best_known must be a positive integer.")
    if isinstance(normalized, tuple):
        return tuple(int(item) if isinstance(item, float) and item.is_integer() else item for item in normalized)
    if isinstance(normalized, float) and normalized.is_integer():
        return int(normalized)
    return normalized


@dataclass(frozen=True, kw_only=True)
class Problem(ABC):
    problem_id: str
    dataset: str
    best_known: ObjectiveValue | None
    problem_type: str
    encoding: str
    direction: DirectionSpec

    def __post_init__(self) -> None:
        if not self.problem_id.strip():
            raise ValueError("problem_id cannot be empty.")
        if not self.dataset.strip():
            raise ValueError("dataset cannot be empty.")
        if not self.problem_type.strip():
            raise ValueError("problem_type cannot be empty.")
        if not self.encoding.strip():
            raise ValueError("encoding cannot be empty.")
        object.__setattr__(self, "direction", normalize_direction_spec(self.direction))

    @abstractmethod
    def fitness(self, solution: np.ndarray) -> ObjectiveValue:
        """Compute the objective value for a decoded solution."""

    @abstractmethod
    def violates_constraints(self, solution: np.ndarray) -> bool:
        """Return True when the decoded solution violates problem constraints."""

    @abstractmethod
    def validate(self, solve_result: "SolveResult") -> ValidationReport:
        """Validate a solver result against this problem's objective and constraints."""
