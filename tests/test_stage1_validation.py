from __future__ import annotations

from pathlib import Path

from mkp.valid.stage1_validation import (
    ComparableResult,
    ValidationScenario,
    build_smoke_scenarios,
    check_refactor_reproducible,
    classify_diff,
    ensure_problem_yaml,
)


def test_build_smoke_scenarios_has_expected_minimum_shape():
    scenarios = build_smoke_scenarios()
    assert len(scenarios) >= 1
    first = scenarios[0]
    assert isinstance(first, ValidationScenario)
    assert len(first.seeds) == 3


def test_check_refactor_reproducible_true_for_stable_app_stub(tmp_path: Path):
    scenario = ValidationScenario(dataset="WEISH", problem_id="weish01", solver_id="bsma", seeds=(101, 202, 303))

    def stable_app(_argv, **_kwargs):
        class _Run:
            best_objective = 60
            stop_reason = "max_iterations_reached"

        class _Report:
            is_feasible = True

        return [(_Run(), _Report(), None)]

    is_repro = check_refactor_reproducible(
        scenario=scenario,
        seed=123,
        output_root=tmp_path,
        problem_root=tmp_path,
        solver_root=tmp_path,
        app_entry=stable_app,
    )
    assert is_repro is True


def test_classify_diff_behaviors():
    refactor = ComparableResult(best_objective=100, feasible=True, stop_reason="max_iterations_reached", seed=1)
    assert classify_diff(refactor, baseline_best_objective=None) == "baseline_missing"
    assert classify_diff(refactor, baseline_best_objective=100) == "match"
    assert classify_diff(refactor, baseline_best_objective=99) == "objective_mismatch"


def test_ensure_problem_yaml_creates_yaml_when_missing(tmp_path: Path):
    scenario = ValidationScenario(dataset="WEISH", problem_id="weish01", solver_id="bsma", seeds=(1, 2, 3))
    dat_dir = tmp_path / "data/WEISH"
    dat_dir.mkdir(parents=True, exist_ok=True)
    (dat_dir / "weish01.dat").write_text(
        "3 2 10\n\n1 2 3\n\n1 1 1\n2 2 2\n\n3 4\n",
        encoding="utf-8",
    )

    yaml_path = ensure_problem_yaml(repo_root=tmp_path, scenario=scenario)
    assert yaml_path.exists()
    content = yaml_path.read_text(encoding="utf-8")
    assert "problem_id: weish01" in content
