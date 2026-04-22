from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from mkp.contracts import ExperimentSpec, RunResult
from mkp.problem_repository import ProblemRepository
from mkp.result_writer import ResultWriter
from mkp.simulator import Simulator
from mkp.solver_config_loader import SolverConfigLoader
from mkp.solver_registry import SolverRegistry
from mkp.validator import Validator


class CountingSolver:
    calls = 0

    def solve(self, problem, config, rng):
        CountingSolver.calls += 1
        return RunResult(
            problem_id=problem.problem_id,
            solver_id=config["solver_id"],
            repeat_index=0,
            seed=int(rng.integers(0, np.iinfo(np.int32).max)),
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


def _write_solver_yaml(path: Path, solver_id: str = "stub_solver") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""
solver_id: {solver_id}
solver_class: CountingSolver
stop_condition:
  type: max_iterations
  max_iterations: 10
params: {{}}
""".strip(),
        encoding="utf-8",
    )


def _build_simulator(tmp_path: Path) -> Simulator:
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    output_root = tmp_path / "output"
    _write_problem_yaml(problem_root / "WEISH" / "weish01.yaml")
    _write_solver_yaml(solver_root / "stub_solver.yaml", solver_id="stub_solver")

    repository = ProblemRepository(config_root=problem_root)
    registry = SolverRegistry()
    registry.register("stub_solver", lambda: CountingSolver())
    config_loader = SolverConfigLoader(config_root=solver_root)
    validator = Validator()
    result_writer = ResultWriter(experiment_id="exp_batch", output_root=output_root)
    return Simulator(
        problem_repository=repository,
        solver_registry=registry,
        solver_config_loader=config_loader,
        validator=validator,
        result_writer=result_writer,
    )


def _build_spec() -> ExperimentSpec:
    return ExperimentSpec(
        experiment_id="exp_batch",
        dataset="WEISH",
        problem_ids=("weish01",),
        solver_ids=("stub_solver",),
        repeat=3,
        base_seed=1234,
        output_dir=Path("mkp/output/exp_batch"),
        benchmark_enabled=False,
    )


def test_expand_tasks_count_and_fields():
    simulator = _build_simulator(Path("/tmp/sim_expand_1"))
    spec = _build_spec()
    tasks = simulator.expand_tasks(spec)

    assert len(tasks) == 3
    assert tasks[0].problem_id == "weish01"
    assert tasks[0].solver_id == "stub_solver"
    assert tasks[0].repeat_index == 0
    assert tasks[1].repeat_index == 1
    assert tasks[2].repeat_index == 2


def test_rng_seed_reproducibility_and_independence():
    simulator = _build_simulator(Path("/tmp/sim_expand_2"))
    spec = _build_spec()
    tasks_a = simulator.expand_tasks(spec)
    tasks_b = simulator.expand_tasks(spec)

    assert [t.seed for t in tasks_a] == [t.seed for t in tasks_b]
    assert len(set(t.seed for t in tasks_a)) == len(tasks_a)


def test_run_batch_fail_fast_on_problem_load_error(tmp_path: Path):
    simulator = _build_simulator(tmp_path)
    spec = ExperimentSpec(
        experiment_id="exp_batch_fail_problem",
        dataset="WEISH",
        problem_ids=("missing", "weish01"),
        solver_ids=("stub_solver",),
        repeat=1,
        base_seed=1,
        output_dir=Path("mkp/output/exp_batch_fail_problem"),
    )

    CountingSolver.calls = 0
    with pytest.raises(FileNotFoundError):
        simulator.run_batch(spec)
    assert CountingSolver.calls == 0


def test_run_batch_fail_fast_on_solver_config_error(tmp_path: Path):
    problem_root = tmp_path / "problems"
    _write_problem_yaml(problem_root / "WEISH" / "weish01.yaml")

    solver_root = tmp_path / "solvers"
    _write_solver_yaml(solver_root / "stub_solver.yaml", solver_id="stub_solver")

    repository = ProblemRepository(config_root=problem_root)
    registry = SolverRegistry()
    registry.register("stub_solver", lambda: CountingSolver())
    config_loader = SolverConfigLoader(config_root=solver_root)
    validator = Validator()
    result_writer = ResultWriter(experiment_id="exp_batch_fail_solver", output_root=tmp_path / "output")
    simulator = Simulator(
        problem_repository=repository,
        solver_registry=registry,
        solver_config_loader=config_loader,
        validator=validator,
        result_writer=result_writer,
    )

    spec = ExperimentSpec(
        experiment_id="exp_batch_fail_solver",
        dataset="WEISH",
        problem_ids=("weish01",),
        solver_ids=("missing_solver",),
        repeat=2,
        base_seed=1,
        output_dir=Path("mkp/output/exp_batch_fail_solver"),
    )

    CountingSolver.calls = 0
    with pytest.raises(FileNotFoundError):
        simulator.run_batch(spec)
    assert CountingSolver.calls == 0
