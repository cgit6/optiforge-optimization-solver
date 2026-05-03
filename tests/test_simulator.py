from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from mkp.engine.models import ExperimentSpec, RunTask
from mkp.engine.bank import ProblemBank
from mkp.engine.repository import ProblemRepository
from mkp.engine.configs import SolverConfigsSnapshot
from mkp.simulator import Simulator, SimulatorResult
from mkp.solver.registry import SolverRegistry
from mkp.solver.validator import Validator
from mkp.tools.stat import write_simulator_result


class RecordingSolver:
    def __init__(self) -> None:
        self.first_random: int | None = None

    def solve(self, problem, config, rng):
        from mkp.engine.models import SolveResult

        self.first_random = int(rng.integers(0, 10_000))
        return SolveResult(
            problem_id=problem.problem_id,
            solver_id=config["solver_id"],
            seed=0,
            best_solution=np.array([1, 1, 1]),
            best_objective=60,
            feasible=True,
            evaluation_count=10,
            stop_reason="max_iterations_reached",
            runtime=0.1,
            linprog_runtime=0.0,
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
capabilities:
  problem_types: [mkp]
  encodings: [binary]
  directions: [max]
stop_condition:
  type: max_iterations
  max_iterations: 10
params: {}
""".strip(),
        encoding="utf-8",
    )


def _build_simulator(tmp_path: Path, solver, *, experiment_id: str = "exp_sim") -> tuple[Simulator, Path]:
    """回傳 (Simulator, output_root)；輸出檔由呼叫端透過 write_simulator_result 觸發。"""
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
        seed=0,
        output_dir=output_root,
    )
    bank = ProblemBank.build_for_spec(repository=repository, spec=bank_spec)
    registry = SolverRegistry()
    registry.register("stub_solver", lambda: solver)
    solver_configs = SolverConfigsSnapshot.build(bank_spec, solver_root)
    validator = Validator()
    return (
        Simulator(
            problem_bank=bank,
            solver_registry=registry,
            solver_configs=solver_configs,
            validator=validator,
        ),
        output_root,
    )


def test_run_task_success_writes_result_and_returns_validation(tmp_path: Path):
    solver = RecordingSolver()
    simulator, output_root = _build_simulator(tmp_path, solver)
    try:
        task = RunTask(problem_id="weish01", dataset="WEISH", solver_id="stub_solver", repeat_index=0, seed=123)

        row = simulator.run_task(task)

        assert row.task is task
        assert row.solve_result.problem_id == "weish01"
        assert row.validation_report.is_feasible is True

        # 透過 stat 模組寫出（保留檔案存在性的覆蓋率）
        write_simulator_result(
            SimulatorResult(rows=(row,)),
            experiment_id="exp_sim",
            output_root=output_root,
        )
        assert (output_root / "exp_sim" / "runs.csv").exists()
        assert (output_root / "exp_sim" / "runs.jsonl").exists()
    finally:
        simulator.close()


def test_run_task_rng_seed_is_reproducible(tmp_path: Path):
    solver1 = RecordingSolver()
    simulator1, _ = _build_simulator(tmp_path / "a", solver1, experiment_id="exp_a")
    task = RunTask(problem_id="weish01", dataset="WEISH", solver_id="stub_solver", repeat_index=0, seed=777)
    try:
        simulator1.run_task(task)
    finally:
        simulator1.close()

    solver2 = RecordingSolver()
    simulator2, _ = _build_simulator(tmp_path / "b", solver2, experiment_id="exp_b")
    try:
        simulator2.run_task(task)
    finally:
        simulator2.close()

    assert solver1.first_random == solver2.first_random


def test_run_task_fail_fast_when_problem_load_fails(tmp_path: Path):
    solver = RecordingSolver()
    simulator, _ = _build_simulator(tmp_path, solver)
    try:
        task = RunTask(problem_id="missing_problem", dataset="WEISH", solver_id="stub_solver", repeat_index=0, seed=1)

        with pytest.raises(FileNotFoundError):
            simulator.run_task(task)
    finally:
        simulator.close()


def test_solver_snapshot_build_fails_when_solver_dir_has_no_yaml(tmp_path: Path) -> None:
    bank_spec = ExperimentSpec(
        experiment_id="exp_fail",
        dataset="WEISH",
        problem_ids=("weish01",),
        solver_ids=("stub_solver",),
        repeat=1,
        seed=0,
        output_dir=tmp_path / "output",
    )
    with pytest.raises(FileNotFoundError):
        SolverConfigsSnapshot.build(bank_spec, tmp_path / "missing-solvers")
