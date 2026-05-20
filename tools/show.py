"""結果輸出模組：將已整理的 run entries 與摘要統計寫入檔案。"""

from __future__ import annotations

import csv
import json
import shutil
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping

from .stat import ResultEntry, ResultMetadata, SummaryMeta, SummaryReport, result_entries, summarize

if TYPE_CHECKING:
    from ..simulator.core import SimulatorResult

def write_simulator_result(
    simulator_result: "SimulatorResult",
    *,
    experiment_name: str,
    output_root: Path | str,
    variant_metadata: Mapping[tuple[str, int], Mapping[str, Any]] | None = None,
) -> tuple[Path, ...]:
    if not experiment_name.strip():
        raise ValueError("experiment_name cannot be empty")
    # 1. 資料轉換
    entries = result_entries(simulator_result)
    # 2. 分組
    grouped: dict[tuple[str, int], list[ResultEntry]] = defaultdict(list)
    for entry in entries:
        grouped[(entry.solver_id, entry.param_set_index)].append(entry)

    written_dirs: list[Path] = []

    # 3. 寫檔案
    for (solver_id, param_set_index), bucket in sorted(grouped.items()):
        output_dir = Path(output_root) / experiment_name / solver_id / f"param_{param_set_index}"
        _reset_variant_output_dir(output_dir)

        _write_runs_csv(output_dir / "runs.csv", bucket)
        _write_runs_json(output_dir / "runs.json", bucket)
        _write_summary(
            output_dir,
            summarize(
                bucket,
                meta=_summary_meta(
                    simulator_result,
                    solver_id,
                    param_set_index,
                    variant_metadata=variant_metadata,
                ),
            ),
        ) # 寫統計結果
        written_dirs.append(output_dir)
    return tuple(written_dirs)


def _summary_meta(
    simulator_result: "SimulatorResult",
    solver_id: str,
    param_set_index: int,
    *,
    variant_metadata: Mapping[tuple[str, int], Mapping[str, Any]] | None = None,
) -> SummaryMeta:
    key = (solver_id, param_set_index)
    if key not in simulator_result.variant_params:
        raise KeyError(
            f"variant params not found for summary: solver_id={solver_id!r}, "
            f"param_set_index={param_set_index!r}"
        )
    return SummaryMeta(
        solver_id=solver_id,
        param_set_index=param_set_index,
        params=simulator_result.variant_params[key],
        experiment=dict((variant_metadata or {}).get(key, {})),
    )


def _reset_variant_output_dir(output_dir: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def _entry_to_json_dict(entry: ResultEntry) -> dict[str, Any]:
    return _json_safe(asdict(entry))


def _entry_to_csv_dict(entry: ResultEntry) -> dict[str, Any]:
    row = asdict(entry)
    metadata = row.pop("metadata")
    row["metadata_json"] = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
    return {key: _csv_cell(value) for key, value in row.items()}


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
        json.dump(_json_safe(asdict(summary)), fh, ensure_ascii=False, indent=2)

    rows = _summary_to_csv_rows(summary)

    with summary_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _summary_to_csv_rows(summary: SummaryReport) -> list[dict[str, Any]]:
    meta_json = json.dumps(asdict(summary.overall.meta), ensure_ascii=False, sort_keys=True)
    rows: list[dict[str, Any]] = [
        {
            "row_type": "overall",
            "meta_json": meta_json,
            "problem_type": "",
            "dataset": "",
            "encoding": "",
            "direction": summary.overall.direction or "",
            "problem_id": "",
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
                "meta_json": meta_json,
                "problem_type": group.problem_type,
                "dataset": group.dataset,
                "encoding": group.encoding,
                "direction": group.direction,
                "problem_id": group.problem_id,
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
    return [{key: _csv_cell(value) for key, value in row.items()} for row in rows]


def _empty_entry() -> ResultEntry:
    return ResultEntry(
        problem_type="",
        dataset="",
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


def _json_safe(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    return value


def _csv_cell(value: Any) -> Any:
    if isinstance(value, (tuple, list, dict)):
        return json.dumps(_json_safe(value), ensure_ascii=False, sort_keys=True)
    return value
