from __future__ import annotations

import numpy as np

from .contracts import ExperimentSpec, RunResult, RunTask
from .problem_repository import ProblemRepository
from .result_writer import ResultEntry, ResultWriter
from .solver_config_loader import SolverConfigLoader
from .solver_registry import SolverRegistry
from .validator import ValidationReport, Validator


class Simulator:
    """Run a single task by integrating current core modules."""

    def __init__(
        self,
        *,
        problem_repository: ProblemRepository,
        solver_registry: SolverRegistry,
        solver_config_loader: SolverConfigLoader,
        validator: Validator,
        result_writer: ResultWriter,
    ) -> None:
        self._problem_repository = problem_repository
        self._solver_registry = solver_registry
        self._solver_config_loader = solver_config_loader
        self._validator = validator
        self._result_writer = result_writer

    def run_task(self, task: RunTask) -> tuple[RunResult, ValidationReport, ResultEntry]:
        problem = self._problem_repository.load(task.dataset, task.problem_id)
        solver_config = self._solver_config_loader.load(task.solver_id)
        rng = np.random.default_rng(task.seed)

        solver = self._solver_registry.create(task.solver_id)
        run_result = solver.solve(problem, solver_config, rng)

        validation_report = self._validator.validate(problem, run_result)
        result_entry = self._result_writer.write_run(run_result, validation_report)
        return run_result, validation_report, result_entry

    def expand_tasks(self, spec: ExperimentSpec) -> list[RunTask]:
        task_defs: list[tuple[str, str, int]] = []
        for problem_id in spec.problem_ids:
            for solver_id in spec.solver_ids:
                for repeat_index in range(spec.repeat):
                    task_defs.append((problem_id, solver_id, repeat_index))

        seed_sequences = np.random.SeedSequence(spec.base_seed).spawn(len(task_defs))
        tasks: list[RunTask] = []
        for idx, (problem_id, solver_id, repeat_index) in enumerate(task_defs):
            seed = int(seed_sequences[idx].generate_state(1, dtype=np.uint64)[0])
            tasks.append(
                RunTask(
                    problem_id=problem_id,
                    dataset=spec.dataset,
                    solver_id=solver_id,
                    repeat_index=repeat_index,
                    seed=seed,
                )
            )
        return tasks

    def run_batch(self, spec: ExperimentSpec) -> list[tuple[RunResult, ValidationReport, ResultEntry]]:
        tasks = self.expand_tasks(spec)
        results: list[tuple[RunResult, ValidationReport, ResultEntry]] = []
        for task in tasks:
            results.append(self.run_task(task))
        return results
