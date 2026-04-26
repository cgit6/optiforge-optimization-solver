from __future__ import annotations

import copy
from concurrent.futures import ProcessPoolExecutor
from typing import Any

import numpy as np

from ..engine.contracts import ExperimentSpec, RunResult, RunTask
from ..engine.solver_configs_snapshot import SolverConfigsSnapshot
from ..engine.problem_bank import (
    ProblemBank,
    ProblemShmPack,
    configure_problem_bank_worker,
    get_worker_problem_bank,
)
from ..solver.bsma_v1_008_solver import BSMAV1008Solver
from ..solver.solver_registry import SolverRegistry, StubMaxIterationsSolver
from ..solver.validator import ValidationReport, Validator
from ..tools.result_writer import ResultEntry, ResultWriter

_PROCESS_SAFE_SOLVERS = {"bsma_v1_008", "stub_solver"}

_worker_solver_configs: dict[str, dict[str, Any]] | None = None


def _configure_curriculum_process_worker(
    packs: tuple[ProblemShmPack, ...],
    solver_configs: dict[str, dict[str, Any]],
) -> None:
    global _worker_solver_configs
    configure_problem_bank_worker(packs)
    _worker_solver_configs = {k: copy.deepcopy(v) for k, v in solver_configs.items()}


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


def _build_process_local_registry() -> SolverRegistry:
    registry = SolverRegistry()
    registry.register("stub_solver", lambda: StubMaxIterationsSolver())
    registry.register("bsma_v1_008", lambda: BSMAV1008Solver())
    return registry



def _run_curriculum_line_process(line_tasks: list[RunTask]) -> list[RunResult]:
    """在子行程中執行一條 repeat 線，線內保持順序；題目由 SHM ProblemBank 提供。"""
    bank = get_worker_problem_bank() # 取得 worker 問題庫
    if _worker_solver_configs is None:
        raise RuntimeError("curriculum worker solver_configs is not configured")
    registry = _build_process_local_registry()
    run_results: list[RunResult] = []

    for task in line_tasks:
        problem = bank.get(task.dataset, task.problem_id)
        solver_config = copy.deepcopy(_worker_solver_configs[task.solver_id])
        rng = np.random.default_rng(task.seed) # 建立隨機數生成器
        solver = registry.create(task.solver_id) # 建立 solver
        run_result = solver.solve(problem, solver_config, rng) # 執行 solver
        run_results.append(run_result)
    return run_results


class Simulator:
    """Run a single task by integrating current core modules."""

    def __init__(
        self,
        *,
        problem_bank: ProblemBank,
        solver_registry: SolverRegistry,
        solver_configs: SolverConfigsSnapshot,
        validator: Validator,
        result_writer: ResultWriter,
    ) -> None:
        self._problem_bank = problem_bank # 問題庫
        self._solver_registry = solver_registry # 求解器註冊表
        self._solver_configs = solver_configs # engine 預載之 solver YAML（執行期不讀檔）
        self._validator = validator # 驗證器
        self._result_writer = result_writer # 結果寫入器

    def close(self) -> None:
        """釋放 `ProblemBank` 的 shared memory（實驗結束後應呼叫）。"""
        self._problem_bank.close()

    # 執行單個任務
    def run_task(self, task: RunTask) -> tuple[RunResult, ValidationReport, ResultEntry]:
        problem = self._problem_bank.get(task.dataset, task.problem_id)
        solver_config = self._solver_configs.get(task.solver_id)
        rng = np.random.default_rng(task.seed)

        solver = self._solver_registry.create(task.solver_id)
        run_result = solver.solve(problem, solver_config, rng)

        validation_report = self._validator.validate(problem, run_result)
        result_entry = self._result_writer.write_run(
            run_result, validation_report, repeat_index=task.repeat_index
        )
        return run_result, validation_report, result_entry

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
                                solver_id=solver_id,
                                repeat_index=repeat_index,
                                seed=seeds[(problem_id, solver_id, repeat_index)],
                            )
                        )
        return tasks

    def _finalize_batch(
        self, results: list[tuple[RunResult, ValidationReport, ResultEntry]]
    ) -> None:
        entries = [entry for _, _, entry in results]
        summary = self._result_writer.build_summary(entries)
        self._result_writer.write_summary(summary)

    def run_sequential(self, spec: ExperimentSpec) -> list[tuple[RunResult, ValidationReport, ResultEntry]]:
        """在主執行緒依 `expand_tasks` 順序逐筆呼叫 `run_task`（多題或多 repeat 時仍是一筆接一筆）。"""
        tasks = self.expand_tasks(spec)
        results: list[tuple[RunResult, ValidationReport, ResultEntry]] = []
        for task in tasks:
            results.append(self.run_task(task))
        self._finalize_batch(results)
        return results

    def _can_use_process_workers(self, spec: ExperimentSpec) -> bool:
        if not set(spec.solver_ids).issubset(_PROCESS_SAFE_SOLVERS):
            return False
        return set(spec.solver_ids).issubset(self._solver_configs.solver_ids())

    def _build_rows_from_run_results(
        self,
        tasks: list[RunTask],
        lines: list[list[RunTask]],
        per_line_results: list[list[RunResult]],
    ) -> list[tuple[RunResult, ValidationReport, ResultEntry]]:
        """以 zip(lines, chunks) 對齊 RunTask 與 RunResult（攤平順序與 expand_tasks 不同，不可 zip(tasks, flat)）。"""
        by_triple: dict[tuple[str, str, int], RunResult] = {}
        for line, chunk in zip(lines, per_line_results, strict=True):
            if len(line) != len(chunk):
                raise RuntimeError(
                    f"worker 回傳筆數與該線任務數不一致：{len(line)=} {len(chunk)=}"
                )
            for task, run_result in zip(line, chunk, strict=True):
                by_triple[(task.problem_id, task.solver_id, task.repeat_index)] = run_result
        rows: list[tuple[RunResult, ValidationReport, ResultEntry]] = []
        for task in tasks:
            run_result = by_triple[(task.problem_id, task.solver_id, task.repeat_index)]
            problem = self._problem_bank.get(task.dataset, task.problem_id)
            validation_report = self._validator.validate(problem, run_result)
            result_entry = self._result_writer.write_run(
                run_result, validation_report, repeat_index=task.repeat_index
            )
            rows.append((run_result, validation_report, result_entry))
        return rows

    def run_batch(self, spec: ExperimentSpec) -> list[tuple[RunResult, ValidationReport, ResultEntry]]:
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
        # 建立 ProcessPoolExecutor，並行執行 _run_curriculum_line_process
        with ProcessPoolExecutor(
            max_workers=spec.repeat,
            initializer=_configure_curriculum_process_worker,
            initargs=(packs, worker_cfgs),
        ) as pool:
            per_line_results = pool.map(_run_curriculum_line_process, lines)
        results = self._build_rows_from_run_results(tasks, lines, list(per_line_results))
        self._finalize_batch(results)
        return results
