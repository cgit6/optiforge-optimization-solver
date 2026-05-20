from __future__ import annotations

from dataclasses import dataclass
from multiprocessing.shared_memory import SharedMemory
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

import numpy as np

from .interface import Direction, Problem, as_int_array, as_int_matrix, normalize_best_known
from .registry import ProblemShmPack, ProblemTypeSpec
from .validation import ValidationReport, build_validation_report
from .yaml import require_fields, validate_identity

if TYPE_CHECKING:
    from ..engine.models import SolveResult


@dataclass(frozen=True, kw_only=True)
class MKPProblem(Problem):
    """Multidimensional knapsack problem."""

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

        values = as_int_array("values", self.values)
        weights = as_int_matrix("weights", self.weights)
        capacities = as_int_array("capacities", self.capacities)

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
        object.__setattr__(self, "best_known", normalize_best_known(self.best_known, allow_none=False))

    # 目標函數
    def fitness(self, solution: np.ndarray) -> int:
        solution = np.asarray(solution, dtype=int)
        if solution.shape != (self.items,):
            raise ValueError("solution shape must equal problem.items")
        return int(np.dot(self.values, solution))

    # 限制式
    def violates_constraints(self, solution: np.ndarray) -> bool:
        solution = np.asarray(solution, dtype=int)
        if solution.shape != (self.items,):
            return True
        used = np.sum(np.multiply(self.weights.T, solution), axis=1)
        return bool(np.any(used > self.capacities))

    # 求解完畢後驗證可行性
    def validate(self, solve_result: "SolveResult") -> ValidationReport:
        solution = np.asarray(solve_result.best_solution, dtype=int)
        return build_validation_report(self, solve_result, solution=solution)


@dataclass(frozen=True)
class MKPProblemShmPack:
    kind: Literal["mkp"]
    problem_type: str
    dataset: str
    problem_id: str
    shm_name_values: str
    shm_name_weights: str
    shm_name_capacities: str
    shape_values: tuple[int, ...]
    shape_weights: tuple[int, int]
    shape_capacities: tuple[int, ...]
    items: int
    dim: int
    best_known: int


def load_mkp_problem(data: dict[str, Any], dataset: str, problem_id: str, file_path: Path) -> MKPProblem:
    required = ("problem_id", "dataset", "items", "dim", "best_known", "values", "weights", "capacities")
    require_fields(data, required, file_path)
    validate_identity(data, problem_type="mkp", dataset=dataset, problem_id=problem_id, file_path=file_path)
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


def make_mkp_shm_pack(model: Problem, shm_blocks: list[SharedMemory]) -> MKPProblemShmPack:
    if not isinstance(model, MKPProblem):
        raise TypeError(f"make_mkp_shm_pack expected MKPProblem, got {type(model).__name__}")
    v_src = np.ascontiguousarray(model.values, dtype=np.int64)
    w_src = np.ascontiguousarray(model.weights, dtype=np.int64)
    c_src = np.ascontiguousarray(model.capacities, dtype=np.int64)

    sv = SharedMemory(create=True, size=int(v_src.nbytes))
    sw = SharedMemory(create=True, size=int(w_src.nbytes))
    sc = SharedMemory(create=True, size=int(c_src.nbytes))
    shm_blocks.extend([sv, sw, sc])

    np.ndarray(v_src.shape, dtype=np.int64, buffer=sv.buf)[:] = v_src
    np.ndarray(w_src.shape, dtype=np.int64, buffer=sw.buf)[:] = w_src
    np.ndarray(c_src.shape, dtype=np.int64, buffer=sc.buf)[:] = c_src

    return MKPProblemShmPack(
        kind="mkp",
        problem_type=model.problem_type,
        dataset=model.dataset,
        problem_id=model.problem_id,
        shm_name_values=sv.name,
        shm_name_weights=sw.name,
        shm_name_capacities=sc.name,
        shape_values=tuple(int(x) for x in v_src.shape),
        shape_weights=(int(w_src.shape[0]), int(w_src.shape[1])),
        shape_capacities=tuple(int(x) for x in c_src.shape),
        items=model.items,
        dim=model.dim,
        best_known=int(model.best_known),
    )


def attach_mkp_shm_pack(pack: ProblemShmPack, shm_blocks: list[SharedMemory]) -> MKPProblem:
    pack = cast(MKPProblemShmPack, pack)
    sv = SharedMemory(name=pack.shm_name_values)
    sw = SharedMemory(name=pack.shm_name_weights)
    sc = SharedMemory(name=pack.shm_name_capacities)
    shm_blocks.extend([sv, sw, sc])
    values = np.ndarray(pack.shape_values, dtype=np.int64, buffer=sv.buf)
    weights = np.ndarray(pack.shape_weights, dtype=np.int64, buffer=sw.buf)
    capacities = np.ndarray(pack.shape_capacities, dtype=np.int64, buffer=sc.buf)
    values.setflags(write=False)
    weights.setflags(write=False)
    capacities.setflags(write=False)
    return MKPProblem(
        problem_id=pack.problem_id,
        dataset=pack.dataset,
        items=pack.items,
        dim=pack.dim,
        values=values,
        weights=weights,
        capacities=capacities,
        best_known=pack.best_known,
    )


def mkpProblemSpec() -> ProblemTypeSpec:
    return ProblemTypeSpec(
        problem_type="mkp",
        encoding="binary",
        direction="max",
        model_type=MKPProblem,
        loader=load_mkp_problem,
        yaml_required_fields=("problem_id", "dataset", "items", "dim", "best_known", "values", "weights", "capacities"),
        make_shm_pack=make_mkp_shm_pack,
        attach_shm_pack=attach_mkp_shm_pack,
    )
