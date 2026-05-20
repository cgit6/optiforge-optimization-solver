from __future__ import annotations

from dataclasses import dataclass
from multiprocessing.shared_memory import SharedMemory
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

import numpy as np

from .interface import Direction, Problem, normalize_best_known
from .registry import ProblemShmPack, ProblemTypeSpec
from .validation import ValidationReport, build_validation_report
from .yaml import require_fields, validate_identity

if TYPE_CHECKING:
    from ..engine.models import SolveResult


@dataclass(frozen=True, kw_only=True)
class TSPProblem(Problem):
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

        object.__setattr__(self, "best_known", normalize_best_known(self.best_known, allow_none=True))

    def fitness(self, solution: np.ndarray) -> int:
        tour = np.asarray(solution, dtype=int)
        if self.violates_constraints(tour):
            raise ValueError("solution must be a permutation of city indices.")
        return int(
            sum(
                int(self.distance_matrix[tour[i], tour[(i + 1) % self.n_cities]])
                for i in range(self.n_cities)
            )
        )

    def violates_constraints(self, solution: np.ndarray) -> bool:
        tour = np.asarray(solution, dtype=int)
        if tour.shape != (self.n_cities,):
            return True
        return set(int(x) for x in tour.tolist()) != set(range(self.n_cities))

    def validate(self, solve_result: "SolveResult") -> ValidationReport:
        tour = np.asarray(solve_result.best_solution, dtype=int)
        return build_validation_report(self, solve_result, solution=tour)


@dataclass(frozen=True)
class TSPProblemShmPack:
    kind: Literal["tsp"]
    problem_type: str
    dataset: str
    problem_id: str
    shm_name_distance_matrix: str
    shape_distance_matrix: tuple[int, int]
    n_cities: int
    best_known: int | float | None


def load_tsp_problem(data: dict[str, Any], dataset: str, problem_id: str, file_path: Path) -> TSPProblem:
    required = ("problem_id", "dataset", "problem_type", "n_cities", "distance_matrix")
    require_fields(data, required, file_path)
    validate_identity(data, problem_type="tsp", dataset=dataset, problem_id=problem_id, file_path=file_path)
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


def make_tsp_shm_pack(model: Problem, shm_blocks: list[SharedMemory]) -> TSPProblemShmPack:
    if not isinstance(model, TSPProblem):
        raise TypeError(f"make_tsp_shm_pack expected TSPProblem, got {type(model).__name__}")
    d_src = np.ascontiguousarray(model.distance_matrix, dtype=np.int64)
    sd = SharedMemory(create=True, size=int(d_src.nbytes))
    shm_blocks.append(sd)
    np.ndarray(d_src.shape, dtype=np.int64, buffer=sd.buf)[:] = d_src
    return TSPProblemShmPack(
        kind="tsp",
        problem_type=model.problem_type,
        dataset=model.dataset,
        problem_id=model.problem_id,
        shm_name_distance_matrix=sd.name,
        shape_distance_matrix=(int(d_src.shape[0]), int(d_src.shape[1])),
        n_cities=model.n_cities,
        best_known=model.best_known,
    )


def attach_tsp_shm_pack(pack: ProblemShmPack, shm_blocks: list[SharedMemory]) -> TSPProblem:
    pack = cast(TSPProblemShmPack, pack)
    shm = SharedMemory(name=pack.shm_name_distance_matrix)
    shm_blocks.append(shm)
    distance_matrix = np.ndarray(pack.shape_distance_matrix, dtype=np.int64, buffer=shm.buf)
    distance_matrix.setflags(write=False)
    return TSPProblem(
        problem_id=pack.problem_id,
        dataset=pack.dataset,
        n_cities=pack.n_cities,
        distance_matrix=distance_matrix,
        best_known=pack.best_known,
    )


def tspProblemSpec() -> ProblemTypeSpec:
    return ProblemTypeSpec(
        problem_type="tsp",
        encoding="permutation",
        direction="min",
        model_type=TSPProblem,
        loader=load_tsp_problem,
        yaml_required_fields=("problem_id", "dataset", "problem_type", "n_cities", "distance_matrix"),
        make_shm_pack=make_tsp_shm_pack,
        attach_shm_pack=attach_tsp_shm_pack,
    )
