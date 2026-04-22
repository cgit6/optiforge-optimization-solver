from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from mkp.contracts import ProblemModel, RunResult
from mkp.result_writer import ResultWriter
from mkp.validator import Validator


def _build_problem() -> ProblemModel:
    return ProblemModel(
        problem_id="weish01",
        dataset="WEISH",
        items=3,
        dim=2,
        values=np.array([10, 20, 30]),
        weights=np.array([[2, 1], [3, 2], [4, 3]]),
        capacities=np.array([10, 8]),
        best_known=50,
    )


def _build_run_result(solution: np.ndarray, objective: int, *, feasible: bool = True, error: str | None = None):
    return RunResult(
        problem_id="weish01",
        solver_id="stub_solver",
        repeat_index=0,
        seed=42,
        best_solution=solution,
        best_objective=objective,
        feasible=feasible,
        evaluation_count=10,
        stop_reason="max_iterations_reached",
        runtime=0.1,
        error=error,
    )


def test_result_writer_writes_single_run_with_standard_fields(tmp_path: Path):
    writer = ResultWriter(experiment_id="exp_001", output_root=tmp_path)
    validator = Validator()
    problem = _build_problem()
    run = _build_run_result(np.array([1, 1, 1]), 60)
    report = validator.validate(problem, run)

    writer.write_run(run, report)

    runs_csv = tmp_path / "exp_001" / "runs.csv"
    runs_jsonl = tmp_path / "exp_001" / "runs.jsonl"
    assert runs_csv.exists()
    assert runs_jsonl.exists()

    with runs_csv.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1
    assert rows[0]["problem_id"] == "weish01"
    assert rows[0]["solver_id"] == "stub_solver"
    assert rows[0]["best_objective"] == "60"

    with runs_jsonl.open("r", encoding="utf-8") as fh:
        line = fh.readline().strip()
    payload = json.loads(line)
    assert payload["problem_id"] == "weish01"
    assert payload["feasible"] is True
    assert payload["objective_valid"] is True


def test_result_writer_summary_aggregation_exclusion_rules(tmp_path: Path):
    writer = ResultWriter(experiment_id="exp_002", output_root=tmp_path)
    validator = Validator()
    problem = _build_problem()

    valid_run = _build_run_result(np.array([1, 1, 1]), 60)
    infeasible_run = _build_run_result(np.array([0, 0, 3]), 90, feasible=False)
    mismatch_run = _build_run_result(np.array([1, 0, 1]), 41)

    entries = [
        writer.write_run(valid_run, validator.validate(problem, valid_run)),
        writer.write_run(infeasible_run, validator.validate(problem, infeasible_run)),
        writer.write_run(mismatch_run, validator.validate(problem, mismatch_run)),
    ]

    summary = writer.build_summary(entries)
    writer.write_summary(summary)

    assert summary["total_runs"] == 3
    assert summary["feasible_rate"] == 2 / 3
    assert summary["avg_objective"] == 60
    assert summary["best_objective"] == 60
    assert summary["excluded_counts"]["infeasible"] == 1
    assert summary["excluded_counts"]["objective_mismatch"] == 1

    summary_json = tmp_path / "exp_002" / "summary.json"
    summary_csv = tmp_path / "exp_002" / "summary.csv"
    assert summary_json.exists()
    assert summary_csv.exists()


def test_result_writer_keeps_invalid_runs_in_outputs(tmp_path: Path):
    writer = ResultWriter(experiment_id="exp_003", output_root=tmp_path)
    validator = Validator()
    problem = _build_problem()

    invalid_run = _build_run_result(np.array([0, 0, 3]), 91, feasible=False, error="solver_warning")
    report = validator.validate(problem, invalid_run)
    entry = writer.write_run(invalid_run, report)

    assert entry.excluded_reason in {"infeasible", "objective_mismatch"}
    assert entry.error == "solver_warning"

    with (tmp_path / "exp_003" / "runs.jsonl").open("r", encoding="utf-8") as fh:
        payload = json.loads(fh.readline())
    assert payload["error"] == "solver_warning"
    assert payload["excluded_reason"] is not None
