"""題庫掃描、Catalog、GameSetting，以及以 shared_memory 共用的 ProblemBank。"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from multiprocessing.shared_memory import SharedMemory
from pathlib import Path
from typing import Any

import numpy as np

from .models import ExperimentSpec, ProblemModel
from .repository import ProblemRepository

_worker_problem_view: Any | None = None


@dataclass(frozen=True)
class ProblemCatalogEntry:
    """僅 metadata，不含題目數值。"""

    dataset: str
    problem_id: str
    filename: str  # 相對於 problem_root 的路徑（POSIX）


@dataclass(frozen=True)
class GameSetting:
    """掃描後的題庫索引：有哪些 dataset、各 dataset 有哪些題目 id。"""

    datasets: tuple[str, ...]
    problems_by_dataset: tuple[tuple[str, tuple[str, ...]], ...]

    def problems_in(self, dataset: str) -> tuple[str, ...]:
        for ds, pids in self.problems_by_dataset:
            if ds == dataset:
                return pids
        return tuple()


@dataclass(frozen=True)
class ProblemShmPack:
    """子行程 attach shared_memory 所需的最小描述（可 pickle）。"""

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


class ProblemWorkerView:
    """子行程內：依 ProblemShmPack 建立唯讀 ProblemModel。"""

    def __init__(self, packs: tuple[ProblemShmPack, ...]) -> None:
        self._models: dict[tuple[str, str], ProblemModel] = {}
        self._shms: list[SharedMemory] = []
        for pack in packs:
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
            self._models[(pack.dataset, pack.problem_id)] = ProblemModel(
                problem_id=pack.problem_id,
                dataset=pack.dataset,
                items=pack.items,
                dim=pack.dim,
                values=values,
                weights=weights,
                capacities=capacities,
                best_known=pack.best_known,
            )

    def get(self, dataset: str, problem_id: str) -> ProblemModel:
        try:
            return self._models[(dataset, problem_id)]
        except KeyError as exc:
            raise FileNotFoundError(
                f"Problem not in shared bank: dataset={dataset!r} problem_id={problem_id!r}"
            ) from exc


def configure_problem_bank_worker(packs: tuple[ProblemShmPack, ...]) -> None:
    global _worker_problem_view
    _worker_problem_view = ProblemWorkerView(packs)


def get_worker_problem_bank() -> ProblemWorkerView:
    if _worker_problem_view is None:
        raise RuntimeError("worker ProblemBank view is not configured")
    return _worker_problem_view

# 掃描問題目錄
def scan_problem_catalog(problem_root: Path) -> tuple[list[ProblemCatalogEntry], GameSetting]:
    """掃描 `problem_root/<DATASET>/*.yaml`，建立 Catalog 與 GameSetting。"""
    if not problem_root.is_dir():
        raise FileNotFoundError(f"problem_root is not a directory: {problem_root}")
    entries: list[ProblemCatalogEntry] = []
    by_dataset: dict[str, list[str]] = {}
    for dataset_dir in sorted(p for p in problem_root.iterdir() if p.is_dir()):
        dataset = dataset_dir.name
        by_dataset.setdefault(dataset, [])
        for yaml_path in sorted(dataset_dir.glob("*.yaml")):
            problem_id = yaml_path.stem
            rel = str(yaml_path.relative_to(problem_root)).replace("\\", "/")
            e = ProblemCatalogEntry(dataset=dataset, problem_id=problem_id, filename=rel)
            entries.append(e)
            by_dataset[dataset].append(problem_id)
    pbd = tuple((ds, tuple(sorted(set(pids)))) for ds, pids in sorted(by_dataset.items()))
    # 這裡命名錯誤
    gs = GameSetting(datasets=tuple(sorted(by_dataset.keys())), problems_by_dataset=pbd)
    return entries, gs


def validate_catalog_entries(
    repository: ProblemRepository, entries: list[ProblemCatalogEntry]
) -> None:
    """逐題載入並做 schema 驗證；任一失敗即拋出。"""
    for entry in entries:
        repository.load(entry.dataset, entry.problem_id)


def assert_spec_problems_in_catalog(
    spec: ExperimentSpec, entries: list[ProblemCatalogEntry]
) -> None:
    keys = {(e.dataset, e.problem_id) for e in entries}
    for pid in spec.problem_ids:
        if (spec.dataset, pid) not in keys:
            raise FileNotFoundError(
                f"Experiment problem not in scanned catalog: {spec.dataset}/{pid}.yaml"
            )


class ProblemBank:
    """本次實驗題目：以 shared_memory 持有唯讀陣列，供主行程與子行程共用。"""

    def __init__(
        self,
        *,
        models: dict[tuple[str, str], ProblemModel],
        shm_blocks: list[SharedMemory],
        packs: tuple[ProblemShmPack, ...],
    ) -> None:
        self._models = models
        self._shm_blocks = shm_blocks
        self._packs = packs

    @staticmethod
    def build_for_spec(*, repository: ProblemRepository, spec: ExperimentSpec) -> ProblemBank:
        """只為本次 `spec.problem_ids` 建立 SHM 與唯讀 ProblemModel。"""
        uniq: dict[tuple[str, str], None] = {}
        for pid in spec.problem_ids:
            uniq[(spec.dataset, pid)] = None

        models: dict[tuple[str, str], ProblemModel] = {}
        shm_blocks: list[SharedMemory] = []
        packs: list[ProblemShmPack] = []

        for dataset, pid in sorted(uniq.keys()):
            model = repository.load(dataset, pid)
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

            pv = np.ndarray(v_src.shape, dtype=np.int64, buffer=sv.buf)
            pw = np.ndarray(w_src.shape, dtype=np.int64, buffer=sw.buf)
            pc = np.ndarray(c_src.shape, dtype=np.int64, buffer=sc.buf)
            pv.setflags(write=False)
            pw.setflags(write=False)
            pc.setflags(write=False)

            pm = ProblemModel(
                problem_id=model.problem_id,
                dataset=model.dataset,
                items=model.items,
                dim=model.dim,
                values=pv,
                weights=pw,
                capacities=pc,
                best_known=model.best_known,
            )
            models[(dataset, pid)] = pm
            packs.append(
                ProblemShmPack(
                    dataset=dataset,
                    problem_id=pid,
                    shm_name_values=sv.name,
                    shm_name_weights=sw.name,
                    shm_name_capacities=sc.name,
                    shape_values=tuple(int(x) for x in v_src.shape),
                    shape_weights=(int(w_src.shape[0]), int(w_src.shape[1])),
                    shape_capacities=tuple(int(x) for x in c_src.shape),
                    items=model.items,
                    dim=model.dim,
                    best_known=model.best_known,
                )
            )

        return ProblemBank(models=models, shm_blocks=shm_blocks, packs=tuple(packs))

    def get(self, dataset: str, problem_id: str) -> ProblemModel:
        try:
            return self._models[(dataset, problem_id)]
        except KeyError as exc:
            raise FileNotFoundError(
                f"Problem not in bank for this experiment: dataset={dataset!r} problem_id={problem_id!r}"
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
