"""統計與輸出模組：將 SimulatorResult 整理後一次性寫入 runs / summary 檔。"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
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
    metadata_json: str


def write_simulator_result(
    simulator_result: "SimulatorResult",
    *,
    experiment_id: str,
    output_root: Path | str,
) -> Path:
    if not experiment_id.strip():
        raise ValueError("experiment_id cannot be empty")

    output_dir = Path(output_root) / experiment_id
    output_dir.mkdir(parents=True, exist_ok=True)

    entries = [
        _build_entry(row.solve_result, row.validation_report, repeat_index=row.task.repeat_index)
        for row in simulator_result.rows
    ]

    _write_runs_csv(output_dir / "runs.csv", entries)
    _write_runs_jsonl(output_dir / "runs.jsonl", entries)
    summary = build_summary(entries)
    _write_summary(output_dir, summary)
    return output_dir


def build_summary(entries: list[ResultEntry]) -> dict[str, Any]:
    valid_entries = [e for e in entries if _is_valid_for_objective_stats(e)]
    overall_direction = _single_value({e.direction for e in entries})
    overall = {
        "total_runs": len(entries),
        "valid_run_count": len(valid_entries),
        "feasible_rate": (sum(1 for e in entries if e.feasible) / len(entries)) if entries else 0.0,
        "avg_runtime": (sum(e.runtime for e in entries) / len(entries)) if entries else 0.0,
        "avg_evaluation_count": (sum(e.evaluation_count for e in entries) / len(entries)) if entries else 0.0,
        "avg_objective": (
            sum(float(e.best_objective) for e in valid_entries) / len(valid_entries) if valid_entries else None
        ),
        "best_objective": _best_objective(valid_entries, overall_direction),
        "direction": overall_direction,
        "excluded_counts": _excluded_counts(entries),
    }

    grouped: dict[tuple[str, str, str], list[ResultEntry]] = defaultdict(list)
    for entry in entries:
        grouped[(entry.problem_type, entry.problem_id, entry.solver_id)].append(entry)

    by_problem_solver: list[dict[str, Any]] = []
    for (problem_type, problem_id, solver_id), bucket in sorted(grouped.items()):
        valid_bucket = [e for e in bucket if _is_valid_for_objective_stats(e)]
        direction = bucket[0].direction if bucket else None
        best_known_value = bucket[0].best_known if bucket else None
        best_known_gaps = [e.best_known_gap for e in valid_bucket if e.best_known_gap is not None]
        by_problem_solver.append(
            {
                "problem_type": problem_type,
                "encoding": bucket[0].encoding if bucket else "",
                "direction": direction,
                "problem_id": problem_id,
                "solver_id": solver_id,
                "run_count": len(bucket),
                "valid_run_count": len(valid_bucket),
                "feasible_rate": (sum(1 for e in bucket if e.feasible) / len(bucket)) if bucket else 0.0,
                "avg_runtime": (sum(e.runtime for e in bucket) / len(bucket)) if bucket else 0.0,
                "avg_evaluation_count": (
                    sum(e.evaluation_count for e in bucket) / len(bucket) if bucket else 0.0
                ),
                "avg_objective": (
                    sum(float(e.best_objective) for e in valid_bucket) / len(valid_bucket)
                    if valid_bucket
                    else None
                ),
                "best_objective": _best_objective(valid_bucket, direction),
                "excluded_counts": _excluded_counts(bucket),
                "best_known": best_known_value,
                "best_known_reached_count": sum(1 for e in valid_bucket if e.best_known_reached is True),
                "best_known_gap_min": min(best_known_gaps) if best_known_gaps else None,
                "best_known_gap_avg": (
                    sum(float(gap) for gap in best_known_gaps) / len(best_known_gaps)
                    if best_known_gaps
                    else None
                ),
            }
        )

    return {"overall": overall, "by_problem_solver": by_problem_solver}


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
    metadata = {
        "solve": dict(solve_result.metadata),
        "validation": dict(validation_report.metadata),
    }

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
        metadata_json=json.dumps(metadata, ensure_ascii=False, sort_keys=True),
    )


def _entry_to_dict(entry: ResultEntry) -> dict[str, Any]:
    return {
        "problem_type": entry.problem_type,
        "encoding": entry.encoding,
        "direction": entry.direction,
        "problem_id": entry.problem_id,
        "solver_id": entry.solver_id,
        "repeat_index": entry.repeat_index,
        "seed": entry.seed,
        "best_objective": entry.best_objective,
        "feasible": entry.feasible,
        "objective_valid": entry.objective_valid,
        "objective_mismatch": entry.objective_mismatch,
        "best_known": entry.best_known,
        "best_known_reached": entry.best_known_reached,
        "best_known_gap": entry.best_known_gap,
        "stop_reason": entry.stop_reason,
        "runtime": entry.runtime,
        "linprog_runtime": entry.linprog_runtime,
        "evaluation_count": entry.evaluation_count,
        "error": entry.error,
        "excluded_reason": entry.excluded_reason,
        "metadata_json": entry.metadata_json,
    }


def _write_runs_csv(path: Path, entries: list[ResultEntry]) -> None:
    rows = [_entry_to_dict(entry) for entry in entries]
    fieldnames = list(_entry_to_dict(entries[0]).keys()) if entries else list(_entry_to_dict(_empty_entry()).keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_runs_jsonl(path: Path, entries: list[ResultEntry]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(_entry_to_dict(entry), ensure_ascii=False) + "\n")


def _write_summary(output_dir: Path, summary: dict[str, Any]) -> None:
    summary_json = output_dir / "summary.json"
    summary_csv = output_dir / "summary.csv"

    with summary_json.open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)

    overall = summary["overall"]
    rows: list[dict[str, Any]] = [
        {
            "row_type": "overall",
            "problem_type": "",
            "encoding": "",
            "direction": overall["direction"] or "",
            "problem_id": "",
            "solver_id": "",
            "run_count": overall["total_runs"],
            "valid_run_count": overall["valid_run_count"],
            "feasible_rate": overall["feasible_rate"],
            "avg_runtime": overall["avg_runtime"],
            "avg_evaluation_count": overall["avg_evaluation_count"],
            "avg_objective": overall["avg_objective"],
            "best_objective": overall["best_objective"],
            "best_known": "",
            "best_known_reached_count": "",
            "best_known_gap_min": "",
            "best_known_gap_avg": "",
            "excluded_infeasible": overall["excluded_counts"]["infeasible"],
            "excluded_objective_mismatch": overall["excluded_counts"]["objective_mismatch"],
            "excluded_runtime_error": overall["excluded_counts"]["runtime_error"],
        }
    ]

    for group in summary["by_problem_solver"]:
        rows.append(
            {
                "row_type": "group",
                "problem_type": group["problem_type"],
                "encoding": group["encoding"],
                "direction": group["direction"],
                "problem_id": group["problem_id"],
                "solver_id": group["solver_id"],
                "run_count": group["run_count"],
                "valid_run_count": group["valid_run_count"],
                "feasible_rate": group["feasible_rate"],
                "avg_runtime": group["avg_runtime"],
                "avg_evaluation_count": group["avg_evaluation_count"],
                "avg_objective": group["avg_objective"],
                "best_objective": group["best_objective"],
                "best_known": group["best_known"],
                "best_known_reached_count": group["best_known_reached_count"],
                "best_known_gap_min": group["best_known_gap_min"],
                "best_known_gap_avg": group["best_known_gap_avg"],
                "excluded_infeasible": group["excluded_counts"]["infeasible"],
                "excluded_objective_mismatch": group["excluded_counts"]["objective_mismatch"],
                "excluded_runtime_error": group["excluded_counts"]["runtime_error"],
            }
        )

    with summary_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


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


def _excluded_counts(entries: list[ResultEntry]) -> dict[str, int]:
    return {
        "infeasible": sum(1 for e in entries if e.excluded_reason == "infeasible"),
        "objective_mismatch": sum(1 for e in entries if e.excluded_reason == "objective_mismatch"),
        "runtime_error": sum(1 for e in entries if e.excluded_reason == "runtime_error"),
    }


def _empty_entry() -> ResultEntry:
    return ResultEntry(
        problem_type="",
        encoding="",
        direction="",
        problem_id="",
        solver_id="",
        repeat_index=0,
        seed=0,
        best_objective=0,
        feasible=False,
        objective_valid=False,
        objective_mismatch=False,
        best_known=None,
        best_known_reached=False,
        best_known_gap=None,
        stop_reason="",
        runtime=0.0,
        linprog_runtime=0.0,
        evaluation_count=0,
        error=None,
        excluded_reason=None,
        metadata_json="{}",
    )
