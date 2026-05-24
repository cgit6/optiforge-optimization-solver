from __future__ import annotations

import sys
from dataclasses import dataclass

from tqdm import tqdm

from ..engine.bank import ProblemBank
from ..engine.configs import SolverConfigsSnapshot
from ..engine.models import ExperimentSpec, RunTask
from ..machine import Machine, MachinePool, MachineResult, SimulatorRunRow
from ..rng import RngFactory, SeedStrategy
from ..solver.registry import SolverRegistry


@dataclass(frozen=True)
class SimulatorResult:
    """整個批次的模擬結果，以 solver+param MachineResult 分桶保存。"""

    machine_results: tuple[MachineResult, ...] # 結果

    def __post_init__(self) -> None:
        seen: set[tuple[str, int]] = set()
        for result in self.machine_results:
            key = (result.solver_id, result.param_set_index)
            if key in seen:
                raise ValueError(f"duplicate MachineResult variant: {key!r}")
            seen.add(key)

    @property
    def by_variant(self) -> dict[tuple[str, int], MachineResult]:
        return {
            (result.solver_id, result.param_set_index): result
            for result in self.machine_results
        }

    def by_run(self, problem_id: str, repeat_index: int) -> tuple[SimulatorRunRow, ...]:
        rows: list[SimulatorRunRow] = []
        for result in self.machine_results:
            rows.extend(
                row
                for row in result.rows
                if row.task.problem_id == problem_id
                and row.task.repeat_index == repeat_index
            )
        return tuple(
            sorted(
                rows,
                key=lambda row: (row.task.solver_id, row.task.param_set_index),
            )
        )

    def iter_rows(self) -> tuple[SimulatorRunRow, ...]:
        return tuple(row for result in self.machine_results for row in result.rows)


class Simulator:
    """單一 solver 的調度器；每組 solver params 由一台 Machine 執行。"""

    def __init__(
        self,
        *,
        spec: ExperimentSpec,
        problem_bank: ProblemBank,
        solver_registry: SolverRegistry,
        solver_configs: SolverConfigsSnapshot,
        seed_strategy: SeedStrategy,
        rng_factory: RngFactory,
    ) -> None:
        if len(spec.solver_ids) != 1:
            raise ValueError("Simulator accepts exactly one solver_id; use SimulationBundle.new_simulators for multi-solver specs.")
        self._spec = spec
        self._problem_bank = problem_bank
        self._solver_registry = solver_registry
        self._solver_configs = solver_configs
        self._seed_strategy = seed_strategy
        self._rng_factory = rng_factory
        self._machines = self._build_machines()

    @property
    def spec(self) -> ExperimentSpec:
        return self._spec

    @property
    def machines(self) -> tuple[Machine, ...]:
        return self._machines

    def close(self) -> None:
        """釋放 `ProblemBank` 的 shared memory（實驗結束後應呼叫）。"""
        self._problem_bank.close()

    def run_task(self, task: RunTask) -> SimulatorRunRow:
        """執行單個任務；主要供測試或低階呼叫端使用。"""
        machine = self._machine_for_task(task)
        return machine.run_task(task)

    def expand_tasks(self, *, base_seed: int | None = None) -> list[RunTask]:
        """把單 solver 的所有參數組合展開成 RunTask。"""
        tasks: list[RunTask] = []
        for machine in self._machines:
            tasks.extend(machine.expand_tasks(base_seed=base_seed))
        return tasks

    def run_sequential(
        self,
        *,
        base_seed: int | None = None,
        show_progress: bool = True,
    ) -> SimulatorResult:
        """一台 Machine 跑完後才執行下一台 Machine。"""
        return self._run_with_pool(
            base_seed=base_seed,
            worker_count=1,
            show_progress=show_progress,
            desc=f"{self._spec.experiment_name} sequential",
        )

    def run_batch(
        self,
        *,
        base_seed: int | None = None,
        show_progress: bool = True,
    ) -> SimulatorResult:
        """以 MachinePool 的 ProcessPool 全域併發執行 RunTask。"""
        return self._run_with_pool(
            base_seed=base_seed,
            worker_count=self._spec.worker_count,
            show_progress=show_progress,
            desc=f"{self._spec.experiment_name} batch",
        )

    def _run_with_pool(
        self,
        *,
        base_seed: int | None,
        worker_count: int,
        show_progress: bool,
        desc: str,
    ) -> SimulatorResult:
        total_tasks = sum(machine.task_count for machine in self._machines)
        with _progress_bar(total=total_tasks, desc=desc, enabled=show_progress) as progress:
            pool = MachinePool(self._machines, worker_count=worker_count)
            machine_results = pool.run(
                base_seed=base_seed,
                progress_callback=progress.update,
            )
        return SimulatorResult(machine_results=machine_results)

    def _build_machines(self) -> tuple[Machine, ...]:
        solver_id = self._spec.solver_ids[0]
        return tuple(
            Machine(
                spec=self._spec,
                solver_id=solver_id,
                param_set_index=param_set_index,
                problem_bank=self._problem_bank,
                solver_registry=self._solver_registry,
                solver_configs=self._solver_configs,
                seed_strategy=self._seed_strategy,
                rng_factory=self._rng_factory,
            )
            for param_set_index in self._solver_configs.param_set_indices(solver_id)
        )

    def _machine_for_task(self, task: RunTask) -> Machine:
        solver_id = self._spec.solver_ids[0]
        if task.solver_id != solver_id:
            raise ValueError(f"task solver_id={task.solver_id!r} does not match simulator solver_id={solver_id!r}.")
        for machine in self._machines:
            if machine.param_set_index == task.param_set_index:
                return machine
        raise KeyError(
            f"param_set_index not in simulator machines: "
            f"solver_id={task.solver_id!r} param_set_index={task.param_set_index!r}"
        )


def _progress_bar(total: int, desc: str, *, enabled: bool = True) -> tqdm:
    return tqdm(
        total=total,
        desc=desc,
        unit="task",
        dynamic_ncols=True,
        disable=(not enabled) or (not sys.stderr.isatty()),
    )
