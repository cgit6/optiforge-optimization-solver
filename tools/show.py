"""結果輸出模組：將已整理的 run entries 與摘要統計寫入檔案。"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .stat import ResultEntry, ResultMetadata, SummaryReport

if TYPE_CHECKING:
    from ..simulator.core import SimulatorResult


def write_simulator_result(
    simulator_result: "SimulatorResult",
    entries: list[ResultEntry],
    summary: SummaryReport,
    *,
    experiment_id: str,
    output_root: Path | str,
) -> Path:
    if not experiment_id.strip():
        raise ValueError("experiment_id cannot be empty")
    if len(entries) != len(simulator_result.rows):
        raise ValueError("entries length must match simulator_result rows")

    output_dir = Path(output_root) / experiment_id
    output_dir.mkdir(parents=True, exist_ok=True)

    _write_runs_csv(output_dir / "runs.csv", entries)
    _write_runs_json(output_dir / "runs.json", entries)

    legacy_runs_jsonl = output_dir / "runs.jsonl"
    if legacy_runs_jsonl.exists():
        legacy_runs_jsonl.unlink()

    _write_summary(output_dir, summary)
    return output_dir


def _entry_to_json_dict(entry: ResultEntry) -> dict[str, Any]:
    return asdict(entry)


def _entry_to_csv_dict(entry: ResultEntry) -> dict[str, Any]:
    row = asdict(entry)
    metadata = row.pop("metadata")
    row["metadata_json"] = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
    return row


def _write_runs_csv(path: Path, entries: list[ResultEntry]) -> None:
    rows = [_entry_to_csv_dict(entry) for entry in entries]
    fieldnames = (
        list(_entry_to_csv_dict(entries[0]).keys()) if entries else list(_entry_to_csv_dict(_empty_entry()).keys())
    )
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_runs_json(path: Path, entries: list[ResultEntry]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        json.dump([_entry_to_json_dict(entry) for entry in entries], fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def _write_summary(output_dir: Path, summary: SummaryReport) -> None:
    summary_json = output_dir / "summary.json"
    summary_csv = output_dir / "summary.csv"

    with summary_json.open("w", encoding="utf-8") as fh:
        json.dump(asdict(summary), fh, ensure_ascii=False, indent=2)

    rows = _summary_to_csv_rows(summary)

    with summary_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _summary_to_csv_rows(summary: SummaryReport) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {
            "row_type": "overall",
            "problem_type": "",
            "encoding": "",
            "direction": summary.overall.direction or "",
            "problem_id": "",
            "solver_id": "",
            "param_set_index": summary.overall.param_set_index,
            "run_count": summary.overall.total_runs,
            "valid_run_count": summary.overall.valid_run_count,
            "feasible_rate": summary.overall.feasible_rate,
            "avg_runtime": summary.overall.avg_runtime,
            "avg_evaluation_count": summary.overall.avg_evaluation_count,
            "best_known": summary.overall.best_known,
            "avg_objective": summary.overall.avg_objective,
            "std_objective": summary.overall.std_objective,
            "best_objective": summary.overall.best_objective,
            "worst_objective": summary.overall.worst_objective,
            "pdev": summary.overall.pdev,
            "best_known_reached_count": "",
            "best_known_gap_min": "",
            "best_known_gap_avg": "",
            "excluded_infeasible": summary.overall.excluded_counts.infeasible,
            "excluded_objective_mismatch": summary.overall.excluded_counts.objective_mismatch,
            "excluded_runtime_error": summary.overall.excluded_counts.runtime_error,
        }
    ]

    for group in summary.by_problem_solver:
        rows.append(
            {
                "row_type": "group",
                "problem_type": group.problem_type,
                "encoding": group.encoding,
                "direction": group.direction,
                "problem_id": group.problem_id,
                "solver_id": group.solver_id,
                "param_set_index": group.param_set_index,
                "run_count": group.run_count,
                "valid_run_count": group.valid_run_count,
                "feasible_rate": group.feasible_rate,
                "avg_runtime": group.avg_runtime,
                "avg_evaluation_count": group.avg_evaluation_count,
                "best_known": group.best_known,
                "avg_objective": group.avg_objective,
                "std_objective": group.std_objective,
                "best_objective": group.best_objective,
                "worst_objective": group.worst_objective,
                "pdev": group.pdev,
                "best_known_reached_count": group.best_known_reached_count,
                "best_known_gap_min": group.best_known_gap_min,
                "best_known_gap_avg": group.best_known_gap_avg,
                "excluded_infeasible": group.excluded_counts.infeasible,
                "excluded_objective_mismatch": group.excluded_counts.objective_mismatch,
                "excluded_runtime_error": group.excluded_counts.runtime_error,
            }
        )
    return rows


def _empty_entry() -> ResultEntry:
    return ResultEntry(
        problem_type="",
        encoding="",
        direction="",
        problem_id="",
        solver_id="",
        param_set_index=0,
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
        metadata=ResultMetadata(solve={}, validation={}),
    )
