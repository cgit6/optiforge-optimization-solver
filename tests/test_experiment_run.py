from __future__ import annotations

from pathlib import Path

from mkp.experiment import CheckResult, EvaluationReport, Experiment, FAIL, STRICT_PASS, build


def _write_problem_yaml(path: Path, *, problem_id: str = "p1", dataset: str = "DATA") -> None:
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


def _config_text(*, seed: str = "[1, 3]", collects: int = 1) -> str:
    return f"""
experiment_name: exp_search
seed: {seed}
collects: {collects}
worker: 1
solvers: [stub_solver]
repeat: 1
stages:
  transfer:
    variants:
      - combo_id: transfer_stub_v
        solver: stub_solver
        param_set_index: 0
        algorithm: HSMSCA
        transfer_type: V
  param:
    variants:
      - combo_id: param_stub
        solver: stub_solver
        param_set_index: 0
        algorithm: HSMSCA
  final:
    variants:
      - combo_id: final_stub
        solver: stub_solver
        param_set_index: 0
        algorithm: HSMSCA
dataset_settings:
  - experiment-id: exp1
    dataset: DATA
    problems: [p1]
    type: mkp
""".strip()


def _project(tmp_path: Path, *, seed: str = "[1, 3]", collects: int = 1) -> tuple[Experiment, Path, Path]:
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    exp_path = tmp_path / "exp_cfg.yaml"
    _write_problem_yaml(problem_root / "DATA" / "p1.yaml")
    _write_solver_yaml(solver_root / "stub_solver.yaml")
    exp_path.write_text(_config_text(seed=seed, collects=collects), encoding="utf-8")
    return build(exp_path, problem_root=problem_root, solver_root=solver_root), problem_root, solver_root


def _custom_report(seed: int, verdict: str) -> EvaluationReport:
    return EvaluationReport(
        seed=seed,
        verdict=verdict,
        checks=(CheckResult(name="custom", verdict=verdict),),
        problem_metrics=(),
        combo_metrics=(),
    )


def test_custom_evaluator_collects_only_passing_seed(tmp_path: Path) -> None:
    experiment, problem_root, solver_root = _project(tmp_path, seed="[1, 2]", collects=1)
    experiment.register(
        "custom",
        lambda _cfg, seed, _summaries: _custom_report(seed, STRICT_PASS if seed == 2 else FAIL),
    )

    report = experiment.run(
        eval_name="custom",
        problem_root=problem_root,
        solver_root=solver_root,
        output_root=tmp_path / "output",
    )

    assert report.collected_seeds == (2,)
    assert [attempt.collected for attempt in report.attempts] == [False, True]
    assert not (tmp_path / "output" / "exp_search" / "collect_0000").exists()
    assert (
        tmp_path
        / "output"
        / "exp_search"
        / "collect_0001"
        / "exp1"
        / "transfer"
        / "stub_solver"
        / "param_0"
        / "summary.json"
    ).exists()


def test_collects_multiple_seeds_without_overwrite(tmp_path: Path) -> None:
    experiment, problem_root, solver_root = _project(tmp_path, seed="[1, 3]", collects=2)
    experiment.register("custom", lambda _cfg, seed, _summaries: _custom_report(seed, STRICT_PASS))

    report = experiment.run(
        eval_name="custom",
        problem_root=problem_root,
        solver_root=solver_root,
        output_root=tmp_path / "output",
    )

    assert report.collected_seeds == (1, 2)
    assert (tmp_path / "output" / "exp_search" / "collect_0001" / "collect_summary.json").exists()
    assert (tmp_path / "output" / "exp_search" / "collect_0002" / "collect_summary.json").exists()


def test_failed_seed_does_not_write_variant_outputs(tmp_path: Path) -> None:
    experiment, problem_root, solver_root = _project(tmp_path, seed="[1, 1]", collects=1)
    experiment.register("custom", lambda _cfg, seed, _summaries: _custom_report(seed, FAIL))

    report = experiment.run(
        eval_name="custom",
        problem_root=problem_root,
        solver_root=solver_root,
        output_root=tmp_path / "output",
    )

    assert report.collected_seeds == ()
    assert not (tmp_path / "output" / "exp_search" / "collect_0001").exists()
    assert (tmp_path / "output" / "exp_search" / "summary.json").exists()
