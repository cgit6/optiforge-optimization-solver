from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np

from .models import BaseProblem, Direction, MKPProblem, TSPProblem

ProblemLoader = Callable[[dict[str, Any], str, str, Path], BaseProblem]


@dataclass(frozen=True)
class ProblemTypeSpec:
    problem_type: str
    encoding: str
    direction: Direction
    loader: ProblemLoader
    yaml_required_fields: tuple[str, ...]


class ProblemRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, ProblemTypeSpec] = {}

    def register(self, spec: ProblemTypeSpec) -> None:
        if not spec.problem_type.strip():
            raise ValueError("problem_type cannot be empty.")
        if spec.problem_type in self._specs:
            raise ValueError(f"Problem type already registered: {spec.problem_type}")
        self._specs[spec.problem_type] = spec

    def get(self, problem_type: str) -> ProblemTypeSpec:
        try:
            return self._specs[problem_type]
        except KeyError as exc:
            raise KeyError(f"Problem type is not registered: {problem_type}") from exc

    def list_problem_types(self) -> tuple[str, ...]:
        return tuple(sorted(self._specs))


def _require(data: dict[str, Any], fields: tuple[str, ...], file_path: Path) -> None:
    missing = [field for field in fields if field not in data]
    if missing:
        raise ValueError(f"Missing required field(s) {missing} in {file_path}")


def _validate_identity(
    data: dict[str, Any],
    *,
    problem_type: str,
    dataset: str,
    problem_id: str,
    file_path: Path,
) -> None:
    yaml_problem_id = str(data["problem_id"])
    yaml_dataset = str(data["dataset"])
    yaml_problem_type = str(data.get("problem_type", problem_type))
    if yaml_problem_id != problem_id:
        raise ValueError(f"problem_id mismatch in {file_path}: expected {problem_id}, got {yaml_problem_id}")
    if yaml_dataset != dataset:
        raise ValueError(f"dataset mismatch in {file_path}: expected {dataset}, got {yaml_dataset}")
    if yaml_problem_type != problem_type:
        raise ValueError(
            f"problem_type mismatch in {file_path}: expected {problem_type}, got {yaml_problem_type}"
        )


def load_mkp_problem(
    data: dict[str, Any], dataset: str, problem_id: str, file_path: Path
) -> MKPProblem:
    required = ("problem_id", "dataset", "items", "dim", "best_known", "values", "weights", "capacities")
    _require(data, required, file_path)
    _validate_identity(data, problem_type="mkp", dataset=dataset, problem_id=problem_id, file_path=file_path)
    try:
        return MKPProblem(
            problem_id=str(data["problem_id"]),
            dataset=str(data["dataset"]),
            items=int(data["items"]),
            dim=int(data["dim"]),
            best_known=data["best_known"],
            values=np.asarray(data["values"], dtype=int),
            weights=np.asarray(data["weights"], dtype=int),
            capacities=np.asarray(data["capacities"], dtype=int),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid MKP problem data in {file_path}: {exc}") from exc


def load_tsp_problem(
    data: dict[str, Any], dataset: str, problem_id: str, file_path: Path
) -> TSPProblem:
    required = ("problem_id", "dataset", "problem_type", "n_cities", "distance_matrix")
    _require(data, required, file_path)
    _validate_identity(data, problem_type="tsp", dataset=dataset, problem_id=problem_id, file_path=file_path)
    try:
        return TSPProblem(
            problem_id=str(data["problem_id"]),
            dataset=str(data["dataset"]),
            n_cities=int(data["n_cities"]),
            best_known=data.get("best_known"),
            distance_matrix=np.asarray(data["distance_matrix"], dtype=int),
            coords=np.asarray(data["coords"], dtype=float) if data.get("coords") is not None else None,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid TSP problem data in {file_path}: {exc}") from exc


def default_problem_registry() -> ProblemRegistry:
    registry = ProblemRegistry()
    registry.register(
        ProblemTypeSpec(
            problem_type="mkp",
            encoding="binary",
            direction="max",
            loader=load_mkp_problem,
            yaml_required_fields=(
                "problem_id",
                "dataset",
                "items",
                "dim",
                "best_known",
                "values",
                "weights",
                "capacities",
            ),
        )
    )
    registry.register(
        ProblemTypeSpec(
            problem_type="tsp",
            encoding="permutation",
            direction="min",
            loader=load_tsp_problem,
            yaml_required_fields=("problem_id", "dataset", "problem_type", "n_cities", "distance_matrix"),
        )
    )
    return registry
