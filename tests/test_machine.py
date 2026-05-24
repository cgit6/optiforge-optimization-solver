from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from mkp.engine.bank import ProblemBank
from mkp.engine.configs import SolverConfigsSnapshot
from mkp.engine.models import ExperimentSpec, SolveResult
from mkp.engine.repository import ProblemRepository
from mkp.machine import Machine, MachinePool
from mkp.problem import buildProblemRegistry, problemBuilders
from mkp.rng import DerivedPerProblemSeedStrategy, make_numpy_rng
from mkp.solver.registry import SolverRegistry


class RecordingSolver:
    def solve(self, problem, config, rng):
        return SolveResult(
            problem_id=problem.problem_id,
            solver_id=config["solver_id"],
            run_seed=int(config["run_seed"]),
            best_solution=np.array([1, 1, 1]),
            best_objective=60,
            feasible=True,
            evaluation_count=10,
            stop_reason="max_iterations_reached",
            runtime=0.1,
        )


def _write_problem_yaml(path: Path, *, problem_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""
problem_id: {problem_id}
dataset: WEISH
items: 3
dim: 2
best_known: 50
values: [10, 20, 30]
weights:
  - [2, 1]
  - [3, 2]
  - [4, 3]
capacities: [10, 8]
""".strip(),
        encoding="utf-8",
    )


def _write_solver_yaml(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
solver_id: stub_solver
solver_class: RecordingSolver
capabilities:
  problem_types: [mkp]
  encodings: [binary]
  directions: [max]
stop_condition:
  type: max_iterations
  max_iterations: 10
params:
  - {z: 0.01}
  - {z: 0.02}
""".strip(),
        encoding="utf-8",
    )


def _build_machine_context(tmp_path: Path):
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    _write_problem_yaml(problem_root / "mkp" / "WEISH" / "p1.yaml", problem_id="p1")
    _write_problem_yaml(problem_root / "mkp" / "WEISH" / "p2.yaml", problem_id="p2")
    _write_solver_yaml(solver_root / "stub_solver.yaml")

    spec = ExperimentSpec(
        experiment_name="exp_machine",
        dataset="WEISH",
        problem_ids=("p1", "p2"),
        solver_ids=("stub_solver",),
        repeat=2,
    )
    problem_registry = buildProblemRegistry(problemBuilders())
    repository = ProblemRepository(config_root=problem_root, registry=problem_registry)
    bank = ProblemBank.build(repository=repository, spec=spec, registry=problem_registry)
    registry = SolverRegistry()
    registry.register("stub_solver", lambda: RecordingSolver())
    solver_configs = SolverConfigsSnapshot.build(spec, solver_root)
    return spec, bank, registry, solver_configs


def _machine(tmp_path: Path, *, param_set_index: int) -> tuple[Machine, ProblemBank]:
    spec, bank, registry, solver_configs = _build_machine_context(tmp_path)
    return (
        Machine(
            spec=spec,
            solver_id="stub_solver",
            param_set_index=param_set_index,
            problem_bank=bank,
            solver_registry=registry,
            solver_configs=solver_configs,
            seed_strategy=DerivedPerProblemSeedStrategy(),
            rng_factory=make_numpy_rng,
        ),
        bank,
    )


def test_machine_expands_only_one_solver_param_variant(tmp_path: Path) -> None:
    machine, bank = _machine(tmp_path, param_set_index=1)
    try:
        tasks = machine.expand_tasks(base_seed=123)

        assert len(tasks) == 4
        assert {task.problem_id for task in tasks} == {"p1", "p2"}
        assert {task.solver_id for task in tasks} == {"stub_solver"}
        assert {task.param_set_index for task in tasks} == {1}
    finally:
        bank.close()


def test_machine_expands_single_selected_task(tmp_path: Path) -> None:
    machine, bank = _machine(tmp_path, param_set_index=1)
    try:
        task = machine.expand_task(problem_id="p2", repeat_index=1, base_seed=123)
        full_tasks = machine.expand_tasks(base_seed=123)

        assert task == [
            item for item in full_tasks
            if item.problem_id == "p2" and item.repeat_index == 1
        ][0]
        assert task.solver_id == "stub_solver"
        assert task.param_set_index == 1
    finally:
        bank.close()


def test_machine_result_contains_only_own_variant_rows(tmp_path: Path) -> None:
    machine, bank = _machine(tmp_path, param_set_index=0)
    try:
        result = machine.run(base_seed=123)

        assert result.solver_id == "stub_solver"
        assert result.param_set_index == 0
        assert result.params == {"z": 0.01}
        assert len(result.rows) == 4
        assert all(row.task.param_set_index == 0 for row in result.rows)
        assert all(row.solve_result.run_seed == row.task.task_seed for row in result.rows)
    finally:
        bank.close()


def test_machine_pool_run_tasks_executes_only_selected_round(tmp_path: Path) -> None:
    spec, bank, registry, solver_configs = _build_machine_context(tmp_path)
    machines = tuple(
        Machine(
            spec=spec,
            solver_id="stub_solver",
            param_set_index=param_set_index,
            problem_bank=bank,
            solver_registry=registry,
            solver_configs=solver_configs,
            seed_strategy=DerivedPerProblemSeedStrategy(),
            rng_factory=make_numpy_rng,
        )
        for param_set_index in (0, 1)
    )
    try:
        tasks = [
            machine.expand_task(problem_id="p1", repeat_index=1, base_seed=123)
            for machine in machines
        ]
        results = MachinePool(machines, worker_count=1).run_tasks(tasks)

        assert len(results) == 2
        assert [len(result.rows) for result in results] == [1, 1]
        assert {
            (row.task.problem_id, row.task.repeat_index)
            for result in results
            for row in result.rows
        } == {("p1", 1)}
        assert len({row.task.task_seed for result in results for row in result.rows}) == 1
    finally:
        bank.close()


def test_machine_pool_worker_limit_uses_total_tasks_not_machine_count(tmp_path: Path, monkeypatch) -> None:
    spec, bank, registry, solver_configs = _build_machine_context(tmp_path)
    machines = tuple(
        Machine(
            spec=spec,
            solver_id="stub_solver",
            param_set_index=param_set_index,
            problem_bank=bank,
            solver_registry=registry,
            solver_configs=solver_configs,
            seed_strategy=DerivedPerProblemSeedStrategy(),
            rng_factory=make_numpy_rng,
        )
        for param_set_index in (0, 1)
    )
    captured: dict[str, int] = {}

    def fake_run_tasks(self, tasks, max_workers, progress_callback):
        captured["task_count"] = len(tasks)
        captured["max_workers"] = max_workers
        solve_results = {}
        for task in tasks:
            machine = machines[task.param_set_index]
            row = machine.run_task(task)
            solve_results[
                (
                    task.problem_type,
                    task.dataset,
                    task.problem_id,
                    task.solver_id,
                    task.param_set_index,
                    task.repeat_index,
                )
            ] = row.solve_result
            if progress_callback is not None:
                progress_callback(1)
        return solve_results

    monkeypatch.setattr(MachinePool, "_run_tasks_in_process_pool", fake_run_tasks)
    try:
        results = MachinePool(machines, worker_count=5).run(base_seed=123)

        assert captured == {"task_count": 8, "max_workers": 5}
        assert sum(len(result.rows) for result in results) == 8
    finally:
        bank.close()


def test_machine_pool_preserves_shared_run_seed_across_param_variants(tmp_path: Path) -> None:
    spec, bank, registry, solver_configs = _build_machine_context(tmp_path)
    machines = tuple(
        Machine(
            spec=spec,
            solver_id="stub_solver",
            param_set_index=param_set_index,
            problem_bank=bank,
            solver_registry=registry,
            solver_configs=solver_configs,
            seed_strategy=DerivedPerProblemSeedStrategy(),
            rng_factory=make_numpy_rng,
        )
        for param_set_index in (0, 1)
    )
    try:
        results = MachinePool(machines, worker_count=2).run(base_seed=123)
        by_variant = {(result.solver_id, result.param_set_index): result for result in results}

        assert set(by_variant) == {("stub_solver", 0), ("stub_solver", 1)}
        seed_param_0 = {
            (row.task.problem_id, row.task.repeat_index): row.task.task_seed
            for row in by_variant[("stub_solver", 0)].rows
        }
        seed_param_1 = {
            (row.task.problem_id, row.task.repeat_index): row.task.task_seed
            for row in by_variant[("stub_solver", 1)].rows
        }
        assert seed_param_0 == seed_param_1
        assert [row.task for row in by_variant[("stub_solver", 0)].rows] == machines[0].expand_tasks(base_seed=123)
        assert [row.task for row in by_variant[("stub_solver", 1)].rows] == machines[1].expand_tasks(base_seed=123)
    finally:
        bank.close()


def test_machine_pool_process_requires_builder_registered_solver(tmp_path: Path) -> None:
    spec, bank, _, _ = _build_machine_context(tmp_path)
    custom_spec = ExperimentSpec(
        experiment_name=spec.experiment_name,
        dataset=spec.dataset,
        problem_ids=spec.problem_ids,
        solver_ids=("stub_solver_custom",),
        repeat=spec.repeat,
        problem_type=spec.problem_type,
        worker_count=2,
        base_seed=spec.base_seed,
    )
    registry = SolverRegistry()
    registry.register("stub_solver_custom", lambda: RecordingSolver())
    machine = Machine(
        spec=custom_spec,
        solver_id="stub_solver_custom",
        param_set_index=0,
        problem_bank=bank,
        solver_registry=registry,
        solver_configs=SolverConfigsSnapshot(
            _by_key=(
                (
                    ("stub_solver_custom", 0),
                    {
                        "solver_id": "stub_solver_custom",
                        "solver_class": "RecordingSolver",
                        "capabilities": {
                            "problem_types": ["mkp"],
                            "encodings": ["binary"],
                            "directions": ["max"],
                        },
                        "stop_condition": {"type": "max_iterations", "max_iterations": 10},
                        "params": {},
                        "param_set_index": 0,
                    },
                ),
            )
        ),
        seed_strategy=DerivedPerProblemSeedStrategy(),
        rng_factory=make_numpy_rng,
    )
    try:
        with pytest.raises(RuntimeError) as exc_info:
            MachinePool((machine,), worker_count=2).run(base_seed=123)
        assert "solverBuilders" in str(exc_info.value)
        assert "stub_solver_custom" in str(exc_info.value)
    finally:
        bank.close()
