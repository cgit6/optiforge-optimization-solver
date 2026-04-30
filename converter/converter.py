"""由 MKP 慣用之 .dat 檔建立 ProblemModel / 對應 YAML。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
from ruamel.yaml import YAML

from ..engine.models import ProblemModel

ProblemPayloadConverter = Callable[[Path], dict[str, Any]]


def dat_file_path(*, repo_root: Path, dataset: str, problem_id: str) -> Path:
    return repo_root / "data" / dataset / f"{problem_id}.dat"


def yaml_file_path(*, repo_root: Path, dataset: str, problem_id: str) -> Path:
    return repo_root / "configs/problems" / dataset / f"{problem_id}.yaml"


def parse_weish_dat(dat_path: Path) -> dict[str, Any]:
    """Parse WEISH-style MKP ``.dat`` payload into standard problem fields."""
    if not dat_path.exists():
        raise FileNotFoundError(f"Missing dat file: {dat_path}")

    raw_lines = [line.strip() for line in dat_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    header = raw_lines[0].split()
    items = int(header[0])
    dim = int(header[1])
    best_known = int(header[2])
    values = [int(x) for x in raw_lines[1].split()]
    weights_by_dim = [[int(x) for x in raw_lines[2 + idx].split()] for idx in range(dim)]
    capacities = [int(x) for x in raw_lines[2 + dim].split()]

    if len(values) != items:
        raise ValueError(f"Invalid dat values length for {dat_path}: expected {items}, got {len(values)}")
    if len(capacities) != dim:
        raise ValueError(f"Invalid dat capacities length for {dat_path}: expected {dim}, got {len(capacities)}")
    for idx, row in enumerate(weights_by_dim):
        if len(row) != items:
            raise ValueError(f"Invalid dat weights row length at dim {idx} for {dat_path}")
    weights = [list(row) for row in zip(*weights_by_dim)]

    return {
        "items": items,
        "dim": dim,
        "best_known": best_known,
        "values": values,
        "weights": weights,
        "capacities": capacities,
    }


def parse_dat_payload(dat_path: Path) -> dict[str, Any]:
    return parse_weish_dat(dat_path)


def build_problem_model_from_dat(
    *,
    dataset: str,
    problem_id: str,
    dat_path: Path,
    parser: ProblemPayloadConverter = parse_weish_dat,
) -> ProblemModel:
    payload = parser(dat_path)
    return ProblemModel(
        problem_id=problem_id,
        dataset=dataset,
        items=int(payload["items"]),
        dim=int(payload["dim"]),
        values=np.asarray(payload["values"], dtype=int),
        weights=np.asarray(payload["weights"], dtype=int),
        capacities=np.asarray(payload["capacities"], dtype=int),
        best_known=int(payload["best_known"]),
    )


def load_problem_model_from_repo_dat(
    *,
    repo_root: Path,
    dataset: str,
    problem_id: str,
    parser: ProblemPayloadConverter = parse_weish_dat,
) -> ProblemModel:
    dat_path = dat_file_path(repo_root=repo_root, dataset=dataset, problem_id=problem_id)
    return build_problem_model_from_dat(
        dataset=dataset,
        problem_id=problem_id,
        dat_path=dat_path,
        parser=parser,
    )


def ensure_problem_yaml_from_dat(
    *,
    repo_root: Path,
    dataset: str,
    problem_id: str,
    parser: ProblemPayloadConverter = parse_weish_dat,
) -> Path:
    """由 data/<dataset>/<problem_id>.dat 產生 configs/problems/...yaml。"""
    dat_path = dat_file_path(repo_root=repo_root, dataset=dataset, problem_id=problem_id)
    payload = parser(dat_path)
    problem_yaml = yaml_file_path(repo_root=repo_root, dataset=dataset, problem_id=problem_id)
    problem_yaml.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "problem_id": problem_id,
        "dataset": dataset,
        "items": payload["items"],
        "dim": payload["dim"],
        "values": payload["values"],
        "weights": payload["weights"],
        "capacities": payload["capacities"],
        "best_known": payload["best_known"],
    }
    yaml = YAML()
    yaml.default_flow_style = False
    with problem_yaml.open("w", encoding="utf-8") as fh:
        yaml.dump(body, fh)
    return problem_yaml
