from __future__ import annotations

import copy
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from dataclasses import dataclass
from multiprocessing import get_context
from typing import Any, Callable

from ..engine.bank import (
    ProblemBank,
    ProblemShmPack,
    configure_problem_bank_worker,
    get_worker_problem_bank,
)
from ..engine.builders import solverBuilders
from ..engine.configs import SolverConfigsSnapshot
from ..engine.models import ExperimentSpec, RunTask, SolveResult
from ..problem.registry import ProblemTypeSpec
from ..problem.validation import ValidationReport
from ..rng import RngFactory, SeedContext, SeedStrategy
from ..solver.registry import SolverRegistry

ProgressCallback = Callable[[int], None]

_worker_solver_configs: dict[tuple[str, int], dict[str, Any]] | None = None
_worker_rng_factory: RngFactory | None = None
_worker_solver_registry: SolverRegistry | None = None


@dataclass(frozen=True)
class SimulatorRunRow:
    """單筆模擬結果：任務、求解輸出與驗證結果三者一組。"""

    task: RunTask # 任務工單
    solve_result: SolveResult # 結果 
    validation_report: ValidationReport # 驗證


@dataclass(frozen=True)
class MachineResult:
    """單一 solver + 參數組合的模擬結果。"""

    solver_id: str # 求解
    param_set_index: int # 算法設定
    params: dict[str, Any]
    rows: tuple[SimulatorRunRow, ...]

    def __post_init__(self) -> None:
        if not self.solver_id.strip():
            raise ValueError("solver_id cannot be empty.")
        if self.param_set_index < 0:
            raise ValueError("param_set_index must be >= 0.")
        for row in self.rows:
            if row.task.solver_id != self.solver_id:
                raise ValueError(
                    "MachineResult rows must belong to one solver: "
                    f"{row.task.solver_id!r} != {self.solver_id!r}"
                )
            if row.task.param_set_index != self.param_set_index:
                raise ValueError(
                    "MachineResult rows must belong to one param_set_index: "
                    f"{row.task.param_set_index!r} != {self.param_set_index!r}"
                )
        object.__setattr__(self, "params", copy.deepcopy(self.params))


class Machine:
    """執行單一 solver + param_set 的 problem x repeat 任務。"""

    def __init__(
        self,
        *,
        spec: ExperimentSpec,
        solver_id: str,
        param_set_index: int,
        problem_bank: ProblemBank,
        solver_registry: SolverRegistry,
        solver_configs: SolverConfigsSnapshot,
        seed_strategy: SeedStrategy,
        rng_factory: RngFactory,
    ) -> None:
        if solver_id not in spec.solver_ids:
            raise ValueError(f"solver_id={solver_id!r} is not in spec.solver_ids.")
        if param_set_index < 0:
            raise ValueError("param_set_index must be >= 0.")
        self._spec = spec # 實驗規格
        self.solver_id = solver_id # 求解器 ID
        self.param_set_index = param_set_index # 算法參數索引
        self._problem_bank = problem_bank # 題庫名稱
        self._solver_registry = solver_registry
        self._solver_configs = solver_configs
        self._seed_strategy = seed_strategy
        self._rng_factory = rng_factory

    @property
    def task_count(self) -> int:
        return len(self._spec.problem_ids) * self._spec.repeat

    @property
    def params(self) -> dict[str, Any]:
        return copy.deepcopy(
            self._solver_configs.get(self.solver_id, self.param_set_index)["params"]
        )

    def expand_tasks(self, *, base_seed: int | None = None) -> list[RunTask]:
        """產生一系列的工單"""
        spec = self._spec
        resolved_seed = _resolve_base_seed(spec, base_seed)
        context = self._seed_context()
        task_seeds = self._seed_strategy.build_task_seeds(context, base_seed=resolved_seed)

        tasks: list[RunTask] = []
        for problem_id in spec.problem_ids:
            for repeat_index in range(spec.repeat):
                tasks.append(
                    self._make_task(
                        problem_id=problem_id,
                        repeat_index=repeat_index,
                        task_seed=task_seeds[(problem_id, repeat_index)],
                    )
                )
        return tasks

    def expand_task(
        self,
        *,
        problem_id: str,
        repeat_index: int,
        base_seed: int | None = None,
    ) -> RunTask:
        """產生單一工單，供 streaming scheduler 避免展開未來 repeat。"""
        spec = self._spec
        if problem_id not in spec.problem_ids:
            raise ValueError(f"problem_id={problem_id!r} is not in spec.problem_ids.")
        if repeat_index < 0 or repeat_index >= spec.repeat:
            raise ValueError(f"repeat_index out of range: {repeat_index!r}.")
        resolved_seed = _resolve_base_seed(spec, base_seed)
        task_seed = self._seed_strategy.build_task_seed(
            self._seed_context(),
            base_seed=resolved_seed,
            problem_id=problem_id,
            repeat_index=repeat_index,
        )
        return self._make_task(
            problem_id=problem_id,
            repeat_index=repeat_index,
            task_seed=task_seed,
        )

    def _seed_context(self) -> SeedContext:
        spec = self._spec
        return SeedContext(
            problem_type=spec.problem_type,
            dataset=spec.dataset,
            problem_ids=spec.problem_ids,
            repeat=spec.repeat,
        )

    def _make_task(self, *, problem_id: str, repeat_index: int, task_seed: int) -> RunTask:
        spec = self._spec
        return RunTask(
            problem_id=problem_id,
            dataset=spec.dataset,
            problem_type=spec.problem_type,
            solver_id=self.solver_id,
            repeat_index=repeat_index,
            task_seed=task_seed,
            param_set_index=self.param_set_index,
        )

    def run_task(self, task: RunTask) -> SimulatorRunRow:
        """執行"""
        if task.solver_id != self.solver_id or task.param_set_index != self.param_set_index:
            raise ValueError(
                "Machine can only run its own variant: "
                f"machine=({self.solver_id!r}, {self.param_set_index!r}) "
                f"task=({task.solver_id!r}, {task.param_set_index!r})"
            )

        problem = self._problem_bank.get(task.dataset, task.problem_id, task.problem_type)
        solver_config = self._solver_configs.get(task.solver_id, task.param_set_index)
        solver_config["run_seed"] = task.task_seed
        rng = self._rng_factory(task.task_seed)
        solver = self._solver_registry.create(task.solver_id)
        solve_result = solver.solve(problem, solver_config, rng)
        validation_report = problem.validate(solve_result)
        return SimulatorRunRow(
            task=task,
            solve_result=solve_result,
            validation_report=validation_report,
        )

    def run(
        self,
        *,
        base_seed: int | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> MachineResult:
        rows: list[SimulatorRunRow] = []
        for task in self.expand_tasks(base_seed=base_seed):
            rows.append(self.run_task(task))
            if progress_callback is not None:
                progress_callback(1)
        return MachineResult(
            solver_id=self.solver_id,
            param_set_index=self.param_set_index,
            params=self.params,
            rows=tuple(rows),
        )


class MachinePool:
    """以全域 RunTask 為併發單位，並依 Machine variant 回填結果。"""

    def __init__(self, machines: tuple[Machine, ...], *, worker_count: int) -> None:
        if worker_count <= 0:
            raise ValueError("worker_count must be > 0.")
        self._machines = machines
        self._worker_count = worker_count

    def run(
        self,
        *,
        base_seed: int | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> tuple[MachineResult, ...]:
        if not self._machines:
            return ()
        if self._worker_count == 1:
            return tuple(
                machine.run(base_seed=base_seed, progress_callback=progress_callback)
                for machine in self._machines
            )

        tasks_by_machine = [
            (machine, machine.expand_tasks(base_seed=base_seed))
            for machine in self._machines
        ]
        tasks = [task for _, machine_tasks in tasks_by_machine for task in machine_tasks]
        if not tasks:
            return tuple(
                MachineResult(
                    solver_id=machine.solver_id,
                    param_set_index=machine.param_set_index,
                    params=machine.params,
                    rows=(),
                )
                for machine in self._machines
            )

        _assert_process_solvers_registered(tasks)
        max_workers = min(self._worker_count, len(tasks))
        solve_results = self._run_tasks_in_process_pool(tasks, max_workers, progress_callback)
        return self._build_machine_results(tasks_by_machine, solve_results)

    def run_tasks(
        self,
        tasks: list[RunTask],
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> tuple[MachineResult, ...]:
        """執行呼叫端挑選好的 tasks，並依 Machine variant 回填結果。"""
        tasks_by_machine = _group_tasks_by_machine(self._machines, tasks)
        if not tasks_by_machine:
            return ()
        if self._worker_count == 1:
            return _run_grouped_tasks_serial(tasks_by_machine, progress_callback)

        _assert_process_solvers_registered(tasks)
        max_workers = min(self._worker_count, len(tasks))
        solve_results = self._run_tasks_in_process_pool(tasks, max_workers, progress_callback)
        return self._build_machine_results(tasks_by_machine, solve_results)

    def session(self) -> MachinePoolSession:
        """建立可重用 worker pool 的 selected-task session。"""
        return MachinePoolSession(self._machines, worker_count=self._worker_count)

    def _run_tasks_in_process_pool(
        self,
        tasks: list[RunTask],
        max_workers: int,
        progress_callback: ProgressCallback | None,
    ) -> dict[tuple[str, str, str, str, int, int], SolveResult]:
        worker_cfgs = self._machines[0]._solver_configs.to_worker_init_dict()
        packs = self._machines[0]._problem_bank.export_worker_packs()
        problem_specs = self._machines[0]._problem_bank.export_worker_problem_specs()
        rng_factory = self._machines[0]._rng_factory
        mp_context = get_context("spawn")

        by_task_key: dict[tuple[str, str, str, str, int, int], SolveResult] = {}
        with ProcessPoolExecutor(
            max_workers=max_workers,
            mp_context=mp_context,
            initializer=_configure_process_worker,
            initargs=(packs, problem_specs, worker_cfgs, rng_factory),
        ) as pool:
            future_to_task = {
                pool.submit(_run_task_process, task): task
                for task in tasks
            }
            pending = set(future_to_task)
            while pending:
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                for future in done:
                    task, solve_result = future.result()
                    by_task_key[_task_key(task)] = solve_result
                    if progress_callback is not None:
                        progress_callback(1)
        return by_task_key

    def _build_machine_results(
        self,
        tasks_by_machine: list[tuple[Machine, list[RunTask]]],
        solve_results: dict[tuple[str, str, str, str, int, int], SolveResult],
    ) -> tuple[MachineResult, ...]:
        return _build_machine_results(tasks_by_machine, solve_results)


def _resolve_base_seed(spec: ExperimentSpec, base_seed: int | None) -> int:
    resolved = spec.base_seed if base_seed is None else base_seed
    if resolved is None:
        raise ValueError("base_seed must be provided by argument or ExperimentSpec.base_seed.")
    return int(resolved)


class MachinePoolSession:
    """可重用 ProcessPool 的 selected RunTask scheduler。"""

    def __init__(self, machines: tuple[Machine, ...], *, worker_count: int) -> None:
        if worker_count <= 0:
            raise ValueError("worker_count must be > 0.")
        self._machines = machines
        self._worker_count = worker_count
        self._pool: ProcessPoolExecutor | None = None

    def __enter__(self) -> MachinePoolSession:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close(cancel_futures=exc_type is not None)

    def close(self, *, cancel_futures: bool = False) -> None:
        if self._pool is None:
            return
        self._pool.shutdown(wait=True, cancel_futures=cancel_futures)
        self._pool = None

    def run_tasks(
        self,
        tasks: list[RunTask],
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> tuple[MachineResult, ...]:
        tasks_by_machine = _group_tasks_by_machine(self._machines, tasks)
        if not tasks_by_machine:
            return ()
        if self._worker_count == 1:
            return _run_grouped_tasks_serial(tasks_by_machine, progress_callback)

        _assert_process_solvers_registered(tasks)
        solve_results = self._run_tasks_in_process_pool(tasks, progress_callback)
        return _build_machine_results(tasks_by_machine, solve_results)

    def _run_tasks_in_process_pool(
        self,
        tasks: list[RunTask],
        progress_callback: ProgressCallback | None,
    ) -> dict[tuple[str, str, str, str, int, int], SolveResult]:
        pool = self._ensure_pool()
        by_task_key: dict[tuple[str, str, str, str, int, int], SolveResult] = {}
        future_to_task = {pool.submit(_run_task_process, task): task for task in tasks}
        pending = set(future_to_task)
        while pending:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                try:
                    task, solve_result = future.result()
                except Exception:
                    for pending_future in pending:
                        pending_future.cancel()
                    raise
                by_task_key[_task_key(task)] = solve_result
                if progress_callback is not None:
                    progress_callback(1)
        return by_task_key

    def _ensure_pool(self) -> ProcessPoolExecutor:
        if self._pool is not None:
            return self._pool
        if not self._machines:
            raise RuntimeError("cannot create process pool without machines.")
        machine = self._machines[0]
        mp_context = get_context("spawn")
        self._pool = ProcessPoolExecutor(
            max_workers=self._worker_count,
            mp_context=mp_context,
            initializer=_configure_process_worker,
            initargs=(
                machine._problem_bank.export_worker_packs(),
                machine._problem_bank.export_worker_problem_specs(),
                machine._solver_configs.to_worker_init_dict(),
                machine._rng_factory,
            ),
        )
        return self._pool


def _group_tasks_by_machine(
    machines: tuple[Machine, ...],
    tasks: list[RunTask],
) -> list[tuple[Machine, list[RunTask]]]:
    if not tasks:
        return []
    by_variant = {(machine.solver_id, machine.param_set_index): machine for machine in machines}
    grouped: dict[tuple[str, int], list[RunTask]] = {}
    for task in tasks:
        key = (task.solver_id, task.param_set_index)
        if key not in by_variant:
            raise ValueError(f"task does not belong to MachinePool variant: {key!r}")
        grouped.setdefault(key, []).append(task)
    return [
        (machine, grouped[(machine.solver_id, machine.param_set_index)])
        for machine in machines
        if (machine.solver_id, machine.param_set_index) in grouped
    ]


def _run_grouped_tasks_serial(
    tasks_by_machine: list[tuple[Machine, list[RunTask]]],
    progress_callback: ProgressCallback | None,
) -> tuple[MachineResult, ...]:
    machine_results: list[MachineResult] = []
    for machine, tasks in tasks_by_machine:
        rows: list[SimulatorRunRow] = []
        for task in tasks:
            rows.append(machine.run_task(task))
            if progress_callback is not None:
                progress_callback(1)
        machine_results.append(
            MachineResult(
                solver_id=machine.solver_id,
                param_set_index=machine.param_set_index,
                params=machine.params,
                rows=tuple(rows),
            )
        )
    return tuple(machine_results)


def _build_machine_results(
    tasks_by_machine: list[tuple[Machine, list[RunTask]]],
    solve_results: dict[tuple[str, str, str, str, int, int], SolveResult],
) -> tuple[MachineResult, ...]:
    machine_results: list[MachineResult] = []
    for machine, tasks in tasks_by_machine:
        rows: list[SimulatorRunRow] = []
        for task in tasks:
            solve_result = solve_results[_task_key(task)]
            problem = machine._problem_bank.get(task.dataset, task.problem_id, task.problem_type)
            validation_report = problem.validate(solve_result)
            rows.append(
                SimulatorRunRow(
                    task=task,
                    solve_result=solve_result,
                    validation_report=validation_report,
                )
            )
        machine_results.append(
            MachineResult(
                solver_id=machine.solver_id,
                param_set_index=machine.param_set_index,
                params=machine.params,
                rows=tuple(rows),
            )
        )
    return tuple(machine_results)


def _configure_process_worker(
    packs: tuple[ProblemShmPack, ...],
    problem_specs: tuple[ProblemTypeSpec, ...],
    solver_configs: dict[tuple[str, int], dict[str, Any]],
    rng_factory: RngFactory,
) -> None:
    global _worker_solver_configs, _worker_rng_factory, _worker_solver_registry
    configure_problem_bank_worker(packs, problem_specs)
    _worker_solver_configs = {key: copy.deepcopy(config) for key, config in solver_configs.items()}
    _worker_rng_factory = rng_factory
    _worker_solver_registry = SolverRegistry()
    for solver_id, builder in solverBuilders().items():
        _worker_solver_registry.register(solver_id, builder)


def _assert_process_solvers_registered(tasks: list[RunTask]) -> None:
    available = set(solverBuilders())
    requested = {task.solver_id for task in tasks}
    missing = sorted(requested - available)
    if missing:
        raise RuntimeError(
            "run_batch process workers only support solvers registered by "
            "engine.builders.solverBuilders(): "
            f"missing={missing!r}, available={sorted(available)!r}"
        )


def _run_task_process(task: RunTask) -> tuple[RunTask, SolveResult]:
    if (
        _worker_solver_configs is None
        or _worker_rng_factory is None
        or _worker_solver_registry is None
    ):
        raise RuntimeError("process worker is not configured")
    bank = get_worker_problem_bank()
    problem = bank.get(task.dataset, task.problem_id, task.problem_type)
    solver_config = copy.deepcopy(_worker_solver_configs[(task.solver_id, task.param_set_index)])
    solver_config["run_seed"] = task.task_seed
    rng = _worker_rng_factory(task.task_seed)

    solver = _worker_solver_registry.create(task.solver_id)
    return task, solver.solve(problem, solver_config, rng)


def _task_key(task: RunTask) -> tuple[str, str, str, str, int, int]:
    return (
        task.problem_type,
        task.dataset,
        task.problem_id,
        task.solver_id,
        task.param_set_index,
        task.repeat_index,
    )
