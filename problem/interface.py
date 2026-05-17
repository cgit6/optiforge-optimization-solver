from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

import numpy as np

Direction = Literal["max", "min"]


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


def normalize_best_known(value: int | float | None, *, allow_none: bool) -> int | float | None:
    if value is None:
        if allow_none:
            return None
        raise ValueError("best_known must be a positive integer.")
    if isinstance(value, bool):
        raise ValueError("best_known must be numeric.")
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    elif isinstance(value, float) and not allow_none:
        raise ValueError("best_known must be a positive integer.")
    if isinstance(value, int) and value <= 0:
        raise ValueError("best_known must be a positive integer.")
    if isinstance(value, float) and value <= 0:
        raise ValueError("best_known must be a positive integer.")
    return value


@dataclass(frozen=True, kw_only=True)
class Problem(ABC):
    problem_id: str
    dataset: str
    best_known: int | float | None
    problem_type: str
    encoding: str
    direction: Direction

    def __post_init__(self) -> None:
        if not self.problem_id.strip():
            raise ValueError("problem_id cannot be empty.")
        if not self.dataset.strip():
            raise ValueError("dataset cannot be empty.")
        if not self.problem_type.strip():
            raise ValueError("problem_type cannot be empty.")
        if not self.encoding.strip():
            raise ValueError("encoding cannot be empty.")
        if self.direction not in ("max", "min"):
            raise ValueError("direction must be 'max' or 'min'.")

    @abstractmethod
    def fitness(self, solution: np.ndarray) -> int | float:
        """Compute the objective value for a decoded solution."""

    @abstractmethod
    def violates_constraints(self, solution: np.ndarray) -> bool:
        """Return True when the decoded solution violates problem constraints."""
