from __future__ import annotations

import dataclasses
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

import numpy as np

from .bsma_v1_008_solver import BSMAV1008Solver
from .contracts import ExperimentSpec, RunResult, RunTask
from .problem_bank import (
    ProblemBank,
    ProblemShmPack,
    configure_problem_bank_worker,
    get_worker_problem_bank,
)
from .result_writer import ResultEntry, ResultWriter
from .solver_config_loader import SolverConfigLoader
from .solver_registry import SolverRegistry, StubMaxIterationsSolver
from .validator import ValidationReport, Validator

_PROCESS_SAFE_SOLVERS = {"bsma_v1_008", "stub_solver"}

_worker_curriculum_solver_root: str | None = None


def _configure_curriculum_process_worker(
    packs: tuple[ProblemShmPack, ...], solver_root: str
) -> None:
    global _worker_curriculum_solver_root
    configure_problem_bank_worker(packs)
    _worker_curriculum_solver_root = solver_root


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
    seed_sequences = np.random.SeedSequence(spec.base_seed).spawn(n)
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
    bank = get_worker_problem_bank()
    if _worker_curriculum_solver_root is None:
        raise RuntimeError("curriculum worker solver_root is not configured")
    config_loader = SolverConfigLoader(config_root=Path(_worker_curriculum_solver_root))
    registry = _build_process_local_registry()
    run_results: list[RunResult] = []

    for task in line_tasks:
        problem = bank.get(task.dataset, task.problem_id)
        solver_config = config_loader.load(task.solver_id)
        rng = np.random.default_rng(task.seed)
        solver = registry.create(task.solver_id)
        run_result = solver.solve(problem, solver_config, rng)
        if run_result.repeat_index != task.repeat_index:
            run_result = dataclasses.replace(run_result, repeat_index=task.repeat_index)
        run_results.append(run_result)
    return run_results


class Simulator:
    """Run a single task by integrating current core modules."""

    def __init__(
        self,
        *,
        problem_bank: ProblemBank,
        solver_registry: SolverRegistry,
        solver_config_loader: SolverConfigLoader,
        validator: Validator,
        result_writer: ResultWriter,
    ) -> None:
        self._problem_bank = problem_bank
        self._solver_registry = solver_registry
        self._solver_config_loader = solver_config_loader
        self._validator = validator
        self._result_writer = result_writer

    def close(self) -> None:
        """釋放 `ProblemBank` 的 shared memory（實驗結束後應呼叫）。"""
        self._problem_bank.close()

    def run_task(self, task: RunTask) -> tuple[RunResult, ValidationReport, ResultEntry]:
        problem = self._problem_bank.get(task.dataset, task.problem_id)
        solver_config = self._solver_config_loader.load(task.solver_id)
        rng = np.random.default_rng(task.seed)

        solver = self._solver_registry.create(task.solver_id)
        run_result = solver.solve(problem, solver_config, rng)
        if run_result.repeat_index != task.repeat_index:
            run_result = dataclasses.replace(run_result, repeat_index=task.repeat_index)

        validation_report = self._validator.validate(problem, run_result)
        result_entry = self._result_writer.write_run(run_result, validation_report)
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

    def _run_curriculum_line(
        self, line_tasks: list[RunTask]
    ) -> list[tuple[RunResult, ValidationReport, ResultEntry]]:
        return [self.run_task(t) for t in line_tasks]

    def _can_use_process_workers(self, spec: ExperimentSpec) -> bool:
        if not set(spec.solver_ids).issubset(_PROCESS_SAFE_SOLVERS):
            return False
        return hasattr(self._solver_config_loader, "_config_root")

    def _build_rows_from_run_results(
        self, run_results: list[RunResult], tasks: list[RunTask]
    ) -> list[tuple[RunResult, ValidationReport, ResultEntry]]:
        by_triple = {
            (r.problem_id, r.solver_id, r.repeat_index): r
            for r in run_results
        }
        rows: list[tuple[RunResult, ValidationReport, ResultEntry]] = []
        for task in tasks:
            run_result = by_triple[(task.problem_id, task.solver_id, task.repeat_index)]
            problem = self._problem_bank.get(task.dataset, task.problem_id)
            validation_report = self._validator.validate(problem, run_result)
            result_entry = self._result_writer.write_run(run_result, validation_report)
            rows.append((run_result, validation_report, result_entry))
        return rows

    def run_batch(self, spec: ExperimentSpec) -> list[tuple[RunResult, ValidationReport, ResultEntry]]:
        tasks = self.expand_tasks(spec)
        if spec.execution_mode == "worker_curriculum":
            lines: list[list[RunTask]] = [[] for _ in range(spec.repeat)]
            for task in tasks:
                lines[task.repeat_index].append(task)
            if self._can_use_process_workers(spec):
                solver_root = str(getattr(self._solver_config_loader, "_config_root"))
                packs = self._problem_bank.export_worker_packs()
                with ProcessPoolExecutor(
                    max_workers=spec.repeat,
                    initializer=_configure_curriculum_process_worker,
                    initargs=(packs, solver_root),
                ) as pool:
                    per_line_results = pool.map(_run_curriculum_line_process, lines)
                run_results = [item for chunk in per_line_results for item in chunk]
                results = self._build_rows_from_run_results(run_results, tasks)
            else:
                with ThreadPoolExecutor(max_workers=spec.repeat) as pool:
                    per_line = pool.map(self._run_curriculum_line, lines)
                flat: list[tuple[RunResult, ValidationReport, ResultEntry]] = [
                    item for chunk in per_line for item in chunk
                ]
                result_by_triple: dict[tuple[str, str, int], tuple[RunResult, ValidationReport, ResultEntry]] = {
                    (row[0].problem_id, row[0].solver_id, row[0].repeat_index): row for row in flat
                }
                results = [
                    result_by_triple[(t.problem_id, t.solver_id, t.repeat_index)] for t in tasks
                ]
        else:
            results = [self.run_task(t) for t in tasks]
        entries = [entry for _, _, entry in results]
        summary = self._result_writer.build_summary(entries)
        self._result_writer.write_summary(summary)
        return results
