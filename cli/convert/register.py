from __future__ import annotations

from pathlib import Path
from typing import Any

from ...converter import register

def _read_numbers(source_path: Path) -> list[int]:
    if not source_path.exists():
        raise FileNotFoundError(f"Missing dat file: {source_path}")

    try:
        return [int(float(raw)) for raw in source_path.read_text(encoding="utf-8").split()]
    except ValueError as exc:
        raise ValueError(f"Invalid numeric value in {source_path}") from exc


def _optional_best_known(raw_value: int) -> int | None:
    return int(raw_value) if int(raw_value) > 0 else None


def _parse_flat_problem(
    source_path: Path,
    *,
    dataset_name: str,
) -> dict[str, Any]:
    numbers = _read_numbers(source_path)
    if len(numbers) < 3:
        raise ValueError(f"Invalid {dataset_name} dat header for {source_path}")

    items = int(numbers[0])
    dim = int(numbers[1])
    best_known = _optional_best_known(numbers[2])
    expected_len = 3 + items + items * dim + dim
    if len(numbers) != expected_len:
        raise ValueError(
            f"Invalid {dataset_name} dat length for {source_path}: expected {expected_len}, got {len(numbers)}"
        )

    values_start = 3
    values_end = values_start + items
    weights_start = values_end
    weights_end = weights_start + items * dim
    capacities_end = weights_end + dim

    values = numbers[values_start:values_end]
    weights_flat = numbers[weights_start:weights_end]
    weights_by_dim = [
        weights_flat[idx * items : (idx + 1) * items]
        for idx in range(dim)
    ]
    capacities = numbers[weights_end:capacities_end]

    if len(values) != items:
        raise ValueError(f"Invalid {dataset_name} values length for {source_path}: expected {items}, got {len(values)}")
    for idx, row in enumerate(weights_by_dim):
        if len(row) != items:
            raise ValueError(f"Invalid {dataset_name} weights row length at dim {idx} for {source_path}")
    if len(capacities) != dim:
        raise ValueError(
            f"Invalid {dataset_name} capacities length for {source_path}: expected {dim}, got {len(capacities)}"
        )

    weights = [list(row) for row in zip(*weights_by_dim)]

    return {
        "items": items,
        "dim": dim,
        "best_known": best_known,
        "values": values,
        "weights": weights,
        "capacities": capacities,
    }


# weish 題庫的解析函數
def parseWeish(dat_path: Path) -> dict[str, Any]:
    """對 weish 題庫進行格式轉換的函數"""
    return _parse_flat_problem(dat_path, dataset_name="WEISH")

# weing 題庫的解析函數
def parseWeing(dat_path: Path) -> dict[str, Any]:
    """依 WEING 題庫格式解析 .dat 檔。"""
    return _parse_flat_problem(dat_path, dataset_name="WEING")


def parsePb(dat_path: Path) -> dict[str, Any]:
    """依 PB 題庫格式解析 .dat 檔。"""
    return _parse_flat_problem(dat_path, dataset_name="PB")


def parsePet(dat_path: Path) -> dict[str, Any]:
    """依 PET 題庫格式解析 .dat 檔。"""
    return _parse_flat_problem(dat_path, dataset_name="PET")


def parseSent(dat_path: Path) -> dict[str, Any]:
    """依 SENT 題庫格式解析 .dat 檔。"""
    return _parse_flat_problem(dat_path, dataset_name="SENT")


def parseHp(dat_path: Path) -> dict[str, Any]:
    """依 HP 題庫格式解析 .dat 檔。"""
    return _parse_flat_problem(dat_path, dataset_name="HP")


def parseCb(dat_path: Path) -> dict[str, Any]:
    """依 CB/OR 題庫格式解析 .dat 檔。"""
    return _parse_flat_problem(dat_path, dataset_name="CB")


def parseGk(txt_path: Path) -> dict[str, Any]:
    """依 GK 題庫格式解析 .txt 檔。"""
    numbers = _read_numbers(txt_path)
    if len(numbers) < 2:
        raise ValueError(f"Invalid GK txt header for {txt_path}")

    items = int(numbers[0])
    dim = int(numbers[1])
    expected_len = 2 + items * (dim + 1) + dim
    if len(numbers) != expected_len:
        raise ValueError(f"Invalid GK txt length for {txt_path}: expected {expected_len}, got {len(numbers)}")

    rows_start = 2
    rows_end = rows_start + items * (dim + 1)
    rows_flat = numbers[rows_start:rows_end]
    rows = [
        rows_flat[idx * (dim + 1) : (idx + 1) * (dim + 1)]
        for idx in range(items)
    ]
    values = [row[0] for row in rows]
    weights = [row[1:] for row in rows]
    capacities = numbers[rows_end:rows_end + dim]

    if len(values) != items:
        raise ValueError(f"Invalid GK values length for {txt_path}: expected {items}, got {len(values)}")
    for idx, row in enumerate(weights):
        if len(row) != dim:
            raise ValueError(f"Invalid GK weights row length at item {idx} for {txt_path}")
    if len(capacities) != dim:
        raise ValueError(f"Invalid GK capacities length for {txt_path}: expected {dim}, got {len(capacities)}")

    return {
        "items": items,
        "dim": dim,
        "best_known": None,
        "values": values,
        "weights": weights,
        "capacities": capacities,
    }



# 註冊解析函數，因為每個題庫的格式都不一樣。
register("weish")(parseWeish)
register("weing")(parseWeing)
register("pb")(parsePb)
register("pet")(parsePet)
register("sent")(parseSent)
register("hp")(parseHp)
register("cb")(parseCb)
register("gk")(parseGk)
