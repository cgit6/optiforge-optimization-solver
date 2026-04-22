from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contracts import RunResult
from .validator import ValidationReport


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
    stop_reason: str
    runtime: float
    evaluation_count: int
    error: str | None
    excluded_reason: str | None


class ResultWriter:
    """Write run results and batch summaries in CSV + JSON formats."""

    def __init__(self, experiment_id: str, output_root: Path | str = Path("mkp/output")) -> None:
        if not experiment_id.strip():
            raise ValueError("experiment_id cannot be empty")
        self._output_dir = Path(output_root) / experiment_id
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._runs_csv = self._output_dir / "runs.csv"
        self._runs_jsonl = self._output_dir / "runs.jsonl"
        self._summary_csv = self._output_dir / "summary.csv"
        self._summary_json = self._output_dir / "summary.json"

    def write_run(self, run_result: RunResult, validation_report: ValidationReport) -> ResultEntry:
        entry = self._build_entry(run_result, validation_report)
        row = self._entry_to_dict(entry)
        self._append_csv_row(self._runs_csv, row)
        self._append_jsonl_row(self._runs_jsonl, row)
        return entry

    def build_summary(self, entries: list[ResultEntry]) -> dict[str, Any]:
        total_runs = len(entries)
        feasible_runs = sum(1 for e in entries if e.feasible)
        valid_objective_runs = [e for e in entries if e.feasible and e.objective_valid]

        excluded_counts = {
            "infeasible": sum(1 for e in entries if not e.feasible),
            "objective_mismatch": sum(1 for e in entries if e.feasible and e.objective_mismatch),
        }

        avg_runtime = (sum(e.runtime for e in entries) / total_runs) if total_runs > 0 else 0.0
        avg_evaluation_count = (
            sum(e.evaluation_count for e in entries) / total_runs if total_runs > 0 else 0.0
        )

        avg_objective = (
            sum(e.best_objective for e in valid_objective_runs) / len(valid_objective_runs)
            if valid_objective_runs
            else None
        )
        best_objective = (
            max(e.best_objective for e in valid_objective_runs) if valid_objective_runs else None
        )

        return {
            "total_runs": total_runs,
            "feasible_rate": (feasible_runs / total_runs) if total_runs > 0 else 0.0,
            "avg_runtime": avg_runtime,
            "avg_evaluation_count": avg_evaluation_count,
            "avg_objective": avg_objective,
            "best_objective": best_objective,
            "excluded_counts": excluded_counts,
        }

    def write_summary(self, summary: dict[str, Any]) -> None:
        flat_summary = {
            "total_runs": summary["total_runs"],
            "feasible_rate": summary["feasible_rate"],
            "avg_runtime": summary["avg_runtime"],
            "avg_evaluation_count": summary["avg_evaluation_count"],
            "avg_objective": summary["avg_objective"],
            "best_objective": summary["best_objective"],
            "excluded_infeasible": summary["excluded_counts"]["infeasible"],
            "excluded_objective_mismatch": summary["excluded_counts"]["objective_mismatch"],
        }

        with self._summary_csv.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(flat_summary.keys()))
            writer.writeheader()
            writer.writerow(flat_summary)

        with self._summary_json.open("w", encoding="utf-8") as fh:
            json.dump(summary, fh, ensure_ascii=False, indent=2)

    def _build_entry(self, run_result: RunResult, validation_report: ValidationReport) -> ResultEntry:
        excluded_reason = None
        if not validation_report.is_feasible:
            excluded_reason = "infeasible"
        elif validation_report.objective_mismatch:
            excluded_reason = "objective_mismatch"

        return ResultEntry(
            problem_id=run_result.problem_id,
            solver_id=run_result.solver_id,
            repeat_index=run_result.repeat_index,
            seed=run_result.seed,
            best_objective=run_result.best_objective,
            feasible=validation_report.is_feasible,
            objective_valid=validation_report.objective_valid,
            objective_mismatch=validation_report.objective_mismatch,
            stop_reason=run_result.stop_reason,
            runtime=run_result.runtime,
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
            "stop_reason": entry.stop_reason,
            "runtime": entry.runtime,
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
