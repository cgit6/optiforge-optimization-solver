from __future__ import annotations

from pathlib import Path
from typing import Any


def require_fields(data: dict[str, Any], fields: tuple[str, ...], file_path: Path) -> None:
    missing = [field for field in fields if field not in data]
    if missing:
        raise ValueError(f"Missing required field(s) {missing} in {file_path}")


def validate_identity(
    data: dict[str, Any],
    *,
    problem_type: str,
    dataset: str,
    problem_id: str,
    file_path: Path,
) -> None:
    yaml_problem_id = str(data["problem_id"])
    yaml_dataset = str(data["dataset"])
    yaml_problem_type = str(data.get("problem_type", problem_type))
    if yaml_problem_id != problem_id:
        raise ValueError(f"problem_id mismatch in {file_path}: expected {problem_id}, got {yaml_problem_id}")
    if yaml_dataset != dataset:
        raise ValueError(f"dataset mismatch in {file_path}: expected {dataset}, got {yaml_dataset}")
    if yaml_problem_type != problem_type:
        raise ValueError(f"problem_type mismatch in {file_path}: expected {problem_type}, got {yaml_problem_type}")
