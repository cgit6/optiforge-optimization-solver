from __future__ import annotations

import csv
from dataclasses import asdict
import json
from pathlib import Path

import numpy as np

from mkp.engine.models import ProblemModel, SolveResult, RunTask
from mkp.simulator import SimulatorResult, SimulatorRunRow
from mkp.solver.validator import Validator
from mkp.tools.show import write_simulator_result
from mkp.tools.stat import SummaryReport, result_entries, summarize
from mkp.tools.stat import _build_entry  # 內部函式：保留覆蓋率


def _build_problem(*, best_known: int = 50) -> ProblemModel:
    return ProblemModel(
        problem_id="weish01",
        dataset="WEISH",
        items=3,
        dim=2,
        values=np.array([10, 20, 30]),
        weights=np.array([[2, 1], [3, 2], [4, 3]]),
        capacities=np.array([10, 8]),
        best_known=best_known,
    )


def _build_solve_result(solution: np.ndarray, objective: int, *, feasible: bool = True, error: str | None = None):
    return SolveResult(
        problem_id="weish01",
        solver_id="stub_solver",
        seed=42,
        best_solution=solution,
        best_objective=objective,
        feasible=feasible,
        evaluation_count=10,
        stop_reason="max_iterations_reached",
        runtime=0.1,
        linprog_runtime=0.0,
        error=error,
    )


def _make_row(solve_result: SolveResult, validation_report, *, repeat_index: int) -> SimulatorRunRow:
    task = RunTask(
        problem_id=solve_result.problem_id,
        dataset="WEISH",
        solver_id=solve_result.solver_id,
        repeat_index=repeat_index,
        seed=solve_result.seed,
    )
    return SimulatorRunRow(task=task, solve_result=solve_result, validation_report=validation_report)


def test_write_simulator_result_writes_single_run_with_standard_fields(tmp_path: Path):
    validator = Validator()
    problem = _build_problem()
    run = _build_solve_result(np.array([1, 1, 1]), 60)
    report = validator.validate(problem, run)
    row = _make_row(run, report, repeat_index=0)

    stale_runs_jsonl = tmp_path / "exp_001" / "runs.jsonl"
    stale_runs_jsonl.parent.mkdir(parents=True, exist_ok=True)
    stale_runs_jsonl.write_text('{"stale": true}\n', encoding="utf-8")

    simulator_result = SimulatorResult(rows=(row,))
    entries = result_entries(simulator_result)
    summary = summarize(entries)
    write_simulator_result(simulator_result, entries, summary, experiment_id="exp_001", output_root=tmp_path)

    runs_csv = tmp_path / "exp_001" / "runs.csv"
    runs_json = tmp_path / "exp_001" / "runs.json"
    assert runs_csv.exists()
    assert runs_json.exists()
    assert not stale_runs_jsonl.exists()

    with runs_csv.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1
    assert rows[0]["problem_id"] == "weish01"
    assert rows[0]["solver_id"] == "stub_solver"
    assert rows[0]["repeat_index"] == "0"
    assert rows[0]["best_objective"] == "60"
    assert rows[0]["linprog_runtime"] == "0.0"
    assert json.loads(rows[0]["metadata_json"]) == {"solve": {}, "validation": {}}

    with runs_json.open("r", encoding="utf-8") as fh:
        payloads = json.load(fh)
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["problem_id"] == "weish01"
    assert payload["repeat_index"] == 0
    assert payload["linprog_runtime"] == 0.0
    assert payload["feasible"] is True
    assert payload["objective_valid"] is True
    assert payload["best_known"] == 50
    assert payload["best_known_reached"] is True
    assert payload["best_known_gap"] == -10
    assert payload["metadata"] == {"solve": {}, "validation": {}}
    assert "metadata_json" not in payload


def test_summary_aggregation_and_exclusion_rules(tmp_path: Path):
    validator = Validator()
    problem = _build_problem()

    valid_run = _build_solve_result(np.array([1, 1, 1]), 60)
    infeasible_run = _build_solve_result(np.array([0, 0, 3]), 90, feasible=False)
    mismatch_run = _build_solve_result(np.array([1, 0, 1]), 41)

    rows = (
        _make_row(valid_run, validator.validate(problem, valid_run), repeat_index=0),
        _make_row(infeasible_run, validator.validate(problem, infeasible_run), repeat_index=1),
        _make_row(mismatch_run, validator.validate(problem, mismatch_run), repeat_index=2),
    )

    simulator_result = SimulatorResult(rows=rows)
    entries = result_entries(simulator_result)
    summary = summarize(entries)
    write_simulator_result(simulator_result, entries, summary, experiment_id="exp_002", output_root=tmp_path)
    assert isinstance(summary, SummaryReport)

    overall = summary.overall
    groups = summary.by_problem_solver
    assert len(groups) == 1
    group = groups[0]

    assert overall.total_runs == 3
    assert overall.valid_run_count == 1
    assert overall.feasible_rate == 2 / 3
    assert overall.avg_objective == 60
    assert overall.best_objective == 60
    assert overall.excluded_counts.infeasible == 1
    assert overall.excluded_counts.objective_mismatch == 1
    assert overall.excluded_counts.runtime_error == 0

    assert group.problem_id == "weish01"
    assert group.solver_id == "stub_solver"
    assert group.run_count == 3
    assert group.valid_run_count == 1
    assert group.best_known == 50
    assert group.best_known_reached_count == 1
    assert group.best_known_gap_min == -10
    assert group.best_known_gap_avg == -10

    summary_payload = asdict(summary)
    assert summary_payload["overall"]["total_runs"] == 3
    assert summary_payload["by_problem_solver"][0]["problem_id"] == "weish01"

    summary_json = tmp_path / "exp_002" / "summary.json"
    summary_csv = tmp_path / "exp_002" / "summary.csv"
    assert summary_json.exists()
    assert summary_csv.exists()


def test_write_keeps_invalid_runs_in_outputs(tmp_path: Path):
    validator = Validator()
    problem = _build_problem()

    invalid_run = _build_solve_result(np.array([0, 0, 3]), 91, feasible=False, error="solver_warning")
    report = validator.validate(problem, invalid_run)
    row = _make_row(invalid_run, report, repeat_index=0)

    simulator_result = SimulatorResult(rows=(row,))
    entries = result_entries(simulator_result)
    summary = summarize(entries)
    write_simulator_result(simulator_result, entries, summary, experiment_id="exp_003", output_root=tmp_path)

    entry = _build_entry(invalid_run, report, repeat_index=0)
    assert entry.excluded_reason in {"infeasible", "objective_mismatch"}
    assert entry.error == "solver_warning"
    assert asdict(entry.metadata)["validation"] == {}

    with (tmp_path / "exp_003" / "runs.json").open("r", encoding="utf-8") as fh:
        payload = json.load(fh)[0]
    assert payload["error"] == "solver_warning"
    assert payload["excluded_reason"] is not None
    assert payload["metadata"] == {"solve": {}, "validation": {}}


def test_runtime_error_is_excluded_separately():
    validator = Validator()
    problem = _build_problem()

    # objective 正確且可行，但 solver 帶 error，應歸類 runtime_error
    error_run = _build_solve_result(np.array([1, 1, 0]), 30, feasible=True, error="runtime_fail")
    report = validator.validate(problem, error_run)
    entry = _build_entry(error_run, report, repeat_index=0)
    summary = summarize([entry])

    assert entry.excluded_reason == "runtime_error"
    assert summary.overall.excluded_counts.runtime_error == 1
    assert summary.overall.valid_run_count == 1
