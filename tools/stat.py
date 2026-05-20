"""統計彙整模組：將模擬結果整理為標準化資料與摘要統計。"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import math
from typing import TYPE_CHECKING, Any, TypeVar

from ..engine.models import SolveResult
from ..problem.validation import DirectionSpec, ObjectiveGap, ObjectiveValue, ValidationReport, is_scalar_objective

if TYPE_CHECKING:
    from ..simulator.core import SimulatorResult

T = TypeVar("T")


@dataclass(frozen=True)
class ResultEntry:
    problem_type: str
    dataset: str # 題庫
    encoding: str
    direction: DirectionSpec
    problem_id: str
    solver_id: str
    param_set_index: int
    repeat_index: int
    seed: int
    best_objective: ObjectiveValue
    feasible: bool
    objective_valid: bool
    objective_mismatch: bool
    best_known: ObjectiveValue | None
    best_known_reached: bool
    best_known_gap: ObjectiveGap
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
class SummaryMeta:
    solver_id: str
    param_set_index: int
    params: dict[str, Any]
    experiment: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.solver_id.strip():
            raise ValueError("solver_id cannot be empty.")
        if self.param_set_index < 0:
            raise ValueError("param_set_index must be >= 0.")
        if not isinstance(self.params, dict):
            raise ValueError("params must be a mapping.")
        if not isinstance(self.experiment, dict):
            raise ValueError("experiment must be a mapping.")
        object.__setattr__(self, "params", dict(self.params))
        object.__setattr__(self, "experiment", dict(self.experiment))


@dataclass(frozen=True)
class OverallSummary:
    total_runs: int
    valid_run_count: int
    feasible_rate: float
    avg_runtime: float
    avg_evaluation_count: float
    meta: SummaryMeta
    best_known: ObjectiveValue | None
    avg_objective: int | float | None
    std_objective: float | None
    best_objective: int | float | None
    worst_objective: int | float | None
    pdev: float | None
    direction: DirectionSpec | None
    excluded_counts: ExcludedCounts


@dataclass(frozen=True)
class ProblemSolverSummary:
    problem_type: str
    dataset: str
    encoding: str
    direction: DirectionSpec
    problem_id: str
    run_count: int
    valid_run_count: int
    feasible_rate: float
    avg_runtime: float
    avg_evaluation_count: float
    best_known: ObjectiveValue | None
    avg_objective: int | float | None
    std_objective: float | None
    best_objective: int | float | None
    worst_objective: int | float | None
    pdev: float | None
    excluded_counts: ExcludedCounts
    best_known_reached_count: int
    best_known_gap_min: int | float | None
    best_known_gap_avg: int | float | None


@dataclass(frozen=True)
class SummaryReport:
    overall: OverallSummary
    by_problem_solver: list[ProblemSolverSummary]


def result_entries(simulator_result: "SimulatorResult") -> list[ResultEntry]:
    return [
        _build_entry(
            row.solve_result,
            row.validation_report,
            dataset=row.task.dataset,
            repeat_index=row.task.repeat_index,
            param_set_index=row.task.param_set_index,
        )
        for row in simulator_result.rows
    ]


def summarize(entries: list[ResultEntry], *, meta: SummaryMeta) -> SummaryReport:
    _validate_single_variant(entries, meta)
    valid_entries = [e for e in entries if _is_valid_for_objective_stats(e)]
    overall_direction = _single_value({e.direction for e in entries})
    overall_best_known = _single_value({e.best_known for e in entries})
    overall_avg_objective = _avg_objective(valid_entries)
    overall = OverallSummary(
        total_runs=len(entries),
        valid_run_count=len(valid_entries),
        feasible_rate=(sum(1 for e in entries if e.feasible) / len(entries)) if entries else 0.0,
        avg_runtime=(sum(e.runtime for e in entries) / len(entries)) if entries else 0.0,
        avg_evaluation_count=(sum(e.evaluation_count for e in entries) / len(entries)) if entries else 0.0,
        meta=meta,
        best_known=overall_best_known,
        avg_objective=overall_avg_objective,
        std_objective=_objective_std(valid_entries),
        best_objective=_best_objective(valid_entries, overall_direction),
        worst_objective=_worst_objective(valid_entries, overall_direction),
        pdev=_percent_deviation(overall_avg_objective, overall_best_known, overall_direction),
        direction=overall_direction,
        excluded_counts=_excluded_counts(entries),
    )

    grouped: dict[tuple[str, str, str], list[ResultEntry]] = defaultdict(list)
    for entry in entries:
        grouped[
            (
                entry.problem_type,
                entry.dataset,
                entry.problem_id,
            )
        ].append(entry)

    by_problem_solver: list[ProblemSolverSummary] = []
    for (problem_type, dataset, problem_id), bucket in sorted(grouped.items()):
        valid_bucket = [e for e in bucket if _is_valid_for_objective_stats(e)]
        direction = bucket[0].direction
        best_known_value = _single_value({e.best_known for e in bucket})
        avg_objective = _avg_objective(valid_bucket)
        best_known_gaps = [
            e.best_known_gap
            for e in valid_bucket
            if e.best_known_gap is not None and is_scalar_objective(e.best_known_gap)
        ]
        by_problem_solver.append(
            ProblemSolverSummary(
                problem_type=problem_type,
                dataset=dataset,
                encoding=bucket[0].encoding,
                direction=direction,
                problem_id=problem_id,
                run_count=len(bucket),
                valid_run_count=len(valid_bucket),
                feasible_rate=(sum(1 for e in bucket if e.feasible) / len(bucket)) if bucket else 0.0,
                avg_runtime=(sum(e.runtime for e in bucket) / len(bucket)) if bucket else 0.0,
                avg_evaluation_count=(
                    sum(e.evaluation_count for e in bucket) / len(bucket) if bucket else 0.0
                ),
                best_known=best_known_value,
                avg_objective=avg_objective,
                std_objective=_objective_std(valid_bucket),
                best_objective=_best_objective(valid_bucket, direction),
                worst_objective=_worst_objective(valid_bucket, direction),
                pdev=_percent_deviation(avg_objective, best_known_value, direction),
                excluded_counts=_excluded_counts(bucket),
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


def _validate_single_variant(entries: list[ResultEntry], meta: SummaryMeta) -> None:
    variants = {(entry.solver_id, entry.param_set_index) for entry in entries}
    expected = (meta.solver_id, meta.param_set_index)
    if not variants or variants == {expected}:
        return
    raise ValueError(
        "SummaryReport must contain exactly one solver variant: "
        f"expected={expected!r}, got={sorted(variants)!r}"
    )


def _build_entry(
    solve_result: SolveResult,
    validation_report: ValidationReport,
    *,
    dataset: str,
    repeat_index: int,
    param_set_index: int,
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
        dataset=dataset,
        encoding=validation_report.encoding,
        direction=validation_report.direction,
        problem_id=solve_result.problem_id,
        solver_id=solve_result.solver_id,
        param_set_index=param_set_index,
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


def _best_objective(entries: list[ResultEntry], direction: DirectionSpec | None) -> int | float | None:
    values = [e.best_objective for e in entries]
    if not values:
        return None
    if not _has_scalar_objectives(entries) or not isinstance(direction, str):
        return None
    if direction == "min":
        return min(values)
    return max(values)


def _worst_objective(entries: list[ResultEntry], direction: DirectionSpec | None) -> int | float | None:
    values = [e.best_objective for e in entries]
    if not values:
        return None
    if not _has_scalar_objectives(entries) or not isinstance(direction, str):
        return None
    if direction == "min":
        return max(values)
    if direction == "max":
        return min(values)
    return None


def _avg_objective(entries: list[ResultEntry]) -> float | None:
    if not entries:
        return None
    if not _has_scalar_objectives(entries):
        return None
    return sum(float(e.best_objective) for e in entries) / len(entries)


def _objective_std(entries: list[ResultEntry]) -> float | None:
    if not entries:
        return None
    if not _has_scalar_objectives(entries):
        return None
    if len(entries) == 1:
        return 0.0

    mean = _avg_objective(entries)
    if mean is None:
        return None

    variance = sum((float(e.best_objective) - mean) ** 2 for e in entries) / (len(entries) - 1)
    return math.sqrt(variance)


def _percent_deviation(
    avg_objective: int | float | None,
    best_known: ObjectiveValue | None,
    direction: DirectionSpec | None,
) -> float | None:
    if (
        avg_objective is None
        or best_known is None
        or not is_scalar_objective(best_known)
        or not isinstance(direction, str)
        or float(best_known) == 0.0
    ):
        return None
    if direction == "max":
        return (float(best_known) - float(avg_objective)) / float(best_known) * 100.0
    if direction == "min":
        return (float(avg_objective) - float(best_known)) / float(best_known) * 100.0
    return None


def _single_value(values: set[T]) -> T | None:
    if len(values) == 1:
        return next(iter(values))
    return None


def _is_valid_for_objective_stats(entry: ResultEntry) -> bool:
    return entry.feasible and entry.objective_valid


def _has_scalar_objectives(entries: list[ResultEntry]) -> bool:
    return bool(entries) and all(is_scalar_objective(entry.best_objective) for entry in entries)


def _excluded_counts(entries: list[ResultEntry]) -> ExcludedCounts:
    return ExcludedCounts(
        infeasible=sum(1 for e in entries if e.excluded_reason == "infeasible"),
        objective_mismatch=sum(1 for e in entries if e.excluded_reason == "objective_mismatch"),
        runtime_error=sum(1 for e in entries if e.excluded_reason == "runtime_error"),
    )
