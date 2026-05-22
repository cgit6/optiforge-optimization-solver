from __future__ import annotations

import csv
from dataclasses import asdict
import json
from pathlib import Path

import numpy as np
import pytest

from mkp.engine.models import SolveResult, RunTask
from mkp.problem import ProblemModel, TSPProblem, ValidationReport
from mkp.simulator import SimulatorResult, SimulatorRunRow
from mkp.tools.show import write_simulator_result
from mkp.tools.stat import SummaryMeta, SummaryReport, result_entries, summarize
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


def _build_tsp_problem(*, best_known: int = 26) -> TSPProblem:
    return TSPProblem(
        problem_id="tsp5",
        dataset="SMALL",
        n_cities=5,
        best_known=best_known,
        distance_matrix=np.array(
            [
                [0, 2, 9, 10, 7],
                [2, 0, 6, 4, 3],
                [9, 6, 0, 8, 5],
                [10, 4, 8, 0, 6],
                [7, 3, 5, 6, 0],
            ]
        ),
    )


def _build_solve_result(
    solution: np.ndarray,
    objective: int,
    *,
    solver_id: str = "stub_solver",
    feasible: bool = True,
    error: str | None = None,
):
    return SolveResult(
        problem_id="weish01",
        solver_id=solver_id,
        run_seed=42,
        best_solution=solution,
        best_objective=objective,
        feasible=feasible,
        evaluation_count=10,
        stop_reason="max_iterations_reached",
        runtime=0.1,
        linprog_runtime=0.0,
        error=error,
    )


def _summary_meta(
    *,
    solver_id: str = "stub_solver",
    param_set_index: int = 0,
    params: dict | None = None,
) -> SummaryMeta:
    return SummaryMeta(
        solver_id=solver_id,
        param_set_index=param_set_index,
        params={} if params is None else params,
    )


def _simulator_result(
    rows: tuple[SimulatorRunRow, ...],
    *,
    params_by_variant: dict[tuple[str, int], dict] | None = None,
) -> SimulatorResult:
    variant_params = params_by_variant or {("stub_solver", 0): {}}
    return SimulatorResult(rows=rows, variant_params=variant_params)


def _make_row(
    solve_result: SolveResult,
    validation_report,
    *,
    repeat_index: int,
    param_set_index: int = 0,
) -> SimulatorRunRow:
    task = RunTask(
        problem_id=solve_result.problem_id,
        dataset="WEISH",
        solver_id=solve_result.solver_id,
        repeat_index=repeat_index,
        task_seed=solve_result.run_seed,
        param_set_index=param_set_index,
    )
    return SimulatorRunRow(task=task, solve_result=solve_result, validation_report=validation_report)


def test_write_simulator_result_writes_single_run_with_standard_fields(tmp_path: Path):
    problem = _build_problem()
    run = _build_solve_result(np.array([1, 1, 1]), 60)
    report = problem.validate(run)
    row = _make_row(run, report, repeat_index=0)

    stale_runs_jsonl = tmp_path / "exp_001" / "stub_solver" / "param_0" / "runs.jsonl"
    stale_runs_jsonl.parent.mkdir(parents=True, exist_ok=True)
    stale_runs_jsonl.write_text('{"stale": true}\n', encoding="utf-8")

    simulator_result = _simulator_result((row,))
    write_simulator_result(simulator_result, experiment_name="exp_001", output_root=tmp_path)

    runs_csv = tmp_path / "exp_001" / "stub_solver" / "param_0" / "runs.csv"
    runs_json = tmp_path / "exp_001" / "stub_solver" / "param_0" / "runs.json"
    assert runs_csv.exists()
    assert runs_json.exists()
    assert not stale_runs_jsonl.exists()

    with runs_csv.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1
    assert rows[0]["dataset"] == "WEISH"
    assert rows[0]["problem_id"] == "weish01"
    assert rows[0]["solver_id"] == "stub_solver"
    assert rows[0]["param_set_index"] == "0"
    assert rows[0]["repeat_index"] == "0"
    assert rows[0]["run_seed"] == "42"
    assert rows[0]["best_objective"] == "60"
    assert rows[0]["linprog_runtime"] == "0.0"
    assert json.loads(rows[0]["metadata_json"]) == {"solve": {}, "validation": {}}

    with runs_json.open("r", encoding="utf-8") as fh:
        payloads = json.load(fh)
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["dataset"] == "WEISH"
    assert payload["problem_id"] == "weish01"
    assert payload["param_set_index"] == 0
    assert payload["repeat_index"] == 0
    assert payload["run_seed"] == 42
    assert payload["linprog_runtime"] == 0.0
    assert payload["feasible"] is True
    assert payload["objective_valid"] is True
    assert payload["best_known"] == 50
    assert payload["best_known_reached"] is True
    assert payload["best_known_gap"] == -10
    assert payload["metadata"] == {"solve": {}, "validation": {}}
    assert "metadata_json" not in payload


def test_summary_aggregation_and_exclusion_rules(tmp_path: Path):
    problem = _build_problem()

    valid_run = _build_solve_result(np.array([1, 1, 1]), 60)
    infeasible_run = _build_solve_result(np.array([0, 0, 3]), 90, feasible=False)
    mismatch_run = _build_solve_result(np.array([1, 0, 1]), 41)

    rows = (
        _make_row(valid_run, problem.validate(valid_run), repeat_index=0),
        _make_row(infeasible_run, problem.validate(infeasible_run), repeat_index=1),
        _make_row(mismatch_run, problem.validate(mismatch_run), repeat_index=2),
    )

    simulator_result = _simulator_result(rows, params_by_variant={("stub_solver", 0): {"z": 0.08, "pop_size": 20}})
    entries = result_entries(simulator_result)
    summary = summarize(entries, meta=_summary_meta(params={"z": 0.08, "pop_size": 20}))
    write_simulator_result(simulator_result, experiment_name="exp_002", output_root=tmp_path)
    assert isinstance(summary, SummaryReport)

    overall = summary.overall
    groups = summary.by_problem_solver
    assert len(groups) == 1
    group = groups[0]

    assert overall.total_runs == 3
    assert overall.valid_run_count == 1
    assert overall.feasible_rate == 2 / 3
    assert overall.meta.solver_id == "stub_solver"
    assert overall.meta.param_set_index == 0
    assert overall.meta.params == {"z": 0.08, "pop_size": 20}
    assert overall.best_known == 50
    assert overall.avg_objective == 60
    assert overall.std_objective == 0.0
    assert overall.best_objective == 60
    assert overall.worst_objective == 60
    assert overall.pdev == -20.0
    assert overall.excluded_counts.infeasible == 1
    assert overall.excluded_counts.objective_mismatch == 1
    assert overall.excluded_counts.runtime_error == 0

    assert group.problem_id == "weish01"
    assert group.dataset == "WEISH"
    assert group.run_count == 3
    assert group.valid_run_count == 1
    assert group.best_known == 50
    assert group.std_objective == 0.0
    assert group.worst_objective == 60
    assert group.pdev == -20.0
    assert group.best_known_reached_count == 1
    assert group.best_known_gap_min == -10
    assert group.best_known_gap_avg == -10

    summary_payload = asdict(summary)
    assert summary_payload["overall"]["total_runs"] == 3
    assert summary_payload["overall"]["meta"] == {
        "solver_id": "stub_solver",
        "param_set_index": 0,
        "params": {"z": 0.08, "pop_size": 20},
        "experiment": {},
    }
    assert summary_payload["overall"]["pdev"] == -20.0
    assert summary_payload["by_problem_solver"][0]["problem_id"] == "weish01"
    assert "solver_id" not in summary_payload["by_problem_solver"][0]
    assert "param_set_index" not in summary_payload["by_problem_solver"][0]
    assert summary_payload["by_problem_solver"][0]["worst_objective"] == 60

    summary_json = tmp_path / "exp_002" / "stub_solver" / "param_0" / "summary.json"
    summary_csv = tmp_path / "exp_002" / "stub_solver" / "param_0" / "summary.csv"
    assert summary_json.exists()
    assert summary_csv.exists()

    with summary_csv.open("r", encoding="utf-8", newline="") as fh:
        summary_rows = list(csv.DictReader(fh))
    assert summary_rows[0]["std_objective"] == "0.0"
    assert summary_rows[0]["worst_objective"] == "60"
    assert summary_rows[0]["pdev"] == "-20.0"
    assert json.loads(summary_rows[0]["meta_json"]) == {
        "solver_id": "stub_solver",
        "param_set_index": 0,
        "params": {"z": 0.08, "pop_size": 20},
        "experiment": {},
    }
    assert "solver_id" not in summary_rows[0]
    assert "param_set_index" not in summary_rows[0]
    assert summary_rows[1]["std_objective"] == "0.0"
    assert summary_rows[1]["worst_objective"] == "60"
    assert summary_rows[1]["pdev"] == "-20.0"
    assert json.loads(summary_rows[1]["meta_json"]) == {
        "solver_id": "stub_solver",
        "param_set_index": 0,
        "params": {"z": 0.08, "pop_size": 20},
        "experiment": {},
    }


def test_summarize_rejects_mixed_param_sets() -> None:
    problem = _build_problem()
    run_a = _build_solve_result(np.array([1, 1, 1]), 60)
    run_b = _build_solve_result(np.array([1, 0, 1]), 40)
    rows = (
        _make_row(run_a, problem.validate(run_a), repeat_index=0, param_set_index=0),
        _make_row(run_b, problem.validate(run_b), repeat_index=0, param_set_index=1),
    )

    with pytest.raises(ValueError, match="exactly one solver variant"):
        summarize(result_entries(_simulator_result(rows)), meta=_summary_meta())


def test_summarize_rejects_mixed_solvers() -> None:
    problem = _build_problem()
    run_a = _build_solve_result(np.array([1, 1, 1]), 60, solver_id="stub_solver")
    run_b = _build_solve_result(np.array([1, 0, 1]), 40, solver_id="other_solver")
    rows = (
        _make_row(run_a, problem.validate(run_a), repeat_index=0, param_set_index=0),
        _make_row(run_b, problem.validate(run_b), repeat_index=1, param_set_index=0),
    )

    with pytest.raises(ValueError, match="exactly one solver variant"):
        summarize(result_entries(_simulator_result(rows)), meta=_summary_meta())


def test_write_splits_param_sets_and_writes_each_variant_meta(tmp_path: Path) -> None:
    problem = _build_problem()
    run_a = _build_solve_result(np.array([1, 1, 1]), 60)
    run_b = _build_solve_result(np.array([1, 0, 1]), 40)
    rows = (
        _make_row(run_a, problem.validate(run_a), repeat_index=0, param_set_index=0),
        _make_row(run_b, problem.validate(run_b), repeat_index=0, param_set_index=1),
    )
    simulator_result = _simulator_result(
        rows,
        params_by_variant={
            ("stub_solver", 0): {"z": 0.08},
            ("stub_solver", 1): {"z": 0.03},
        },
    )

    write_simulator_result(simulator_result, experiment_name="exp_params", output_root=tmp_path)

    for param_set_index, z in ((0, 0.08), (1, 0.03)):
        summary_path = tmp_path / "exp_params" / "stub_solver" / f"param_{param_set_index}" / "summary.json"
        with summary_path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
        assert payload["overall"]["meta"] == {
            "solver_id": "stub_solver",
            "param_set_index": param_set_index,
            "params": {"z": z},
            "experiment": {},
        }


def test_write_summary_meta_includes_experiment_metadata(tmp_path: Path) -> None:
    problem = _build_problem()
    run = _build_solve_result(np.array([1, 1, 1]), 60)
    row = _make_row(run, problem.validate(run), repeat_index=0)
    simulator_result = _simulator_result((row,), params_by_variant={("stub_solver", 0): {"z": 0.08}})

    write_simulator_result(
        simulator_result,
        experiment_name="exp_meta",
        output_root=tmp_path,
        variant_metadata={
            ("stub_solver", 0): {
                "stage": "final",
                "algorithm": "HSMSCA",
                "combo_id": "final_hsmsca",
                "seed": 7,
            }
        },
    )

    summary_path = tmp_path / "exp_meta" / "stub_solver" / "param_0" / "summary.json"
    with summary_path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    assert payload["overall"]["meta"]["experiment"] == {
        "stage": "final",
        "algorithm": "HSMSCA",
        "combo_id": "final_hsmsca",
        "seed": 7,
    }


def test_write_keeps_invalid_runs_in_outputs(tmp_path: Path):
    problem = _build_problem()

    invalid_run = _build_solve_result(np.array([0, 0, 3]), 91, feasible=False, error="solver_warning")
    report = problem.validate(invalid_run)
    row = _make_row(invalid_run, report, repeat_index=0)

    simulator_result = _simulator_result((row,))
    write_simulator_result(simulator_result, experiment_name="exp_003", output_root=tmp_path)

    entry = _build_entry(invalid_run, report, dataset="WEISH", repeat_index=0, param_set_index=0)
    assert entry.excluded_reason in {"infeasible", "objective_mismatch"}
    assert entry.error == "solver_warning"
    assert asdict(entry.metadata)["validation"] == {}

    with (tmp_path / "exp_003" / "stub_solver" / "param_0" / "runs.json").open("r", encoding="utf-8") as fh:
        payload = json.load(fh)[0]
    assert payload["error"] == "solver_warning"
    assert payload["excluded_reason"] is not None
    assert payload["metadata"] == {"solve": {}, "validation": {}}


def test_runtime_error_is_excluded_separately():
    problem = _build_problem()

    # objective 正確且可行，但 solver 帶 error，應歸類 runtime_error
    error_run = _build_solve_result(np.array([1, 1, 0]), 30, feasible=True, error="runtime_fail")
    report = problem.validate(error_run)
    entry = _build_entry(error_run, report, dataset="WEISH", repeat_index=0, param_set_index=0)
    summary = summarize([entry], meta=_summary_meta())

    assert entry.excluded_reason == "runtime_error"
    assert summary.overall.excluded_counts.runtime_error == 1
    assert summary.overall.valid_run_count == 1


def test_summary_adds_std_worst_and_pdev_for_multiple_valid_mkp_runs():
    problem = _build_problem()

    run_a = _build_solve_result(np.array([1, 1, 1]), 60)
    run_b = _build_solve_result(np.array([1, 0, 1]), 40)
    entries = [
        _build_entry(run_a, problem.validate(run_a), dataset="WEISH", repeat_index=0, param_set_index=0),
        _build_entry(run_b, problem.validate(run_b), dataset="WEISH", repeat_index=1, param_set_index=0),
    ]

    summary = summarize(entries, meta=_summary_meta())
    overall = summary.overall
    group = summary.by_problem_solver[0]

    assert overall.avg_objective == 50.0
    assert np.isclose(overall.std_objective, np.sqrt(200.0))
    assert overall.best_objective == 60
    assert overall.worst_objective == 40
    assert overall.pdev == 0.0

    assert group.avg_objective == 50.0
    assert np.isclose(group.std_objective, np.sqrt(200.0))
    assert group.best_objective == 60
    assert group.worst_objective == 40
    assert group.pdev == 0.0


def test_summary_uses_min_direction_for_worst_and_pdev():
    problem = _build_tsp_problem()
    best_run = SolveResult(
        problem_id="tsp5",
        solver_id="tsp_solver",
        run_seed=0,
        best_solution=np.array([0, 1, 3, 2, 4]),
        best_objective=26,
        feasible=True,
        evaluation_count=5,
        stop_reason="done",
        runtime=0.0,
    )
    worse_run = SolveResult(
        problem_id="tsp5",
        solver_id="tsp_solver",
        run_seed=1,
        best_solution=np.array([0, 1, 2, 3, 4]),
        best_objective=29,
        feasible=True,
        evaluation_count=5,
        stop_reason="done",
        runtime=0.0,
    )
    entries = [
        _build_entry(best_run, problem.validate(best_run), dataset="SMALL", repeat_index=0, param_set_index=0),
        _build_entry(worse_run, problem.validate(worse_run), dataset="SMALL", repeat_index=1, param_set_index=0),
    ]

    summary = summarize(entries, meta=_summary_meta(solver_id="tsp_solver"))
    group = summary.by_problem_solver[0]

    assert group.direction == "min"
    assert group.best_objective == 26
    assert group.worst_objective == 29
    assert group.avg_objective == 27.5
    assert np.isclose(group.std_objective, np.sqrt(4.5))
    assert np.isclose(group.pdev, (27.5 - 26.0) / 26.0 * 100.0)


def test_multi_objective_runs_are_saved_without_scalar_summary_stats(tmp_path: Path):
    run = SolveResult(
        problem_id="multi01",
        solver_id="multi_solver",
        run_seed=42,
        best_solution=np.array([1.0, 0.5]),
        best_objective=(10, 2.5),
        feasible=True,
        evaluation_count=5,
        stop_reason="done",
        runtime=0.1,
    )
    report = ValidationReport(
        is_feasible=True,
        feasibility_violations=(),
        objective_valid=True,
        recomputed_objective=(10, 2.5),
        objective_mismatch=False,
        best_known_reached=True,
        best_known_gap=(-1, -0.5),
        problem_type="multi",
        encoding="continuous",
        direction=("max", "min"),
        best_known=(9, 3.0),
    )
    task = RunTask(
        problem_id="multi01",
        dataset="MULTI",
        problem_type="multi",
        solver_id="multi_solver",
        repeat_index=0,
        task_seed=42,
        param_set_index=0,
    )
    simulator_result = SimulatorResult(
        rows=(SimulatorRunRow(task=task, solve_result=run, validation_report=report),),
        variant_params={("multi_solver", 0): {}},
    )

    write_simulator_result(simulator_result, experiment_name="exp_multi", output_root=tmp_path)

    with (tmp_path / "exp_multi" / "multi_solver" / "param_0" / "runs.json").open("r", encoding="utf-8") as fh:
        runs_payload = json.load(fh)
    assert runs_payload[0]["best_objective"] == [10, 2.5]
    assert runs_payload[0]["best_known"] == [9, 3.0]
    assert runs_payload[0]["best_known_gap"] == [-1, -0.5]
    assert runs_payload[0]["direction"] == ["max", "min"]

    with (tmp_path / "exp_multi" / "multi_solver" / "param_0" / "runs.csv").open(
        "r",
        encoding="utf-8",
        newline="",
    ) as fh:
        rows = list(csv.DictReader(fh))
    assert json.loads(rows[0]["best_objective"]) == [10, 2.5]
    assert json.loads(rows[0]["direction"]) == ["max", "min"]

    with (tmp_path / "exp_multi" / "multi_solver" / "param_0" / "summary.json").open(
        "r",
        encoding="utf-8",
    ) as fh:
        summary_payload = json.load(fh)
    overall = summary_payload["overall"]
    group = summary_payload["by_problem_solver"][0]
    assert overall["valid_run_count"] == 1
    assert overall["avg_objective"] is None
    assert overall["std_objective"] is None
    assert overall["best_objective"] is None
    assert overall["worst_objective"] is None
    assert overall["pdev"] is None
    assert group["valid_run_count"] == 1
    assert group["avg_objective"] is None
    assert group["best_known_gap_min"] is None
    assert group["best_known_gap_avg"] is None
