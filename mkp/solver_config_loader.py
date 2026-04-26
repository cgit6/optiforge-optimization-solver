from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError


class SolverConfigLoader:
    """Load and validate solver config YAML files."""

    _ALLOWED_STOP_TYPES = {"max_iterations", "max_seconds"}

    def __init__(self, config_root: Path | str = Path("mkp/configs/solvers")) -> None:
        self._config_root = Path(config_root)
        self._yaml = YAML(typ="safe")
        self._yaml_parse_lock = threading.Lock()

    def load(self, solver_id: str) -> dict[str, Any]:
        config_path = self._config_root / f"{solver_id}.yaml"
        if not config_path.exists():
            raise FileNotFoundError(f"Solver config YAML not found: {config_path}")

        data = self._read_yaml(config_path)
        self._validate_schema(data, solver_id=solver_id, file_path=config_path)
        return data

    def _read_yaml(self, path: Path) -> dict[str, Any]:
        try:
            with path.open("r", encoding="utf-8") as fh:
                with self._yaml_parse_lock:
                    loaded = self._yaml.load(fh)
        except YAMLError as exc:
            raise ValueError(f"Invalid YAML format in {path}: {exc}") from exc

        if not isinstance(loaded, dict):
            raise ValueError(f"Solver config must be a mapping: {path}")
        return loaded

    def _validate_schema(self, data: dict[str, Any], *, solver_id: str, file_path: Path) -> None:
        required_fields = ("solver_id", "solver_class", "stop_condition", "params")
        missing = [field for field in required_fields if field not in data]
        if missing:
            raise ValueError(f"Missing required field(s) {missing} in {file_path}")

        yaml_solver_id = str(data["solver_id"])
        if yaml_solver_id != solver_id:
            raise ValueError(
                f"solver_id mismatch in {file_path}: expected {solver_id}, got {yaml_solver_id}"
            )

        if not str(data["solver_class"]).strip():
            raise ValueError(f"solver_class cannot be empty in {file_path}")

        stop_condition = data["stop_condition"]
        if not isinstance(stop_condition, dict):
            raise ValueError(f"stop_condition must be a mapping in {file_path}")

        stop_type = stop_condition.get("type")
        if stop_type not in self._ALLOWED_STOP_TYPES:
            raise ValueError(
                f"stop_condition.type must be one of {sorted(self._ALLOWED_STOP_TYPES)} in {file_path}"
            )

        if stop_type == "max_iterations":
            value = stop_condition.get("max_iterations")
            if value is None or int(value) <= 0:
                raise ValueError(f"max_iterations must be > 0 in {file_path}")
        elif stop_type == "max_seconds":
            value = stop_condition.get("max_seconds")
            if value is None or float(value) <= 0:
                raise ValueError(f"max_seconds must be > 0 in {file_path}")

        if not isinstance(data["params"], dict):
            raise ValueError(f"params must be a mapping in {file_path}")
