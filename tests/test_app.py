from __future__ import annotations

from pathlib import Path

import pytest

from mkp.cli.run import build_parser, create_experiment_spec, main
from mkp.cli.run import validate_execute_args
from mkp.engine.contracts import ExperimentSpec


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
solver_class: StubMaxIterationsSolver
stop_condition:
  type: max_iterations
  max_iterations: 10
params: {}
""".strip(),
        encoding="utf-8",
    )


def test_create_experiment_spec_execution_mode_worker_curriculum(tmp_path: Path):
    parser = build_parser()
    out = str(tmp_path / "out")
    args = parser.parse_args(
        [
            "--experiment-id",
            "exp_mode",
            "--dataset",
            "WEISH",
            "--problems",
            "weish01",
            "--solver",
            "stub_solver",
            "--repeat",
            "1",
            "--base-seed",
            "123",
            "--output-dir",
            out,
            "--execution-mode",
            "worker_curriculum",
        ]
    )
    spec = create_experiment_spec(args)
    assert spec.execution_mode == "worker_curriculum"
    assert spec.solver_ids == ("stub_solver",)


def test_app_cli_success_runs_batch(tmp_path: Path):
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    output_root = tmp_path / "output"
    _write_problem_yaml(problem_root / "WEISH" / "weish01.yaml")
    _write_solver_yaml(solver_root / "stub_solver.yaml")

    argv = [
        "--experiment-id",
        "exp_cli_1",
        "--dataset",
        "WEISH",
        "--problems",
        "weish01",
        "--solver",
        "stub_solver",
        "--repeat",
        "1",
        "--base-seed",
        "123",
        "--output-dir",
        str(output_root),
    ]

    results = main(argv, problem_root=problem_root, solver_root=solver_root)
    assert len(results) == 1
    assert (output_root / "exp_cli_1" / "runs.csv").exists()
    assert (output_root / "exp_cli_1" / "runs.jsonl").exists()


def test_app_cli_worker_curriculum_runs_batch(tmp_path: Path):
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    output_root = tmp_path / "output"
    _write_problem_yaml(problem_root / "WEISH" / "weish01.yaml")
    _write_solver_yaml(solver_root / "stub_solver.yaml")

    argv = [
        "--experiment-id",
        "exp_cli_worker",
        "--dataset",
        "WEISH",
        "--problems",
        "weish01",
        "--solver",
        "stub_solver",
        "--repeat",
        "1",
        "--base-seed",
        "123",
        "--output-dir",
        str(output_root),
        "--execution-mode",
        "worker_curriculum",
    ]

    results = main(argv, problem_root=problem_root, solver_root=solver_root)
    assert len(results) == 1
    assert (output_root / "exp_cli_worker" / "runs.csv").exists()


def test_app_cli_fail_fast_when_problem_yaml_missing(tmp_path: Path):
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    output_root = tmp_path / "output"
    _write_solver_yaml(solver_root / "stub_solver.yaml")

    argv = [
        "--experiment-id",
        "exp_cli_missing_problem",
        "--dataset",
        "WEISH",
        "--problems",
        "weish01",
        "--solver",
        "stub_solver",
        "--repeat",
        "1",
        "--base-seed",
        "1",
        "--output-dir",
        str(output_root),
    ]

    with pytest.raises(FileNotFoundError, match="Missing problem YAML file"):
        main(argv, problem_root=problem_root, solver_root=solver_root)


def test_app_cli_fail_fast_when_solver_yaml_missing(tmp_path: Path):
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    output_root = tmp_path / "output"
    _write_problem_yaml(problem_root / "WEISH" / "weish01.yaml")

    argv = [
        "--experiment-id",
        "exp_cli_missing_solver",
        "--dataset",
        "WEISH",
        "--problems",
        "weish01",
        "--solver",
        "stub_solver",
        "--repeat",
        "1",
        "--base-seed",
        "1",
        "--output-dir",
        str(output_root),
    ]

    with pytest.raises(FileNotFoundError, match="Missing solver YAML file"):
        main(argv, problem_root=problem_root, solver_root=solver_root)


def test_app_cli_missing_required_arg_rejected(tmp_path: Path):
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    output_root = tmp_path / "output"
    _write_problem_yaml(problem_root / "WEISH" / "weish01.yaml")
    _write_solver_yaml(solver_root / "stub_solver.yaml")

    argv = [
        "--experiment-id",
        "exp_cli_bad",
        "--dataset",
        "WEISH",
        "--problems",
        "weish01",
        "--repeat",
        "1",
        "--base-seed",
        "1",
        "--output-dir",
        str(output_root),
    ]

    with pytest.raises(SystemExit):
        main(argv, problem_root=problem_root, solver_root=solver_root)


def test_validate_execute_args_rejects_multiple_solvers(tmp_path: Path) -> None:
    spec = ExperimentSpec(
        experiment_id="e",
        dataset="D",
        problem_ids=("p1",),
        solver_ids=("a", "b"),
        repeat=1,
        seed=1,
        output_dir=tmp_path / "o",
    )
    with pytest.raises(ValueError, match="Exactly one solver is required"):
        validate_execute_args(spec, tmp_path, tmp_path)
