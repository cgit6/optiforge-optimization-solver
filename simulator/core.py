from __future__ import annotations

import copy
import sys
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from dataclasses import dataclass
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
from ..solver.BSMA import BSMASolver
from ..solver.BSMA_numba import BSMANumbaSolver
from ..solver.BSCA import BSCASolver
from ..solver.BSCA_numba import BSCANumbaSolver
from ..solver.BSCASMA import BRLSMASCATestSolver
from ..solver.BSCASMA_numba import BRLSMASCATestNumbaSolver
from ..solver.nearest_neighbor_tsp import NearestNeighborTSPSolver
from ..solver.registry import SolverRegistry, StubMaxIterationsSolver
from ..solver.sma_mkp_modular import SMAMKPModularV1Solver
from ..solver.sma_tsp_modular import SMATSPModularV1Solver
from ..solver.validator import ValidationReport, Validator



_PROCESS_SAFE_SOLVERS = {
    "bsma",
    "bsma_numba",
    "bsca",
    "bsca_numba",
    "brlsmasca",
    "brlsmasca_numba",
    "sma_mkp_modular_v1",
    "sma_tsp_modular_v1",
    "nn_tsp_v1",
    "stub_solver",
}

_worker_solver_configs: dict[str, dict[str, Any]] | None = None
_worker_progress_queue: Any | None = None


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


def _configure_curriculum_process_worker(
    packs: tuple[ProblemShmPack, ...],
    solver_configs: dict[str, dict[str, Any]],
    progress_queue: Any | None = None,
) -> None:
    global _worker_solver_configs, _worker_progress_queue
    configure_problem_bank_worker(packs)
    _worker_solver_configs = {k: copy.deepcopy(v) for k, v in solver_configs.items()}
    _worker_progress_queue = progress_queue


def _progress_bar(total: int, desc: str) -> tqdm:
    return tqdm(
        total=total,
        desc=desc,
        unit="task",
        dynamic_ncols=True,
        disable=not sys.stderr.isatty(),
    )


def _seed_by_triple(spec: ExperimentSpec) -> dict[tuple[str, str, int], int]:
    """依 (problem_idx, solver_idx, repeat) 典範排序後 spawn，與 grid 巢狀迴圈順序一致。"""
    p_idx = {p: i for i, p in enumerate(spec.problem_ids)}
    s_idx = {s: i for i, s in enumerate(spec.solver_ids)}
    triples = [
        (p, s, r)
        for p in spec.problem_ids
        for s in spec.solver_ids
        for r in range(spec.repeat)
    ]
    triples.sort(key=lambda t: (p_idx[t[0]], s_idx[t[1]], t[2]))
    n = len(triples)
    seed_sequences = np.random.SeedSequence(spec.seed).spawn(n)
    seeds: dict[tuple[str, str, int], int] = {}
    for seq, (p, s, r) in zip(seed_sequences, triples):
        seeds[(p, s, r)] = int(seq.generate_state(1, dtype=np.uint64)[0])
    return seeds

# 
def _build_process_local_registry() -> SolverRegistry:
    registry = SolverRegistry()
    registry.register("stub_solver", lambda: StubMaxIterationsSolver())
    registry.register("bsma", lambda: BSMASolver())
    registry.register("bsma_numba", lambda: BSMANumbaSolver())
    registry.register("bsca", lambda: BSCASolver())
    registry.register("bsca_numba", lambda: BSCANumbaSolver())
    registry.register("brlsmasca", lambda: BRLSMASCATestSolver())
    registry.register("brlsmasca_numba", lambda: BRLSMASCATestNumbaSolver())
    registry.register("sma_mkp_modular_v1", lambda: SMAMKPModularV1Solver())
    registry.register("sma_tsp_modular_v1", lambda: SMATSPModularV1Solver())
    registry.register("nn_tsp_v1", lambda: NearestNeighborTSPSolver())
    return registry



def _run_curriculum_line_process(line_tasks: list[RunTask]) -> list[SolveResult]:
    """在子行程中執行一條 repeat 線，線內保持順序；題目由 SHM ProblemBank 提供。"""
    bank = get_worker_problem_bank() # 取得 worker 問題庫
    if _worker_solver_configs is None:
        raise RuntimeError("curriculum worker solver_configs is not configured")
    registry = _build_process_local_registry()
    solve_results: list[SolveResult] = []

    for task in line_tasks:
        problem = bank.get(task.dataset, task.problem_id, task.problem_type)
        solver_config = copy.deepcopy(_worker_solver_configs[task.solver_id])
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
        problem_bank: ProblemBank,
        solver_registry: SolverRegistry,
        solver_configs: SolverConfigsSnapshot,
        validator: Validator,
    ) -> None:
        self._problem_bank = problem_bank # 問題庫
        self._solver_registry = solver_registry # 求解器註冊表
        self._solver_configs = solver_configs # engine 預載之 solver YAML（執行期不讀檔）
        self._validator = validator # 驗證器

    def close(self) -> None:
        """釋放 `ProblemBank` 的 shared memory（實驗結束後應呼叫）。"""
        self._problem_bank.close()

    # 執行單個任務
    def run_task(self, task: RunTask) -> SimulatorRunRow:
        problem = self._problem_bank.get(task.dataset, task.problem_id, task.problem_type)
        solver_config = self._solver_configs.get(task.solver_id)
        rng = np.random.default_rng(task.seed)

        solver = self._solver_registry.create(task.solver_id)
        solve_result = solver.solve(problem, solver_config, rng)

        validation_report = self._validator.validate(problem, solve_result)
        return SimulatorRunRow(
            task=task,
            solve_result=solve_result,
            validation_report=validation_report,
        )

    def expand_tasks(self, spec: ExperimentSpec) -> list[RunTask]:
        seeds = _seed_by_triple(spec)
        tasks: list[RunTask] = []

        if spec.execution_mode == "grid":
            for problem_id in spec.problem_ids:
                for solver_id in spec.solver_ids:
                    for repeat_index in range(spec.repeat):
                        tasks.append(
                            RunTask(
                                problem_id=problem_id,
                                dataset=spec.dataset,
                                problem_type=spec.problem_type,
                                solver_id=solver_id,
                                repeat_index=repeat_index,
                                seed=seeds[(problem_id, solver_id, repeat_index)],
                            )
                        )
        else:
            for solver_id in spec.solver_ids:
                for repeat_index in range(spec.repeat):
                    for problem_id in spec.problem_ids:
                        tasks.append(
                            RunTask(
                                problem_id=problem_id,
                                dataset=spec.dataset,
                                problem_type=spec.problem_type,
                                solver_id=solver_id,
                                repeat_index=repeat_index,
                                seed=seeds[(problem_id, solver_id, repeat_index)],
                            )
                        )
        return tasks

    def run_sequential(self, spec: ExperimentSpec) -> SimulatorResult:
        """在主執行緒依 `expand_tasks` 順序逐筆呼叫 `run_task`（多題或多 repeat 時仍是一筆接一筆）。"""
        tasks = self.expand_tasks(spec)
        rows: list[SimulatorRunRow] = []

        # 進度條顯示
        with _progress_bar(total=len(tasks), desc=f"{spec.experiment_id} sequential") as progress:
            for task in tasks:
                rows.append(self.run_task(task))
                progress.update(1)
        return SimulatorResult(rows=tuple(rows))

    def _can_use_process_workers(self, spec: ExperimentSpec) -> bool:
        if not set(spec.solver_ids).issubset(_PROCESS_SAFE_SOLVERS):
            return False
        return set(spec.solver_ids).issubset(self._solver_configs.solver_ids())

    def _build_rows_from_solve_results(
        self,
        tasks: list[RunTask],
        lines: list[list[RunTask]],
        per_line_results: list[list[SolveResult]],
    ) -> list[SimulatorRunRow]:
        """以 zip(lines, chunks) 對齊 RunTask 與 SolveResult（攤平順序與 expand_tasks 不同，不可 zip(tasks, flat)）。"""
        by_triple: dict[tuple[str, str, str, int], SolveResult] = {}
        for line, chunk in zip(lines, per_line_results, strict=True):
            if len(line) != len(chunk):
                raise RuntimeError(
                    f"worker 回傳筆數與該線任務數不一致：{len(line)=} {len(chunk)=}"
                )
            for task, solve_result in zip(line, chunk, strict=True):
                by_triple[(task.problem_type, task.problem_id, task.solver_id, task.repeat_index)] = solve_result
        rows: list[SimulatorRunRow] = []
        for task in tasks:
            solve_result = by_triple[(task.problem_type, task.problem_id, task.solver_id, task.repeat_index)]
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

    def run_batch(self, spec: ExperimentSpec) -> SimulatorResult:
        """僅處理 `worker_curriculum` 下以 `repeat` 條 worker 線並行（線內仍串行）；必須使用 ProcessPoolExecutor。"""
        if not self._can_use_process_workers(spec):
            unsafe = sorted(set(spec.solver_ids) - _PROCESS_SAFE_SOLVERS)
            missing = sorted(set(spec.solver_ids) - self._solver_configs.solver_ids())
            parts = [
                "worker_curriculum 的 run_batch 必須以 ProcessPoolExecutor 執行，目前條件不滿足而中止。",
                f"允許的 solver_id：{sorted(_PROCESS_SAFE_SOLVERS)}。",
            ]
            if unsafe:
                parts.append(f"不在允許清單的 solver：{unsafe}。")
            if missing:
                parts.append(f"solver 設定快照缺少：{missing}（請以相同 spec 呼叫 engine.build）。")
            raise RuntimeError(" ".join(parts))

        tasks = self.expand_tasks(spec)
        # 依 repeat_index 分線
        lines: list[list[RunTask]] = [[] for _ in range(spec.repeat)]
        for task in tasks:
            lines[task.repeat_index].append(task)

        worker_cfgs = self._solver_configs.to_worker_init_dict()
        packs = self._problem_bank.export_worker_packs()
        per_line_results: list[list[SolveResult] | None] = [None] * len(lines)
        # 作業系統
        if sys.platform == "win32":
            mp_context = get_context("spawn") # windows 下使用 spawn 模式
        else:
            mp_context = get_context("fork") # 其他平台使用 fork 模式
        
        progress_queue = mp_context.Queue()
        try:
            with _progress_bar(total=len(tasks), desc=f"{spec.experiment_id} batch") as progress:
                # 建立 ProcessPoolExecutor，並行執行 _run_curriculum_line_process
                with ProcessPoolExecutor(
                    max_workers=spec.repeat,
                    mp_context=mp_context,
                    initializer=_configure_curriculum_process_worker,
                    initargs=(packs, worker_cfgs, progress_queue),
                ) as pool:
                    future_to_index = {
                        pool.submit(_run_curriculum_line_process, line): idx
                        for idx, line in enumerate(lines)
                    }
                    pending = set(future_to_index)
                    while pending:
                        self._drain_progress_queue(progress_queue, progress)
                        done, pending = wait(pending, timeout=0.1, return_when=FIRST_COMPLETED)
                        for future in done:
                            line_idx = future_to_index[future]
                            per_line_results[line_idx] = future.result()
                    self._drain_progress_queue(progress_queue, progress)
        finally:
            progress_queue.close()
            progress_queue.join_thread()

        ordered_results: list[list[SolveResult]] = []
        for idx, result in enumerate(per_line_results):
            if result is None:
                raise RuntimeError(f"worker line did not return results: line_idx={idx}")
            ordered_results.append(result)
        rows = self._build_rows_from_solve_results(tasks, lines, ordered_results)
        return SimulatorResult(rows=tuple(rows))

    @staticmethod
    def _drain_progress_queue(progress_queue: Any, progress: tqdm) -> None:
        while True:
            try:
                progress_queue.get_nowait()
            except Empty:
                return
            progress.update(1)
