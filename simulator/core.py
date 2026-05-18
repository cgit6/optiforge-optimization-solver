from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from dataclasses import dataclass, field
from multiprocessing import get_context
from queue import Empty
from typing import Any

import numpy as np
from tqdm import tqdm

from ..engine.models import ExperimentSpec, SolveResult, RunTask
from ..engine.configs import SolverConfigsSnapshot
from ..engine.bank import (
    ProblemBank,
    ProblemShmPack,
    configure_problem_bank_worker,
    get_worker_problem_bank,
)
from ..problem.registry import ProblemTypeSpec
from ..solver.BSMA import BSMASolver
from ..solver.BSMA_numba import BSMANumbaSolver
from ..solver.BSMA_numba_v2 import BSMANumbaSolver as BSMANumbaSolverV2
from ..solver.BSCA import BSCASolver
from ..solver.BSCA_numba import BSCANumbaSolver
from ..solver.BSCA_numba_v2 import BSCANumbaSolver as BSCANumbaSolverV2
from ..solver.BSCASMA import BRLSMASCATestSolver
from ..solver.BSCASMA_numba import BRLSMASCATestNumbaSolver
from ..solver.BSCASMA_numba_v2 import BRLSMASCATestNumbaSolver as BRLSMASCATestNumbaSolverV2
from ..solver.nearest_neighbor_tsp import NearestNeighborTSPSolver
from ..solver.registry import SolverRegistry, StubMaxIterationsSolver
from ..solver.sma_mkp_modular import SMAMKPModularV1Solver
from ..solver.sma_tsp_modular import SMATSPModularV1Solver
from ..solver.validator import ValidationReport, Validator



_PROCESS_SAFE_SOLVERS = {
    "bsma",
    "bsma_numba",
    "bsma_numba_v2",
    "bsca",
    "bsca_numba",
    "bsca_numba_v2",
    "brlsmasca",
    "brlsmasca_numba",
    "brlsmasca_numba_v2",
    "sma_mkp_modular_v1",
    "sma_tsp_modular_v1",
    "nn_tsp_v1",
    "stub_solver",
}

_worker_solver_configs: dict[tuple[str, int], dict[str, Any]] | None = None
_worker_progress_queue: Any | None = None
_TASK_SEED_VERSION = "mkp.task-seed.v1"


@dataclass(frozen=True)
class SimulatorRunRow:
    """單筆模擬結果：任務、求解輸出與驗證結果三者一組。"""

    task: RunTask
    solve_result: SolveResult
    validation_report: ValidationReport


@dataclass(frozen=True)
class SimulatorResult:
    """整個批次的模擬結果：依執行順序保存所有 SimulatorRunRow。"""

    rows: tuple[SimulatorRunRow, ...]
    variant_params: dict[tuple[str, int], dict[str, Any]] = field(default_factory=dict)


def _configure_curriculum_process_worker(
    packs: tuple[ProblemShmPack, ...],
    problem_specs: tuple[ProblemTypeSpec, ...],
    solver_configs: dict[tuple[str, int], dict[str, Any]],
    progress_queue: Any | None = None,
) -> None:
    global _worker_solver_configs, _worker_progress_queue
    configure_problem_bank_worker(packs, problem_specs)
    _worker_solver_configs = {k: copy.deepcopy(v) for k, v in solver_configs.items()}
    _worker_progress_queue = progress_queue


def _progress_bar(total: int, desc: str, *, enabled: bool = True) -> tqdm:
    return tqdm(
        total=total,
        desc=desc,
        unit="task",
        dynamic_ncols=True,
        disable=(not enabled) or (not sys.stderr.isatty()),
    )


def _seed_by_task(
    spec: ExperimentSpec,
    solver_configs: SolverConfigsSnapshot,
    *,
    base_seed: int,
) -> dict[tuple[str, str, int, int], int]:
    """依 task identity 派生 seed，避免其他 solver/params 數量改變造成 seed 位移。"""
    base_seed = _validate_base_seed(base_seed)
    seeds: dict[tuple[str, str, int, int], int] = {}
    for problem_id in spec.problem_ids:
        for solver_id in spec.solver_ids:
            for param_set_index in solver_configs.param_set_indices(solver_id):
                solver_config = solver_configs.get(solver_id, param_set_index)
                for repeat_index in range(spec.repeat):
                    seeds[(problem_id, solver_id, param_set_index, repeat_index)] = _stable_task_seed(
                        base_seed=base_seed,
                        problem_type=spec.problem_type,
                        dataset=spec.dataset,
                        problem_id=problem_id,
                        solver_id=solver_id,
                        params=solver_config["params"],
                        repeat_index=repeat_index,
                    )
    return seeds


def _validate_base_seed(seed: int) -> int:
    seed = int(seed)
    if seed < 0:
        raise ValueError("seed must be >= 0.")
    return seed


def _stable_task_seed(
    *,
    base_seed: int,
    problem_type: str,
    dataset: str,
    problem_id: str,
    solver_id: str,
    params: dict[str, Any],
    repeat_index: int,
) -> int:
    payload = {
        "version": _TASK_SEED_VERSION,
        "base_seed": int(base_seed),
        "problem_type": problem_type,
        "dataset": dataset,
        "problem_id": problem_id,
        "solver_id": solver_id,
        "params": params,
        "repeat_index": int(repeat_index),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.blake2b(raw, digest_size=8).digest()
    return int.from_bytes(digest, byteorder="little", signed=False)

# 
def _build_process_local_registry() -> SolverRegistry:
    registry = SolverRegistry()
    registry.register("stub_solver", lambda: StubMaxIterationsSolver())
    registry.register("bsma", lambda: BSMASolver())
    registry.register("bsma_numba", lambda: BSMANumbaSolver())
    registry.register("bsma_numba_v2", lambda: BSMANumbaSolverV2())
    registry.register("bsca", lambda: BSCASolver())
    registry.register("bsca_numba", lambda: BSCANumbaSolver())
    registry.register("bsca_numba_v2", lambda: BSCANumbaSolverV2())
    registry.register("brlsmasca", lambda: BRLSMASCATestSolver())
    registry.register("brlsmasca_numba", lambda: BRLSMASCATestNumbaSolver())
    registry.register("brlsmasca_numba_v2", lambda: BRLSMASCATestNumbaSolverV2())
    registry.register("sma_mkp_modular_v1", lambda: SMAMKPModularV1Solver())
    registry.register("sma_tsp_modular_v1", lambda: SMATSPModularV1Solver())
    registry.register("nn_tsp_v1", lambda: NearestNeighborTSPSolver())
    return registry



def _run_task_chunk_process(tasks: list[RunTask]) -> list[SolveResult]:
    """在子行程中執行一批 task；題目由 SHM ProblemBank 提供。"""
    bank = get_worker_problem_bank() # 取得 worker 問題庫
    if _worker_solver_configs is None:
        raise RuntimeError("curriculum worker solver_configs is not configured")
    registry = _build_process_local_registry()
    solve_results: list[SolveResult] = []

    for task in tasks:
        problem = bank.get(task.dataset, task.problem_id, task.problem_type)
        solver_config = copy.deepcopy(_worker_solver_configs[(task.solver_id, task.param_set_index)])
        rng = np.random.default_rng(task.seed) # 建立隨機數生成器
        solver = registry.create(task.solver_id) # 建立 solver
        solve_result = solver.solve(problem, solver_config, rng) # 執行 solver
        solve_results.append(solve_result)
        if _worker_progress_queue is not None:
            _worker_progress_queue.put(1)
    return solve_results


class Simulator:
    """執行單筆任務或整批任務，回傳 SimulatorResult；輸出檔案的職責由 stat 模組接手。"""

    def __init__(
        self,
        *,
        spec: ExperimentSpec,
        problem_bank: ProblemBank,
        solver_registry: SolverRegistry,
        solver_configs: SolverConfigsSnapshot,
        validator: Validator,
    ) -> None:
        self._spec = spec # 實驗規格
        self._problem_bank = problem_bank # 問題庫
        self._solver_registry = solver_registry # 求解器註冊表
        self._solver_configs = solver_configs # engine 預載之 solver YAML
        self._validator = validator # 驗證器

    def close(self) -> None:
        """釋放 `ProblemBank` 的 shared memory（實驗結束後應呼叫）。"""
        self._problem_bank.close()

    # 執行單個任務
    def run_task(self, task: RunTask) -> SimulatorRunRow:
        problem = self._problem_bank.get(task.dataset, task.problem_id, task.problem_type)
        solver_config = self._solver_configs.get(task.solver_id, task.param_set_index)
        rng = np.random.default_rng(task.seed)

        solver = self._solver_registry.create(task.solver_id)
        solve_result = solver.solve(problem, solver_config, rng)

        validation_report = self._validator.validate(problem, solve_result)
        return SimulatorRunRow(
            task=task,
            solve_result=solve_result,
            validation_report=validation_report,
        )

    def expand_tasks(self, *, seed: int) -> list[RunTask]:
        """把一份高階的實驗設定 ExperimentSpec，展開成一串可以真的執行的單筆任務 RunTask"""
        spec = self._spec # 實驗規格
        seeds = _seed_by_task(spec, self._solver_configs, base_seed=seed)
        tasks: list[RunTask] = []

        for problem_id in spec.problem_ids:
            for solver_id in spec.solver_ids:
                for param_set_index in self._solver_configs.param_set_indices(solver_id):
                    for repeat_index in range(spec.repeat):
                        tasks.append(
                            RunTask(
                                problem_id=problem_id,
                                dataset=spec.dataset,
                                problem_type=spec.problem_type,
                                solver_id=solver_id,
                                repeat_index=repeat_index,
                                seed=seeds[(problem_id, solver_id, param_set_index, repeat_index)],
                                param_set_index=param_set_index,
                            )
                        )
        return tasks

    def _variant_params(self) -> dict[tuple[str, int], dict[str, Any]]:
        return {
            (solver_id, param_set_index): copy.deepcopy(
                self._solver_configs.get(solver_id, param_set_index)["params"]
            )
            for solver_id in self._spec.solver_ids
            for param_set_index in self._solver_configs.param_set_indices(solver_id)
        }

    def run_sequential(self, *, seed: int, show_progress: bool = True) -> SimulatorResult:
        """在主執行緒依 `expand_tasks` 順序逐筆呼叫 `run_task`（多題或多 repeat 時仍是一筆接一筆）。"""
        spec = self._spec
        tasks = self.expand_tasks(seed=seed) 
        rows: list[SimulatorRunRow] = []

        # 進度條顯示
        with _progress_bar(
            total=len(tasks),
            desc=f"{spec.experiment_name} sequential",
            enabled=show_progress,
        ) as progress:
            for task in tasks:
                rows.append(self.run_task(task))
                progress.update(1)
        return SimulatorResult(rows=tuple(rows), variant_params=self._variant_params())

    def _can_use_process_workers(self) -> bool:
        spec = self._spec
        if not set(spec.solver_ids).issubset(_PROCESS_SAFE_SOLVERS):
            return False
        return set(spec.solver_ids).issubset(self._solver_configs.solver_ids())

    def _build_rows_from_solve_results(
        self,
        tasks: list[RunTask],
        chunks: list[list[RunTask]],
        per_chunk_results: list[list[SolveResult]],
    ) -> list[SimulatorRunRow]:
        """以 zip(chunks, results) 對齊 RunTask 與 SolveResult（攤平順序與 expand_tasks 不同）。"""
        by_triple: dict[tuple[str, str, str, int, int], SolveResult] = {}
        for task_chunk, result_chunk in zip(chunks, per_chunk_results, strict=True):
            if len(task_chunk) != len(result_chunk):
                raise RuntimeError(
                    f"worker 回傳筆數與 task 數不一致：{len(task_chunk)=} {len(result_chunk)=}"
                )
            for task, solve_result in zip(task_chunk, result_chunk, strict=True):
                by_triple[
                    (
                        task.problem_type,
                        task.problem_id,
                        task.solver_id,
                        task.param_set_index,
                        task.repeat_index,
                    )
                ] = solve_result
        rows: list[SimulatorRunRow] = []
        for task in tasks:
            solve_result = by_triple[
                (
                    task.problem_type,
                    task.problem_id,
                    task.solver_id,
                    task.param_set_index,
                    task.repeat_index,
                )
            ]
            problem = self._problem_bank.get(task.dataset, task.problem_id, task.problem_type)
            validation_report = self._validator.validate(problem, solve_result)
            rows.append(
                SimulatorRunRow(
                    task=task,
                    solve_result=solve_result,
                    validation_report=validation_report,
                )
            )
        return rows

    def run_batch(self, *, seed: int, show_progress: bool = True) -> SimulatorResult:
        """以 `worker_count` 個 process workers 並行執行展開後的任務。"""
        spec = self._spec
        if not self._can_use_process_workers():
            unsafe = sorted(set(spec.solver_ids) - _PROCESS_SAFE_SOLVERS)
            missing = sorted(set(spec.solver_ids) - self._solver_configs.solver_ids())
            parts = [
                "run_batch 必須以 ProcessPoolExecutor 執行，目前條件不滿足而中止。",
                f"允許的 solver_id：{sorted(_PROCESS_SAFE_SOLVERS)}。",
            ]
            if unsafe:
                parts.append(f"不在允許清單的 solver：{unsafe}。")
            if missing:
                parts.append(f"solver 設定快照缺少：{missing}（請以相同 spec 呼叫 engine.build）。")
            raise RuntimeError(" ".join(parts))

        tasks = self.expand_tasks(seed=seed)
        max_workers = min(spec.worker_count, len(tasks), os.cpu_count() or 1)
        chunks: list[list[RunTask]] = [[] for _ in range(max_workers)]
        for index, task in enumerate(tasks):
            chunks[index % max_workers].append(task)
        chunks = [chunk for chunk in chunks if chunk]

        worker_cfgs = self._solver_configs.to_worker_init_dict()
        packs = self._problem_bank.export_worker_packs()
        problem_specs = self._problem_bank.export_worker_problem_specs()
        per_chunk_results: list[list[SolveResult] | None] = [None] * len(chunks)
        # 作業系統
        if sys.platform == "win32":
            mp_context = get_context("spawn") # windows 下使用 spawn 模式
        else:
            mp_context = get_context("fork") # 其他平台使用 fork 模式

        progress_queue = mp_context.Queue() if show_progress else None
        try:
            with _progress_bar(
                total=len(tasks),
                desc=f"{spec.experiment_name} batch",
                enabled=show_progress,
            ) as progress:
                # 建立 ProcessPoolExecutor，並行執行 _run_task_chunk_process
                with ProcessPoolExecutor(
                    max_workers=max_workers, # 併發數量
                    mp_context=mp_context,
                    initializer=_configure_curriculum_process_worker,
                    initargs=(packs, problem_specs, worker_cfgs, progress_queue),
                ) as pool:
                    future_to_index = {
                        pool.submit(_run_task_chunk_process, chunk): idx
                        for idx, chunk in enumerate(chunks)
                    }
                    pending = set(future_to_index)
                    while pending:
                        if progress_queue is not None:
                            self._drain_progress_queue(progress_queue, progress)
                        done, pending = wait(pending, timeout=0.1, return_when=FIRST_COMPLETED)
                        for future in done:
                            chunk_idx = future_to_index[future]
                            per_chunk_results[chunk_idx] = future.result()
                    if progress_queue is not None:
                        self._drain_progress_queue(progress_queue, progress)
        finally:
            if progress_queue is not None:
                progress_queue.close()
                progress_queue.join_thread()

        ordered_results: list[list[SolveResult]] = []
        for idx, result in enumerate(per_chunk_results):
            if result is None:
                raise RuntimeError(f"worker chunk did not return results: chunk_idx={idx}")
            ordered_results.append(result)
        rows = self._build_rows_from_solve_results(tasks, chunks, ordered_results)
        return SimulatorResult(rows=tuple(rows), variant_params=self._variant_params())

    @staticmethod
    def _drain_progress_queue(progress_queue: Any, progress: tqdm) -> None:
        while True:
            try:
                progress_queue.get_nowait()
            except Empty:
                return
            progress.update(1)
