"""統計彙整模組：將模擬結果整理為標準化資料與摘要統計。"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ..engine.models import SolveResult
from ..solver.validator import ValidationReport

if TYPE_CHECKING:
    from ..simulator.core import SimulatorResult


@dataclass(frozen=True)
class ResultEntry:
    problem_type: str
    encoding: str
    direction: str
    problem_id: str
    solver_id: str
    repeat_index: int
    seed: int
    best_objective: int | float
    feasible: bool
    objective_valid: bool
    objective_mismatch: bool
    best_known: int | float | None
    best_known_reached: bool
    best_known_gap: int | float | None
    stop_reason: str
    runtime: float
    linprog_runtime: float
    evaluation_count: int
    error: str | None
    excluded_reason: str | None
    metadata: "ResultMetadata"


@dataclass(frozen=True)
class ResultMetadata:
    solve: dict[str, Any]
    validation: dict[str, Any]


@dataclass(frozen=True)
class ExcludedCounts:
    infeasible: int
    objective_mismatch: int
    runtime_error: int


@dataclass(frozen=True)
class OverallSummary:
    total_runs: int
    valid_run_count: int
    feasible_rate: float
    avg_runtime: float
    avg_evaluation_count: float
    avg_objective: int | float | None
    best_objective: int | float | None
    direction: str | None
    excluded_counts: ExcludedCounts


@dataclass(frozen=True)
class ProblemSolverSummary:
    problem_type: str
    encoding: str
    direction: str
    problem_id: str
    solver_id: str
    run_count: int
    valid_run_count: int
    feasible_rate: float
    avg_runtime: float
    avg_evaluation_count: float
    avg_objective: int | float | None
    best_objective: int | float | None
    excluded_counts: ExcludedCounts
    best_known: int | float | None
    best_known_reached_count: int
    best_known_gap_min: int | float | None
    best_known_gap_avg: int | float | None


@dataclass(frozen=True)
class SummaryReport:
    overall: OverallSummary
    by_problem_solver: list[ProblemSolverSummary]


def result_entries(simulator_result: "SimulatorResult") -> list[ResultEntry]:
    return [
        _build_entry(row.solve_result, row.validation_report, repeat_index=row.task.repeat_index)
        for row in simulator_result.rows
    ]


def summarize(entries: list[ResultEntry]) -> SummaryReport:
    valid_entries = [e for e in entries if _is_valid_for_objective_stats(e)]
    overall_direction = _single_value({e.direction for e in entries})
    overall = OverallSummary(
        total_runs=len(entries),
        valid_run_count=len(valid_entries),
        feasible_rate=(sum(1 for e in entries if e.feasible) / len(entries)) if entries else 0.0,
        avg_runtime=(sum(e.runtime for e in entries) / len(entries)) if entries else 0.0,
        avg_evaluation_count=(sum(e.evaluation_count for e in entries) / len(entries)) if entries else 0.0,
        avg_objective=(
            sum(float(e.best_objective) for e in valid_entries) / len(valid_entries) if valid_entries else None
        ),
        best_objective=_best_objective(valid_entries, overall_direction),
        direction=overall_direction,
        excluded_counts=_excluded_counts(entries),
    )

    grouped: dict[tuple[str, str, str], list[ResultEntry]] = defaultdict(list)
    for entry in entries:
        grouped[(entry.problem_type, entry.problem_id, entry.solver_id)].append(entry)

    by_problem_solver: list[ProblemSolverSummary] = []
    for (problem_type, problem_id, solver_id), bucket in sorted(grouped.items()):
        valid_bucket = [e for e in bucket if _is_valid_for_objective_stats(e)]
        direction = bucket[0].direction
        best_known_value = bucket[0].best_known
        best_known_gaps = [e.best_known_gap for e in valid_bucket if e.best_known_gap is not None]
        by_problem_solver.append(
            ProblemSolverSummary(
                problem_type=problem_type,
                encoding=bucket[0].encoding,
                direction=direction,
                problem_id=problem_id,
                solver_id=solver_id,
                run_count=len(bucket),
                valid_run_count=len(valid_bucket),
                feasible_rate=(sum(1 for e in bucket if e.feasible) / len(bucket)) if bucket else 0.0,
                avg_runtime=(sum(e.runtime for e in bucket) / len(bucket)) if bucket else 0.0,
                avg_evaluation_count=(
                    sum(e.evaluation_count for e in bucket) / len(bucket) if bucket else 0.0
                ),
                avg_objective=(
                    sum(float(e.best_objective) for e in valid_bucket) / len(valid_bucket)
                    if valid_bucket
                    else None
                ),
                best_objective=_best_objective(valid_bucket, direction),
                excluded_counts=_excluded_counts(bucket),
                best_known=best_known_value,
                best_known_reached_count=sum(1 for e in valid_bucket if e.best_known_reached is True),
                best_known_gap_min=min(best_known_gaps) if best_known_gaps else None,
                best_known_gap_avg=(
                    sum(float(gap) for gap in best_known_gaps) / len(best_known_gaps)
                    if best_known_gaps
                    else None
                ),
            )
        )

    return SummaryReport(overall=overall, by_problem_solver=by_problem_solver)


def _build_entry(
    solve_result: SolveResult,
    validation_report: ValidationReport,
    *,
    repeat_index: int,
) -> ResultEntry:
    excluded_reason: str | None = None
    if not validation_report.is_feasible:
        excluded_reason = "infeasible"
    elif validation_report.objective_mismatch:
        excluded_reason = "objective_mismatch"
    elif solve_result.error:
        excluded_reason = "runtime_error"

    linprog_runtime = float(solve_result.metadata.get("linprog_runtime", solve_result.linprog_runtime))
    metadata = ResultMetadata(
        solve=dict(solve_result.metadata),
        validation=dict(validation_report.metadata),
    )

    return ResultEntry(
        problem_type=validation_report.problem_type,
        encoding=validation_report.encoding,
        direction=validation_report.direction,
        problem_id=solve_result.problem_id,
        solver_id=solve_result.solver_id,
        repeat_index=repeat_index,
        seed=solve_result.seed,
        best_objective=solve_result.best_objective,
        feasible=validation_report.is_feasible,
        objective_valid=validation_report.objective_valid,
        objective_mismatch=validation_report.objective_mismatch,
        best_known=validation_report.best_known,
        best_known_reached=validation_report.best_known_reached,
        best_known_gap=validation_report.best_known_gap,
        stop_reason=solve_result.stop_reason,
        runtime=solve_result.runtime,
        linprog_runtime=linprog_runtime,
        evaluation_count=solve_result.evaluation_count,
        error=solve_result.error,
        excluded_reason=excluded_reason,
        metadata=metadata,
    )


def _best_objective(entries: list[ResultEntry], direction: str | None) -> int | float | None:
    values = [e.best_objective for e in entries]
    if not values:
        return None
    if direction == "min":
        return min(values)
    return max(values)


def _single_value(values: set[str]) -> str | None:
    if len(values) == 1:
        return next(iter(values))
    return None


def _is_valid_for_objective_stats(entry: ResultEntry) -> bool:
    return entry.feasible and entry.objective_valid


def _excluded_counts(entries: list[ResultEntry]) -> ExcludedCounts:
    return ExcludedCounts(
        infeasible=sum(1 for e in entries if e.excluded_reason == "infeasible"),
        objective_mismatch=sum(1 for e in entries if e.excluded_reason == "objective_mismatch"),
        runtime_error=sum(1 for e in entries if e.excluded_reason == "runtime_error"),
    )
