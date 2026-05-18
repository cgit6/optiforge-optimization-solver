from __future__ import annotations

import pytest
from pathlib import Path

from mkp.cli.run import createExperimentSpec, main, parser, validate_execute_args
from mkp.engine.models import ExperimentSpec


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


def _write_solver_yaml(path: Path, solver_id: str = "stub_solver", *, param_count: int = 1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    params = "\n".join(f"  - {{index: {index}}}" for index in range(param_count))
    path.write_text(
        f"""
solver_id: {solver_id}
solver_class: StubMaxIterationsSolver
capabilities:
  problem_types: [mkp]
  encodings: [binary]
  directions: [max]
stop_condition:
  type: max_iterations
  max_iterations: 10
params:
{params}
""".strip(),
        encoding="utf-8",
    )


def test_create_experiment_spec_uses_new_cli_defaults() -> None:
    arg_parser = parser()
    args = arg_parser.parse_args(
        [
            "--experiment-name",
            "exp_mode",
            "--type",
            "mkp",
            "--dataset",
            "WEISH",
            "--problems",
            "weish01",
            "--solver",
            "stub_solver",
        ]
    )
    spec = createExperimentSpec(args)
    assert spec.experiment_name == "exp_mode"
    assert spec.problem_type == "mkp"
    assert spec.solver_ids == ("stub_solver",)
    assert spec.repeat == 20
    assert args.seed == 55688
    assert spec.worker_count == 1


def test_create_experiment_spec_rejects_invalid_worker_count() -> None:
    arg_parser = parser()
    args = arg_parser.parse_args(
        [
            "--experiment-name",
            "exp_bad_worker",
            "--type",
            "mkp",
            "--dataset",
            "WEISH",
            "--problems",
            "weish01",
            "--solver",
            "stub_solver",
            "--worker",
            "0",
        ]
    )

    with pytest.raises(ValueError, match="worker_count must be > 0"):
        createExperimentSpec(args)


def test_app_cli_success_runs_all_solver_params(tmp_path: Path):
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    output_root = tmp_path / "output"
    _write_problem_yaml(problem_root / "mkp" / "WEISH" / "weish01.yaml")
    _write_solver_yaml(solver_root / "stub_solver.yaml", param_count=2)

    argv = [
        "--experiment-name",
        "exp_cli_1",
        "--type",
        "mkp",
        "--dataset",
        "WEISH",
        "--problems",
        "weish01",
        "--solver",
        "stub_solver",
        "--repeat",
        "1",
        "--seed",
        "123",
    ]

    result = main(argv, problem_root=problem_root, solver_root=solver_root, output_root=output_root)
    assert len(result.rows) == 2
    assert (output_root / "exp_cli_1" / "stub_solver" / "param_0" / "runs.csv").exists()
    assert (output_root / "exp_cli_1" / "stub_solver" / "param_1" / "runs.csv").exists()


def test_app_cli_worker_runs_batch(tmp_path: Path):
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    output_root = tmp_path / "output"
    _write_problem_yaml(problem_root / "mkp" / "WEISH" / "weish01.yaml")
    _write_solver_yaml(solver_root / "stub_solver.yaml")

    argv = [
        "--experiment-name",
        "exp_cli_worker",
        "--type",
        "mkp",
        "--dataset",
        "WEISH",
        "--problems",
        "weish01",
        "--solver",
        "stub_solver",
        "--repeat",
        "1",
        "--seed",
        "123",
        "--worker",
        "2",
    ]

    result = main(argv, problem_root=problem_root, solver_root=solver_root, output_root=output_root)
    assert len(result.rows) == 1
    assert (output_root / "exp_cli_worker" / "stub_solver" / "param_0" / "runs.csv").exists()
    assert (output_root / "exp_cli_worker" / "stub_solver" / "param_0" / "runs.json").exists()


def test_app_cli_fail_fast_when_problem_yaml_missing(tmp_path: Path):
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    _write_solver_yaml(solver_root / "stub_solver.yaml")

    argv = [
        "--experiment-name",
        "exp_cli_missing_problem",
        "--type",
        "mkp",
        "--dataset",
        "WEISH",
        "--problems",
        "weish01",
        "--solver",
        "stub_solver",
        "--repeat",
        "1",
        "--seed",
        "1",
    ]

    with pytest.raises(FileNotFoundError, match="Problem YAML not found"):
        main(argv, problem_root=problem_root, solver_root=solver_root)


def test_app_cli_fail_fast_when_solver_yaml_missing(tmp_path: Path):
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    _write_problem_yaml(problem_root / "mkp" / "WEISH" / "weish01.yaml")

    argv = [
        "--experiment-name",
        "exp_cli_missing_solver",
        "--type",
        "mkp",
        "--dataset",
        "WEISH",
        "--problems",
        "weish01",
        "--solver",
        "stub_solver",
        "--repeat",
        "1",
        "--seed",
        "1",
    ]

    with pytest.raises(FileNotFoundError, match="Solver config YAML not found"):
        main(argv, problem_root=problem_root, solver_root=solver_root)


def test_app_cli_missing_required_arg_rejected(tmp_path: Path):
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    _write_problem_yaml(problem_root / "mkp" / "WEISH" / "weish01.yaml")
    _write_solver_yaml(solver_root / "stub_solver.yaml")

    argv = [
        "--experiment-name",
        "exp_cli_bad",
        "--type",
        "mkp",
        "--dataset",
        "WEISH",
        "--problems",
        "weish01",
        "--repeat",
        "1",
        "--seed",
        "1",
    ]

    with pytest.raises(SystemExit):
        main(argv, problem_root=problem_root, solver_root=solver_root)


def test_validate_execute_args_rejects_multiple_solvers_for_cli_run(tmp_path: Path) -> None:
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    _write_problem_yaml(problem_root / "mkp" / "WEISH" / "weish01.yaml")
    spec = ExperimentSpec(
        experiment_name="e",
        dataset="WEISH",
        problem_ids=("weish01",),
        solver_ids=("a", "b"),
        repeat=1,
    )
    with pytest.raises(ValueError, match="cli.run accepts exactly one solver"):
        validate_execute_args(spec, problem_root, solver_root)
