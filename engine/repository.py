from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from .models import BaseProblem
from .problem_registry import ProblemRegistry, default_problem_registry


class ProblemRepository:
    """Load problem YAML files through the problem-type registry."""

    def __init__(
        self,
        config_root: Path | str = Path("configs/problems"),
        *,
        problem_registry: ProblemRegistry | None = None,
    ) -> None:
        self._config_root = Path(config_root)
        self._registry = problem_registry or default_problem_registry()
        self._yaml = YAML(typ="safe")
        self._cache: dict[tuple[str, str, str], BaseProblem] = {}
        self._cache_lock = threading.Lock()
        self._yaml_parse_lock = threading.Lock()

    def resolve_path(self, problem_type: str, dataset: str, problem_id: str) -> Path:
        canonical = self._config_root / problem_type / dataset / f"{problem_id}.yaml"
        if canonical.exists():
            return canonical
        legacy = self._config_root / dataset / f"{problem_id}.yaml"
        if problem_type == "mkp" and legacy.exists():
            return legacy
        return canonical

    def load(self, dataset: str, problem_id: str, problem_type: str = "mkp") -> BaseProblem:
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
