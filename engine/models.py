from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping, Optional

import numpy as np

ExecutionMode = Literal["grid", "worker_curriculum"]
Direction = Literal["max", "min"]


def _as_int_array(name: str, data: np.ndarray | list[int]) -> np.ndarray:
    """Normalize to ``int64`` C-contiguous (shared contract for solvers / Numba)."""
    arr = np.ascontiguousarray(np.asarray(data, dtype=np.int64))
    if arr.ndim != 1:
        raise ValueError(f"{name} must be a 1D integer array.")
    return arr


def _as_int_matrix(name: str, data: np.ndarray | list[list[int]]) -> np.ndarray:
    """Normalize to ``int64`` C-contiguous 2D matrix."""
    arr = np.ascontiguousarray(np.asarray(data, dtype=np.int64))
    if arr.ndim != 2:
        raise ValueError(f"{name} must be a 2D integer matrix.")
    return arr


def _normalize_best_known(value: int | float | None, *, allow_none: bool) -> int | float | None:
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


@dataclass(frozen=True)
class ExperimentSpec:
    experiment_id: str
    dataset: str
    problem_ids: tuple[str, ...]
    solver_ids: tuple[str, ...]
    repeat: int
    seed: int
    output_dir: Path
    problem_type: str = "mkp"
    benchmark_enabled: bool = False
    execution_mode: ExecutionMode = "grid"

    def __post_init__(self) -> None:
        if not self.experiment_id.strip():
            raise ValueError("experiment_id cannot be empty.")
        if not self.problem_type.strip():
            raise ValueError("problem_type cannot be empty.")
        if not self.dataset.strip():
            raise ValueError("dataset cannot be empty.")
        if self.repeat <= 0:
            raise ValueError("repeat must be > 0.")
        if self.seed < 0:
            raise ValueError("seed must be >= 0.")
        if not self.problem_ids:
            raise ValueError("problem_ids cannot be empty.")
        if not self.solver_ids:
            raise ValueError("solver_ids cannot be empty.")
        if any(not problem_id.strip() for problem_id in self.problem_ids):
            raise ValueError("problem_ids cannot contain empty value.")
        if any(not solver_id.strip() for solver_id in self.solver_ids):
            raise ValueError("solver_ids cannot contain empty value.")
        if self.execution_mode not in ("grid", "worker_curriculum"):
            raise ValueError("execution_mode must be 'grid' or 'worker_curriculum'.")


@dataclass(frozen=True, kw_only=True)
class BaseProblem:
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


@dataclass(frozen=True, kw_only=True)
class MKPProblem(BaseProblem):
    """MKP 題目。

    After ``__post_init__``, ``values``, ``weights``, and ``capacities`` are guaranteed
    ``dtype=np.int64``, C-contiguous, and read-only. Solvers should use them directly
    without re-casting inside hot paths.
    """

    items: int
    dim: int
    values: np.ndarray
    weights: np.ndarray
    capacities: np.ndarray
    problem_type: str = "mkp"
    encoding: str = "binary"
    direction: Direction = "max"

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.items <= 0:
            raise ValueError("items must be > 0.")
        if self.dim <= 0:
            raise ValueError("dim must be > 0.")

        values = _as_int_array("values", self.values)
        weights = _as_int_matrix("weights", self.weights)
        capacities = _as_int_array("capacities", self.capacities)

        if len(values) != self.items:
            raise ValueError("len(values) must equal items.")
        if weights.shape != (self.items, self.dim):
            raise ValueError("weights shape must be (items, dim).")
        if len(capacities) != self.dim:
            raise ValueError("len(capacities) must equal dim.")

        values.setflags(write=False)
        weights.setflags(write=False)
        capacities.setflags(write=False)
        object.__setattr__(self, "values", values)
        object.__setattr__(self, "weights", weights)
        object.__setattr__(self, "capacities", capacities)
        object.__setattr__(
            self,
            "best_known",
            _normalize_best_known(self.best_known, allow_none=False),
        )


@dataclass(frozen=True, kw_only=True)
class TSPProblem(BaseProblem):
    n_cities: int
    distance_matrix: np.ndarray
    coords: np.ndarray | None = None
    problem_type: str = "tsp"
    encoding: str = "permutation"
    direction: Direction = "min"

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.n_cities <= 1:
            raise ValueError("n_cities must be > 1.")
        distances = np.ascontiguousarray(np.asarray(self.distance_matrix, dtype=np.int64))
        if distances.shape != (self.n_cities, self.n_cities):
            raise ValueError("distance_matrix shape must be (n_cities, n_cities).")
        if not np.all(np.diag(distances) == 0):
            raise ValueError("distance_matrix diagonal must be 0.")
        if not np.array_equal(distances, distances.T):
            raise ValueError("distance_matrix must be symmetric.")
        distances.setflags(write=False)
        object.__setattr__(self, "distance_matrix", distances)

        if self.coords is not None:
            coords = np.asarray(self.coords, dtype=float)
            if coords.shape != (self.n_cities, 2):
                raise ValueError("coords shape must be (n_cities, 2) when present.")
            coords.setflags(write=False)
            object.__setattr__(self, "coords", coords)

        object.__setattr__(
            self,
            "best_known",
            _normalize_best_known(self.best_known, allow_none=True),
        )


# Backward-compatible name for existing MKP tests and callers.
ProblemModel = MKPProblem


@dataclass(frozen=True)
class RunTask:
    problem_id: str
    dataset: str
    solver_id: str
    repeat_index: int
    seed: int
    problem_type: str = "mkp"

    def __post_init__(self) -> None:
        if not self.problem_type.strip():
            raise ValueError("problem_type cannot be empty.")
        if not self.problem_id.strip():
            raise ValueError("problem_id cannot be empty.")
        if not self.dataset.strip():
            raise ValueError("dataset cannot be empty.")
        if not self.solver_id.strip():
            raise ValueError("solver_id cannot be empty.")
        if self.repeat_index < 0:
            raise ValueError("repeat_index must be >= 0.")
        if self.seed < 0:
            raise ValueError("seed must be >= 0.")


@dataclass(frozen=True)
class SolveResult:
    problem_id: str
    solver_id: str
    seed: int
    best_solution: np.ndarray
    best_objective: int | float
    feasible: bool
    evaluation_count: int
    stop_reason: str
    runtime: float
    linprog_runtime: float = 0.0
    error: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.problem_id.strip():
            raise ValueError("problem_id cannot be empty.")
        if not self.solver_id.strip():
            raise ValueError("solver_id cannot be empty.")
        if self.seed < 0:
            raise ValueError("seed must be >= 0.")
        if self.evaluation_count < 0:
            raise ValueError("evaluation_count must be >= 0.")
        if self.runtime < 0:
            raise ValueError("runtime must be >= 0.")
        if self.linprog_runtime < 0:
            raise ValueError("linprog_runtime must be >= 0.")
        if not self.stop_reason.strip():
            raise ValueError("stop_reason cannot be empty.")
        if isinstance(self.best_objective, bool):
            raise ValueError("best_objective must be numeric.")

        best_solution = np.asarray(self.best_solution)
        if best_solution.ndim != 1:
            raise ValueError("best_solution must be a 1D array.")
        best_solution.setflags(write=False)
        object.__setattr__(self, "best_solution", best_solution)
        object.__setattr__(self, "metadata", dict(self.metadata))
