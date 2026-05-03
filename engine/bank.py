"""題庫掃描、Catalog、GameSetting，以及以 shared_memory 共用的 ProblemBank。"""

from __future__ import annotations

from dataclasses import dataclass
from multiprocessing.shared_memory import SharedMemory
from pathlib import Path
from typing import Any, Literal

import numpy as np

from .models import BaseProblem, ExperimentSpec, MKPProblem, TSPProblem
from .problem_registry import default_problem_registry
from .repository import ProblemRepository

_worker_problem_view: Any | None = None


@dataclass(frozen=True)
class ProblemCatalogEntry:
    problem_type: str
    dataset: str
    problem_id: str
    filename: str


@dataclass(frozen=True)
class GameSetting:
    problem_types: tuple[str, ...]
    datasets: tuple[str, ...]
    problems_by_dataset: tuple[tuple[str, tuple[str, ...]], ...]

    def problems_in(self, dataset: str) -> tuple[str, ...]:
        for ds, pids in self.problems_by_dataset:
            if ds == dataset:
                return pids
        return tuple()


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


ProblemShmPack = MKPProblemShmPack | TSPProblemShmPack


class ProblemWorkerView:
    def __init__(self, packs: tuple[ProblemShmPack, ...]) -> None:
        self._models: dict[tuple[str, str, str], BaseProblem] = {}
        self._shms: list[SharedMemory] = []
        for pack in packs:
            if pack.kind == "mkp":
                self._attach_mkp(pack)
            elif pack.kind == "tsp":
                self._attach_tsp(pack)
            else:
                raise RuntimeError(f"Unsupported problem shm pack kind: {pack!r}")

    def _attach_mkp(self, pack: MKPProblemShmPack) -> None:
        sv = SharedMemory(name=pack.shm_name_values)
        sw = SharedMemory(name=pack.shm_name_weights)
        sc = SharedMemory(name=pack.shm_name_capacities)
        self._shms.extend([sv, sw, sc])
        values = np.ndarray(pack.shape_values, dtype=np.int64, buffer=sv.buf)
        weights = np.ndarray(pack.shape_weights, dtype=np.int64, buffer=sw.buf)
        capacities = np.ndarray(pack.shape_capacities, dtype=np.int64, buffer=sc.buf)
        values.setflags(write=False)
        weights.setflags(write=False)
        capacities.setflags(write=False)
        self._models[(pack.problem_type, pack.dataset, pack.problem_id)] = MKPProblem(
            problem_id=pack.problem_id,
            dataset=pack.dataset,
            items=pack.items,
            dim=pack.dim,
            values=values,
            weights=weights,
            capacities=capacities,
            best_known=pack.best_known,
        )

    def _attach_tsp(self, pack: TSPProblemShmPack) -> None:
        shm = SharedMemory(name=pack.shm_name_distance_matrix)
        self._shms.append(shm)
        distance_matrix = np.ndarray(pack.shape_distance_matrix, dtype=np.int64, buffer=shm.buf)
        distance_matrix.setflags(write=False)
        self._models[(pack.problem_type, pack.dataset, pack.problem_id)] = TSPProblem(
            problem_id=pack.problem_id,
            dataset=pack.dataset,
            n_cities=pack.n_cities,
            distance_matrix=distance_matrix,
            best_known=pack.best_known,
        )

    def get(self, dataset: str, problem_id: str, problem_type: str = "mkp") -> BaseProblem:
        try:
            return self._models[(problem_type, dataset, problem_id)]
        except KeyError as exc:
            raise FileNotFoundError(
                "Problem not in shared bank: "
                f"problem_type={problem_type!r} dataset={dataset!r} problem_id={problem_id!r}"
            ) from exc


def configure_problem_bank_worker(packs: tuple[ProblemShmPack, ...]) -> None:
    global _worker_problem_view
    _worker_problem_view = ProblemWorkerView(packs)


def get_worker_problem_bank() -> ProblemWorkerView:
    if _worker_problem_view is None:
        raise RuntimeError("worker ProblemBank view is not configured")
    return _worker_problem_view


def scan_problem_catalog(problem_root: Path) -> tuple[list[ProblemCatalogEntry], GameSetting]:
    if not problem_root.is_dir():
        raise FileNotFoundError(f"problem_root is not a directory: {problem_root}")
    entries: list[ProblemCatalogEntry] = []
    by_dataset: dict[str, list[str]] = {}
    problem_types: set[str] = set()
    known_problem_types = set(default_problem_registry().list_problem_types())

    for first_level in sorted(p for p in problem_root.iterdir() if p.is_dir()):
        if first_level.name in known_problem_types:
            problem_type = first_level.name
            for dataset_dir in sorted(p for p in first_level.iterdir() if p.is_dir()):
                dataset = dataset_dir.name
                by_dataset.setdefault(dataset, [])
                problem_types.add(problem_type)
                for yaml_path in sorted(dataset_dir.glob("*.yaml")):
                    problem_id = yaml_path.stem
                    rel = str(yaml_path.relative_to(problem_root)).replace("\\", "/")
                    entries.append(
                        ProblemCatalogEntry(
                            problem_type=problem_type,
                            dataset=dataset,
                            problem_id=problem_id,
                            filename=rel,
                        )
                    )
                    by_dataset[dataset].append(problem_id)
        else:
            dataset = first_level.name
            by_dataset.setdefault(dataset, [])
            for yaml_path in sorted(first_level.glob("*.yaml")):
                problem_id = yaml_path.stem
                rel = str(yaml_path.relative_to(problem_root)).replace("\\", "/")
                entries.append(
                    ProblemCatalogEntry(
                        problem_type="mkp",
                        dataset=dataset,
                        problem_id=problem_id,
                        filename=rel,
                    )
                )
                problem_types.add("mkp")
                by_dataset[dataset].append(problem_id)

    pbd = tuple((ds, tuple(sorted(set(pids)))) for ds, pids in sorted(by_dataset.items()))
    gs = GameSetting(
        problem_types=tuple(sorted(problem_types)),
        datasets=tuple(sorted(by_dataset.keys())),
        problems_by_dataset=pbd,
    )
    return entries, gs


def validate_catalog_entries(repository: ProblemRepository, entries: list[ProblemCatalogEntry]) -> None:
    """載入並驗證 catalog 內每一題（全題庫）；CI 或維護工具可呼叫。

    日常 `engine.build` 改用 :func:`validate_spec_problems_in_repository` 以避免對未使用題目重複 I/O。
    """
    for entry in entries:
        repository.load(entry.dataset, entry.problem_id, entry.problem_type)


def validate_spec_problems_in_repository(repository: ProblemRepository, spec: ExperimentSpec) -> None:
    """僅對本次實驗的題目呼叫 ``repository.load``（語意與舊版全量驗證的子集一致）。"""
    seen: set[str] = set()
    for pid in spec.problem_ids:
        if pid in seen:
            continue
        seen.add(pid)
        repository.load(spec.dataset, pid, spec.problem_type)


def assert_spec_problems_in_catalog(spec: ExperimentSpec, entries: list[ProblemCatalogEntry]) -> None:
    keys = {(e.problem_type, e.dataset, e.problem_id) for e in entries}
    for pid in spec.problem_ids:
        if (spec.problem_type, spec.dataset, pid) not in keys:
            raise FileNotFoundError(
                f"Experiment problem not in scanned catalog: {spec.problem_type}/{spec.dataset}/{pid}.yaml"
            )


class ProblemBank:
    def __init__(
        self,
        *,
        models: dict[tuple[str, str, str], BaseProblem],
        shm_blocks: list[SharedMemory],
        packs: tuple[ProblemShmPack, ...],
    ) -> None:
        self._models = models
        self._shm_blocks = shm_blocks
        self._packs = packs

    @staticmethod
    def build_for_spec(*, repository: ProblemRepository, spec: ExperimentSpec) -> ProblemBank:
        uniq: dict[tuple[str, str, str], None] = {}
        for pid in spec.problem_ids:
            uniq[(spec.problem_type, spec.dataset, pid)] = None

        models: dict[tuple[str, str, str], BaseProblem] = {}
        shm_blocks: list[SharedMemory] = []
        packs: list[ProblemShmPack] = []

        for problem_type, dataset, pid in sorted(uniq.keys()):
            model = repository.load(dataset, pid, problem_type)
            if isinstance(model, MKPProblem):
                pack = _make_mkp_pack(model, shm_blocks)
            elif isinstance(model, TSPProblem):
                pack = _make_tsp_pack(model, shm_blocks)
            else:
                raise TypeError(f"Unsupported problem model type for SHM: {type(model).__name__}")
            models[(problem_type, dataset, pid)] = model
            packs.append(pack)

        return ProblemBank(models=models, shm_blocks=shm_blocks, packs=tuple(packs))

    def get(self, dataset: str, problem_id: str, problem_type: str = "mkp") -> BaseProblem:
        try:
            return self._models[(problem_type, dataset, problem_id)]
        except KeyError as exc:
            raise FileNotFoundError(
                "Problem not in bank for this experiment: "
                f"problem_type={problem_type!r} dataset={dataset!r} problem_id={problem_id!r}"
            ) from exc

    def export_worker_packs(self) -> tuple[ProblemShmPack, ...]:
        return self._packs

    def close(self) -> None:
        for shm in self._shm_blocks:
            try:
                shm.close()
            except Exception:
                pass
            try:
                shm.unlink()
            except FileNotFoundError:
                pass
        self._shm_blocks.clear()


def _make_mkp_pack(model: MKPProblem, shm_blocks: list[SharedMemory]) -> MKPProblemShmPack:
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


def _make_tsp_pack(model: TSPProblem, shm_blocks: list[SharedMemory]) -> TSPProblemShmPack:
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
