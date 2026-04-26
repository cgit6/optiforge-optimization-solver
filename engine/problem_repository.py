from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import numpy as np
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from .contracts import ProblemModel


class  ProblemRepository:
    """Load MKP problem YAML files and cache ProblemModel instances."""

    def __init__(self, config_root: Path | str = Path("configs/problems")) -> None:
        self._config_root = Path(config_root)
        self._yaml = YAML(typ="safe")
        self._cache: dict[tuple[str, str], ProblemModel] = {}
        self._cache_lock = threading.Lock()
        # ruamel YAML 解析器非執行緒安全；worker_curriculum 等多線同時 load 須序列化 parse
        self._yaml_parse_lock = threading.Lock()

    def load(self, dataset: str, problem_id: str) -> ProblemModel:
        key = (dataset, problem_id)
        with self._cache_lock:
            if key in self._cache:
                return self._cache[key]

        file_path = self._config_root / dataset / f"{problem_id}.yaml"
        if not file_path.exists():
            raise FileNotFoundError(f"Problem YAML not found: {file_path}")

        data = self._read_yaml(file_path)
        model = self._build_problem_model(data, dataset=dataset, problem_id=problem_id, file_path=file_path)
        with self._cache_lock:
            if key in self._cache:
                return self._cache[key]
            self._cache[key] = model
            return model

    def _read_yaml(self, path: Path) -> dict[str, Any]:
        try:
            with path.open("r", encoding="utf-8") as fh:
                with self._yaml_parse_lock:
                    loaded = self._yaml.load(fh)
        except YAMLError as exc:
            raise ValueError(f"Invalid YAML format in {path}: {exc}") from exc

        if not isinstance(loaded, dict):
            raise ValueError(f"Problem YAML must be a mapping: {path}")
        return loaded

    def _build_problem_model(
        self,
        data: dict[str, Any],
        *,
        dataset: str,
        problem_id: str,
        file_path: Path,
    ) -> ProblemModel:
        required_fields = ("problem_id", "dataset", "items", "dim", "best_known", "values", "weights", "capacities")
        missing = [field for field in required_fields if field not in data]
        if missing:
            raise ValueError(f"Missing required field(s) {missing} in {file_path}")

        if data["best_known"] is None:
            raise ValueError(f"best_known cannot be null in {file_path}")

        yaml_problem_id = str(data["problem_id"])
        yaml_dataset = str(data["dataset"])
        if yaml_problem_id != problem_id:
            raise ValueError(f"problem_id mismatch in {file_path}: expected {problem_id}, got {yaml_problem_id}")
        if yaml_dataset != dataset:
            raise ValueError(f"dataset mismatch in {file_path}: expected {dataset}, got {yaml_dataset}")

        try:
            items = int(data["items"])
            dim = int(data["dim"])
            best_known = int(data["best_known"])
            values = np.asarray(data["values"], dtype=int)
            weights = np.asarray(data["weights"], dtype=int)
            capacities = np.asarray(data["capacities"], dtype=int)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid data type in {file_path}: {exc}") from exc

        if values.shape != (items,):
            raise ValueError(f"len(values) must equal items in {file_path}")
        if weights.shape != (items, dim):
            raise ValueError(f"weights shape must be (items, dim) in {file_path}")
        if capacities.shape != (dim,):
            raise ValueError(f"len(capacities) must equal dim in {file_path}")

        return ProblemModel(
            problem_id=yaml_problem_id,
            dataset=yaml_dataset,
            items=items,
            dim=dim,
            values=values,
            weights=weights,
            capacities=capacities,
            best_known=best_known,
        )
