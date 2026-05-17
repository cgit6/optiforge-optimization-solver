from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from ..problem import Problem
from ..problem.registry import ProblemRegistry


class ProblemRepository:
    """Load problem YAML files through the problem-type registry."""

    def __init__(
        self,
        problem_root: Path | None = None,
        *,
        config_root: Path | None = None,
        registry: ProblemRegistry,
    ) -> None:
        root = problem_root if problem_root is not None else config_root
        if root is None:
            raise TypeError("ProblemRepository requires problem_root or config_root.")
        self._problem_root = Path(root)
        self._registry = registry # 優化題目型別對照表
        self._yaml = YAML(typ="safe")
        self._cache: dict[tuple[str, str, str], Problem] = {}

        # 併發鎖
        self._cache_lock = threading.Lock()
        self._yaml_parse_lock = threading.Lock()

    def resolve_path(self, problem_type: str, dataset: str, problem_id: str) -> Path:
        return self._problem_root / problem_type / dataset / f"{problem_id}.yaml"

    def load(self, dataset: str, problem_id: str, problem_type: str = "mkp") -> Problem:
        key = (problem_type, dataset, problem_id)
        with self._cache_lock:
            if key in self._cache:
                return self._cache[key]

        file_path = self.resolve_path(problem_type, dataset, problem_id)
        if not file_path.exists():
            raise FileNotFoundError(f"Problem YAML not found: {file_path}")

        data = self._read_yaml(file_path)
        yaml_problem_type = str(data.get("problem_type", problem_type))
        if yaml_problem_type != problem_type:
            raise ValueError(
                f"problem_type mismatch in {file_path}: expected {problem_type}, got {yaml_problem_type}"
            )
        spec = self._registry.get(problem_type)
        model = spec.loader(data, dataset, problem_id, file_path)
        self._registry.validate_model(model, problem_type)
        with self._cache_lock:
            if key in self._cache:
                return self._cache[key]
            self._cache[key] = model
            return model

    def read_metadata(self, dataset: str, problem_id: str, problem_type: str = "mkp") -> dict[str, Any]:
        file_path = self.resolve_path(problem_type, dataset, problem_id)
        if not file_path.exists():
            raise FileNotFoundError(f"Problem YAML not found: {file_path}")
        data = self._read_yaml(file_path)
        spec = self._registry.get(problem_type)
        yaml_problem_type = str(data.get("problem_type", problem_type))
        if yaml_problem_type != problem_type:
            raise ValueError(
                f"problem_type mismatch in {file_path}: expected {problem_type}, got {yaml_problem_type}"
            )
        if str(data.get("problem_id", problem_id)) != problem_id:
            raise ValueError(
                f"problem_id mismatch in {file_path}: expected {problem_id}, got {data.get('problem_id')}"
            )
        if str(data.get("dataset", dataset)) != dataset:
            raise ValueError(f"dataset mismatch in {file_path}: expected {dataset}, got {data.get('dataset')}")
        return {
            "problem_type": problem_type,
            "dataset": str(data.get("dataset", dataset)),
            "problem_id": str(data.get("problem_id", problem_id)),
            "encoding": str(data.get("encoding", spec.encoding)),
            "direction": str(data.get("direction", spec.direction)),
            "path": file_path,
        }

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
