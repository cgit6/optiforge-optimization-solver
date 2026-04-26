from __future__ import annotations

import csv
import json
import threading
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..engine.contracts import RunResult
from ..solver.validator import ValidationReport


@dataclass(frozen=True)
class ResultEntry:
    problem_id: str
    solver_id: str
    repeat_index: int
    seed: int
    best_objective: int
    feasible: bool
    objective_valid: bool
    objective_mismatch: bool
    best_known: int
    best_known_reached: bool
    best_known_gap: int
    stop_reason: str
    runtime: float
    linprog_runtime: float
    evaluation_count: int
    error: str | None
    excluded_reason: str | None


class ResultWriter:
    """Write run results and batch summaries in CSV + JSON formats."""

    def __init__(self, experiment_id: str, output_root: Path | str = Path("output")) -> None:
        if not experiment_id.strip():
            raise ValueError("experiment_id cannot be empty")
        self._output_dir = Path(output_root) / experiment_id
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._runs_csv = self._output_dir / "runs.csv"
        self._runs_jsonl = self._output_dir / "runs.jsonl"
        self._summary_csv = self._output_dir / "summary.csv"
        self._summary_json = self._output_dir / "summary.json"
        self._run_write_lock = threading.Lock()

    def write_run(
        self,
        run_result: RunResult,
        validation_report: ValidationReport,
        *,
        repeat_index: int,
    ) -> ResultEntry:
        entry = self._build_entry(run_result, validation_report, repeat_index=repeat_index)
        row = self._entry_to_dict(entry)
        with self._run_write_lock:
            self._append_csv_row(self._runs_csv, row)
            self._append_jsonl_row(self._runs_jsonl, row)
        return entry

    def build_summary(self, entries: list[ResultEntry]) -> dict[str, Any]:
        valid_entries = [e for e in entries if self._is_valid_for_objective_stats(e)]
        overall = {
            "total_runs": len(entries),
            "valid_run_count": len(valid_entries),
            "feasible_rate": (sum(1 for e in entries if e.feasible) / len(entries)) if entries else 0.0,
            "avg_runtime": (sum(e.runtime for e in entries) / len(entries)) if entries else 0.0,
            "avg_evaluation_count": (sum(e.evaluation_count for e in entries) / len(entries)) if entries else 0.0,
            "avg_objective": (
                sum(e.best_objective for e in valid_entries) / len(valid_entries) if valid_entries else None
            ),
            "best_objective": max((e.best_objective for e in valid_entries), default=None),
            "excluded_counts": self._excluded_counts(entries),
        }

        grouped: dict[tuple[str, str], list[ResultEntry]] = defaultdict(list)
        for entry in entries:
            grouped[(entry.problem_id, entry.solver_id)].append(entry)

        by_problem_solver: list[dict[str, Any]] = []
        for (problem_id, solver_id), bucket in sorted(grouped.items()):
            valid_bucket = [e for e in bucket if self._is_valid_for_objective_stats(e)]
            best_known_value = bucket[0].best_known if bucket else None
            best_known_gaps = [e.best_known_gap for e in valid_bucket]
            by_problem_solver.append(
                {
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
                        sum(e.best_objective for e in valid_bucket) / len(valid_bucket) if valid_bucket else None
                    ),
                    "best_objective": max((e.best_objective for e in valid_bucket), default=None),
                    "excluded_counts": self._excluded_counts(bucket),
                    "best_known": best_known_value,
                    "best_known_reached_count": sum(1 for e in valid_bucket if e.best_known_reached),
                    "best_known_gap_min": min(best_known_gaps) if best_known_gaps else None,
                    "best_known_gap_avg": (
                        sum(best_known_gaps) / len(best_known_gaps) if best_known_gaps else None
                    ),
                }
            )

        return {"overall": overall, "by_problem_solver": by_problem_solver}

    def write_summary(self, summary: dict[str, Any]) -> None:
        with self._summary_json.open("w", encoding="utf-8") as fh:
            json.dump(summary, fh, ensure_ascii=False, indent=2)

        overall = summary["overall"]
        rows: list[dict[str, Any]] = [
            {
                "row_type": "overall",
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

        with self._summary_csv.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    def _build_entry(
        self,
        run_result: RunResult,
        validation_report: ValidationReport,
        *,
        repeat_index: int,
    ) -> ResultEntry:
        excluded_reason = None
        if not validation_report.is_feasible:
            excluded_reason = "infeasible"
        elif validation_report.objective_mismatch:
            excluded_reason = "objective_mismatch"
        elif run_result.error:
            excluded_reason = "runtime_error"

        best_known = int(run_result.best_objective + validation_report.best_known_gap)

        return ResultEntry(
            problem_id=run_result.problem_id,
            solver_id=run_result.solver_id,
            repeat_index=repeat_index,
            seed=run_result.seed,
            best_objective=run_result.best_objective,
            feasible=validation_report.is_feasible,
            objective_valid=validation_report.objective_valid,
            objective_mismatch=validation_report.objective_mismatch,
            best_known=best_known,
            best_known_reached=validation_report.best_known_reached,
            best_known_gap=validation_report.best_known_gap,
            stop_reason=run_result.stop_reason,
            runtime=run_result.runtime,
            linprog_runtime=run_result.linprog_runtime,
            evaluation_count=run_result.evaluation_count,
            error=run_result.error,
            excluded_reason=excluded_reason,
        )

    def _entry_to_dict(self, entry: ResultEntry) -> dict[str, Any]:
        return {
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
        }

    def _append_csv_row(self, path: Path, row: dict[str, Any]) -> None:
        write_header = not path.exists()
        with path.open("a", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(row.keys()))
            if write_header:
                writer.writeheader()
            writer.writerow(row)

    def _append_jsonl_row(self, path: Path, row: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _is_valid_for_objective_stats(self, entry: ResultEntry) -> bool:
        return entry.feasible and entry.objective_valid

    def _excluded_counts(self, entries: list[ResultEntry]) -> dict[str, int]:
        return {
            "infeasible": sum(1 for e in entries if e.excluded_reason == "infeasible"),
            "objective_mismatch": sum(1 for e in entries if e.excluded_reason == "objective_mismatch"),
            "runtime_error": sum(1 for e in entries if e.excluded_reason == "runtime_error"),
        }
