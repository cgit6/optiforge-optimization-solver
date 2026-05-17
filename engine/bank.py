"""題庫掃描、Catalog、CatalogSummary，以及以 shared_memory 共用的 ProblemBank。"""

from __future__ import annotations

from dataclasses import dataclass
from multiprocessing.shared_memory import SharedMemory
from pathlib import Path
from typing import Any

from ..problem import Problem
from ..problem.registry import ProblemRegistry, ProblemShmPack, ProblemTypeSpec, registryFromSpecs
from .models import ExperimentSpec
from .repository import ProblemRepository

_worker_problem_view: Any | None = None


@dataclass(frozen=True)
class ProblemCatalogEntry:
    problem_type: str
    dataset: str
    problem_id: str
    filePath: str


@dataclass(frozen=True)
class CatalogSummary:
    problem_types: tuple[str, ...]
    datasets: tuple[str, ...]
    problems_by_dataset: tuple[tuple[str, tuple[str, ...]], ...]

    def problems_in(self, dataset: str) -> tuple[str, ...]:
        for ds, pids in self.problems_by_dataset:
            if ds == dataset:
                return pids
        return tuple()


class ProblemWorkerView:
    def __init__(self, packs: tuple[ProblemShmPack, ...], problem_specs: tuple[ProblemTypeSpec, ...]) -> None:
        self._registry = registryFromSpecs(problem_specs)
        self._models: dict[tuple[str, str, str], Problem] = {}
        self._shms: list[SharedMemory] = []
        for pack in packs:
            spec = self._registry.get(pack.problem_type)
            model = spec.attach_shm_pack(pack, self._shms)
            self._registry.validate_model(model, pack.problem_type)
            self._models[(pack.problem_type, pack.dataset, pack.problem_id)] = model

    def get(self, dataset: str, problem_id: str, problem_type: str = "mkp") -> Problem:
        try:
            return self._models[(problem_type, dataset, problem_id)]
        except KeyError as exc:
            raise FileNotFoundError(
                "Problem not in shared bank: "
                f"problem_type={problem_type!r} dataset={dataset!r} problem_id={problem_id!r}"
            ) from exc


def configure_problem_bank_worker(
    packs: tuple[ProblemShmPack, ...],
    problem_specs: tuple[ProblemTypeSpec, ...],
) -> None:
    global _worker_problem_view
    _worker_problem_view = ProblemWorkerView(packs, problem_specs)


def get_worker_problem_bank() -> ProblemWorkerView:
    if _worker_problem_view is None:
        raise RuntimeError("worker ProblemBank view is not configured")
    return _worker_problem_view

# 問題1: problem_type 不是問題類型是題庫名稱，
def scanProblemCatalog(
    problem_root: Path,
    registry: ProblemRegistry,
) -> tuple[list[ProblemCatalogEntry], CatalogSummary]:
    if not problem_root.is_dir():
        raise FileNotFoundError(f"problem_root is not a directory: {problem_root}")

    entries: list[ProblemCatalogEntry] = [] # 
    by_dataset: dict[str, list[str]] = {} # 
    problem_types: set[str] = set() # 
    known_problem_types = set(registry.list_problem_types())

    # 1. 遍歷所有題庫
    for first_level in sorted(p for p in problem_root.iterdir() if p.is_dir()):
        # 獲取子資料夾做為 問題類型名稱
        problem_type = first_level.name
        if problem_type not in known_problem_types:
            continue
        
        # 2. 獲取第二層資料夾清單做為題庫名稱
        for dataset_dir in sorted(p for p in first_level.iterdir() if p.is_dir()):
            dataset = dataset_dir.name
            by_dataset.setdefault(dataset, [])
            problem_types.add(problem_type)

            # 3. 獲取資料夾中的每一個題目檔案做成題目摘要
            for yaml_path in sorted(dataset_dir.glob("*.yaml")):
                
                # 檔名
                problem_id = yaml_path.stem 
                # 相對路徑
                rel = str(yaml_path.relative_to(problem_root)).replace("\\", "/")
                # 添加題目摘要
                entries.append(
                    ProblemCatalogEntry(
                        problem_type=problem_type, # 問題類型
                        dataset=dataset, # 題庫名稱
                        problem_id=problem_id, # 檔名
                        filePath=rel, # 相對路徑
                    )
                )

                # 題庫索引
                by_dataset[dataset].append(problem_id)

    # 獲取每個 dataset 和題目 id 清單
    # 把 題庫名稱做排序(為什麼?)
    # 去重把重複的 problem_id 去掉
    # 對題目 id 清單做排序
    # 轉成 tuple
    pbd = tuple((ds, tuple(sorted(set(pids)))) for ds, pids in sorted(by_dataset.items()))
    # 
    summary = CatalogSummary(
        problem_types=tuple(sorted(problem_types)),
        datasets=tuple(sorted(by_dataset.keys())),
        problems_by_dataset=pbd,
    )
    return entries, summary


def validate_catalog_entries(repository: ProblemRepository, entries: list[ProblemCatalogEntry]) -> None:
    """載入並驗證 catalog 內每一題（全題庫）；CI 或維護工具可呼叫。

    日常 `engine.build` 改用 :func:`validate_spec_problems_in_repository` 以避免對未使用題目重複 I/O。
    """
    for entry in entries:
        repository.load(entry.dataset, entry.problem_id, entry.problem_type)


def validate_spec_problems_in_repository(repository: ProblemRepository, spec: ExperimentSpec) -> None:
    """僅對本次實驗的題目呼叫 ``repository.load``（語意與舊版全量驗證的子集一致）。"""
    seen: set[str] = set() # 以讀的題目清單
    for pid in spec.problem_ids:
        seen.add(pid) # 更新已讀題目清單
        # 讀 yaml 檔案
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
        models: dict[tuple[str, str, str], Problem],
        shm_blocks: list[SharedMemory],
        packs: tuple[ProblemShmPack, ...],
        problem_specs: tuple[ProblemTypeSpec, ...],
    ) -> None:
        self._models = models
        self._shm_blocks = shm_blocks
        self._packs = packs
        self._problem_specs = problem_specs

    @staticmethod
    def build(
        *,
        repository: ProblemRepository,
        spec: ExperimentSpec,
        registry: ProblemRegistry,
    ) -> ProblemBank:
        uniq: dict[tuple[str, str, str], None] = {}
        for pid in spec.problem_ids:
            uniq[(spec.problem_type, spec.dataset, pid)] = None

        models: dict[tuple[str, str, str], Problem] = {}
        shm_blocks: list[SharedMemory] = []
        packs: list[ProblemShmPack] = []

        for problem_type, dataset, pid in sorted(uniq.keys()):
            model = repository.load(dataset, pid, problem_type)
            problem_spec = registry.get(problem_type)
            pack = problem_spec.make_shm_pack(model, shm_blocks)
            models[(problem_type, dataset, pid)] = model
            packs.append(pack)

        return ProblemBank(
            models=models,
            shm_blocks=shm_blocks,
            packs=tuple(packs),
            problem_specs=registry.specs(),
        )

    def get(self, dataset: str, problem_id: str, problem_type: str = "mkp") -> Problem:
        try:
            return self._models[(problem_type, dataset, problem_id)]
        except KeyError as exc:
            raise FileNotFoundError(
                "Problem not in bank for this experiment: "
                f"problem_type={problem_type!r} dataset={dataset!r} problem_id={problem_id!r}"
            ) from exc

    def export_worker_packs(self) -> tuple[ProblemShmPack, ...]:
        return self._packs

    def export_worker_problem_specs(self) -> tuple[ProblemTypeSpec, ...]:
        return self._problem_specs

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
