from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from mkp.contracts import ExperimentSpec, RunTask
from mkp.problem_bank import ProblemBank
from mkp.problem_repository import ProblemRepository
from mkp.result_writer import ResultWriter
from mkp.simulator import Simulator
from mkp.solver_config_loader import SolverConfigLoader
from mkp.solver_registry import SolverRegistry
from mkp.validator import Validator


class RecordingSolver:
    def __init__(self) -> None:
        self.first_random: int | None = None

    def solve(self, problem, config, rng):
        from mkp.contracts import RunResult

        self.first_random = int(rng.integers(0, 10_000))
        return RunResult(
            problem_id=problem.problem_id,
            solver_id=config["solver_id"],
            repeat_index=0,
            seed=0,
            best_solution=np.array([1, 1, 1]),
            best_objective=60,
            feasible=True,
            evaluation_count=10,
            stop_reason="max_iterations_reached",
            runtime=0.1,
            error=None,
        )


def _write_problem_yaml(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
problem_id: weish01
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
stop_condition:
  type: max_iterations
  max_iterations: 10
params: {}
""".strip(),
        encoding="utf-8",
    )


def _build_simulator(tmp_path: Path, solver, *, experiment_id: str = "exp_sim") -> Simulator:
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    output_root = tmp_path / "output"

    _write_problem_yaml(problem_root / "WEISH" / "weish01.yaml")
    _write_solver_yaml(solver_root / "stub_solver.yaml")

    repository = ProblemRepository(config_root=problem_root)
    bank_spec = ExperimentSpec(
        experiment_id=experiment_id,
        dataset="WEISH",
        problem_ids=("weish01",),
        solver_ids=("stub_solver",),
        repeat=1,
        base_seed=0,
        output_dir=output_root,
    )
    bank = ProblemBank.build_for_spec(repository=repository, spec=bank_spec)
    registry = SolverRegistry()
    registry.register("stub_solver", lambda: solver)
    config_loader = SolverConfigLoader(config_root=solver_root)
    validator = Validator()
    result_writer = ResultWriter(experiment_id=experiment_id, output_root=output_root)
    return Simulator(
        problem_bank=bank,
        solver_registry=registry,
        solver_config_loader=config_loader,
        validator=validator,
        result_writer=result_writer,
    )


def test_run_task_success_writes_result_and_returns_validation(tmp_path: Path):
    solver = RecordingSolver()
    simulator = _build_simulator(tmp_path, solver)
    try:
        task = RunTask(problem_id="weish01", dataset="WEISH", solver_id="stub_solver", repeat_index=0, seed=123)

        run_result, report, entry = simulator.run_task(task)

        assert run_result.problem_id == "weish01"
        assert report.is_feasible is True
        assert entry.problem_id == "weish01"
        assert (tmp_path / "output" / "exp_sim" / "runs.csv").exists()
        assert (tmp_path / "output" / "exp_sim" / "runs.jsonl").exists()
    finally:
        simulator.close()


def test_run_task_rng_seed_is_reproducible(tmp_path: Path):
    solver1 = RecordingSolver()
    simulator1 = _build_simulator(tmp_path / "a", solver1, experiment_id="exp_a")
    task = RunTask(problem_id="weish01", dataset="WEISH", solver_id="stub_solver", repeat_index=0, seed=777)
    try:
        simulator1.run_task(task)
    finally:
        simulator1.close()

    solver2 = RecordingSolver()
    simulator2 = _build_simulator(tmp_path / "b", solver2, experiment_id="exp_b")
    try:
        simulator2.run_task(task)
    finally:
        simulator2.close()

    assert solver1.first_random == solver2.first_random


def test_run_task_fail_fast_when_problem_load_fails(tmp_path: Path):
    solver = RecordingSolver()
    simulator = _build_simulator(tmp_path, solver)
    try:
        task = RunTask(problem_id="missing_problem", dataset="WEISH", solver_id="stub_solver", repeat_index=0, seed=1)

        with pytest.raises(FileNotFoundError):
            simulator.run_task(task)
    finally:
        simulator.close()


def test_run_task_fail_fast_when_solver_config_load_fails(tmp_path: Path):
    problem_root = tmp_path / "problems"
    _write_problem_yaml(problem_root / "WEISH" / "weish01.yaml")

    repository = ProblemRepository(config_root=problem_root)
    bank_spec = ExperimentSpec(
        experiment_id="exp_fail",
        dataset="WEISH",
        problem_ids=("weish01",),
        solver_ids=("stub_solver",),
        repeat=1,
        base_seed=0,
        output_dir=tmp_path / "output",
    )
    bank = ProblemBank.build_for_spec(repository=repository, spec=bank_spec)
    registry = SolverRegistry()
    solver = RecordingSolver()
    registry.register("stub_solver", lambda: solver)
    config_loader = SolverConfigLoader(config_root=tmp_path / "missing-solvers")
    validator = Validator()
    result_writer = ResultWriter(experiment_id="exp_fail", output_root=tmp_path / "output")
    simulator = Simulator(
        problem_bank=bank,
        solver_registry=registry,
        solver_config_loader=config_loader,
        validator=validator,
        result_writer=result_writer,
    )
    try:
        task = RunTask(problem_id="weish01", dataset="WEISH", solver_id="stub_solver", repeat_index=0, seed=1)

        with pytest.raises(FileNotFoundError):
            simulator.run_task(task)
    finally:
        simulator.close()
