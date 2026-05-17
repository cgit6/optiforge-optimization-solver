from __future__ import annotations

from pathlib import Path

from mkp.experiment import DatasetEvalDecision, DatasetEvalInput, Experiment, FAIL, PASS, build


def _write_problem_yaml(path: Path, *, problem_id: str, dataset: str = "DATA") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""
problem_id: {problem_id}
dataset: {dataset}
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
capabilities:
  problem_types: [mkp]
  encodings: [binary]
  directions: [max]
stop_condition:
  type: max_iterations
  max_iterations: 2
params:
  - {}
""".strip(),
        encoding="utf-8",
    )


def _config_text(*, seed: str = "[1, 3]", collects: int = 1, datasets: str | None = None) -> str:
    dataset_block = datasets or """
  - experiment-id: exp1
    dataset: DATA
    problems: [p1]
    type: mkp
"""
    return f"""
experiment_name: exp_search
seed: {seed}
collects: {collects}
worker: 1
solvers: [stub_solver]
repeat: 1
evaluation:
  name: custom
  config: {{}}
dataset_settings:
{dataset_block}
""".strip()


def _project(tmp_path: Path, *, seed: str = "[1, 3]", collects: int = 1, datasets: str | None = None) -> tuple[Experiment, Path, Path]:
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    exp_path = tmp_path / "exp_cfg.yaml"
    _write_problem_yaml(problem_root / "DATA" / "p1.yaml", problem_id="p1")
    _write_problem_yaml(problem_root / "DATA" / "p2.yaml", problem_id="p2")
    _write_solver_yaml(solver_root / "stub_solver.yaml")
    exp_path.write_text(_config_text(seed=seed, collects=collects, datasets=datasets), encoding="utf-8")
    return build(exp_path, problem_root=problem_root, solver_root=solver_root), problem_root, solver_root


def test_custom_evaluator_collects_only_passing_seed(tmp_path: Path) -> None:
    experiment, problem_root, solver_root = _project(tmp_path, seed="[1, 2]", collects=1)

    def evaluator(input_data: DatasetEvalInput) -> DatasetEvalDecision:
        passed = input_data.seed == 2
        return DatasetEvalDecision(
            passed=passed,
            verdict=PASS if passed else FAIL,
            message=f"seed={input_data.seed}",
        )

    experiment.register("custom", evaluator)
    report = experiment.run(
        problem_root=problem_root,
        solver_root=solver_root,
        output_root=tmp_path / "output",
    )

    assert report.collected_seeds == (2,)
    assert [attempt.collected for attempt in report.attempts] == [False, True]
    assert (
        tmp_path
        / "output"
        / "exp_search"
        / "collect_0001"
        / "exp1"
        / "stub_solver"
        / "param_0"
        / "summary.json"
    ).exists()


def test_dataset_fail_restarts_next_seed_from_first_dataset(tmp_path: Path) -> None:
    datasets = """
  - experiment-id: exp1
    dataset: DATA
    problems: [p1]
    type: mkp
  - experiment-id: exp2
    dataset: DATA
    problems: [p2]
    type: mkp
"""
    experiment, problem_root, solver_root = _project(tmp_path, seed="[1, 2]", collects=1, datasets=datasets)
    calls: list[tuple[int, str]] = []

    def evaluator(input_data: DatasetEvalInput) -> DatasetEvalDecision:
        calls.append((input_data.seed, input_data.dataset_setting.experiment_id))
        passed = not (input_data.seed == 1 and input_data.dataset_setting.experiment_id == "exp2")
        return DatasetEvalDecision(
            passed=passed,
            verdict=PASS if passed else FAIL,
            message=input_data.dataset_setting.experiment_id,
        )

    experiment.register("custom", evaluator)
    report = experiment.run(
        problem_root=problem_root,
        solver_root=solver_root,
        output_root=tmp_path / "output",
    )

    assert report.collected_seeds == (2,)
    assert calls == [(1, "exp1"), (1, "exp2"), (2, "exp1"), (2, "exp2")]


def test_collects_multiple_seeds_without_overwrite(tmp_path: Path) -> None:
    experiment, problem_root, solver_root = _project(tmp_path, seed="[1, 3]", collects=2)
    experiment.register(
        "custom",
        lambda _input: DatasetEvalDecision(passed=True, verdict=PASS, message="ok"),
    )

    report = experiment.run(
        problem_root=problem_root,
        solver_root=solver_root,
        output_root=tmp_path / "output",
    )

    assert report.collected_seeds == (1, 2)
    assert (tmp_path / "output" / "exp_search" / "collect_0001" / "collect_summary.json").exists()
    assert (tmp_path / "output" / "exp_search" / "collect_0002" / "collect_summary.json").exists()


def test_failed_seed_does_not_write_variant_outputs(tmp_path: Path) -> None:
    experiment, problem_root, solver_root = _project(tmp_path, seed="[1, 1]", collects=1)
    experiment.register(
        "custom",
        lambda _input: DatasetEvalDecision(passed=False, verdict=FAIL, message="failed"),
    )

    report = experiment.run(
        problem_root=problem_root,
        solver_root=solver_root,
        output_root=tmp_path / "output",
    )

    assert report.collected_seeds == ()
    assert not (tmp_path / "output" / "exp_search" / "collect_0001").exists()
    assert (tmp_path / "output" / "exp_search" / "summary.json").exists()
