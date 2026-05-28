"""於 engine 階段預載 solver YAML，執行期僅從記憶體讀取（與題庫預載對齊）。"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ..tools.solver_config_loader import SolverConfigLoader
from .models import ExperimentSpec


@dataclass(frozen=True)
class SolverConfigsSnapshot:
    """`spec.solver_ids` 對應的所有參數組設定；對外 `get` 再給副本以免求解改寫快照。"""

    _by_key: tuple[tuple[tuple[str, int], dict[str, Any]], ...]

    @classmethod
    def build(
        cls,
        spec: ExperimentSpec,
        solver_root: Path | str,
        *,
        param_set_indices: Mapping[str, tuple[int, ...]] | None = None,
    ) -> SolverConfigsSnapshot:
        loader = SolverConfigLoader(config_root=solver_root)
        pairs: list[tuple[tuple[str, int], dict[str, Any]]] = []
        for solver_id in spec.solver_ids:
            selected_indices = param_set_indices.get(solver_id) if param_set_indices is not None else None
            if selected_indices is None:
                configs = loader.load_all(solver_id)
            else:
                configs = tuple(
                    loader.load(solver_id, param_set_index=int(param_set_index))
                    for param_set_index in selected_indices
                )
            for raw in configs:
                param_set_index = int(raw["param_set_index"])
                pairs.append(((solver_id, param_set_index), copy.deepcopy(raw)))
        return cls(_by_key=tuple(pairs))

    @classmethod
    def from_configs(cls, configs: tuple[dict[str, Any], ...] | list[dict[str, Any]]) -> SolverConfigsSnapshot:
        pairs: list[tuple[tuple[str, int], dict[str, Any]]] = []
        seen: set[tuple[str, int]] = set()
        for config in configs:
            solver_id = str(config.get("solver_id", "")).strip()
            if not solver_id:
                raise ValueError("solver config snapshot requires solver_id.")
            param_set_index = int(config.get("param_set_index", -1))
            if param_set_index < 0:
                raise ValueError("solver config snapshot requires param_set_index >= 0.")
            key = (solver_id, param_set_index)
            if key in seen:
                raise ValueError(f"duplicate solver config snapshot: {key!r}")
            for field in ("solver_class", "capabilities", "stop_condition", "params"):
                if field not in config:
                    raise ValueError(f"solver config snapshot missing required field: {field}")
            seen.add(key)
            pairs.append((key, copy.deepcopy(config)))
        if not pairs:
            raise ValueError("solver config snapshot cannot be empty.")
        return cls(_by_key=tuple(pairs))

    def get(self, solver_id: str, param_set_index: int) -> dict[str, Any]:
        key = (solver_id, param_set_index)
        for stored_key, cfg in self._by_key:
            if stored_key == key:
                return copy.deepcopy(cfg)
        raise KeyError(
            f"solver config not in snapshot: solver_id={solver_id!r}, "
            f"param_set_index={param_set_index!r}"
        )

    def solver_ids(self) -> frozenset[str]:
        return frozenset(sid for (sid, _), _ in self._by_key)

    def param_set_indices(self, solver_id: str) -> tuple[int, ...]:
        return tuple(index for (sid, index), _ in self._by_key if sid == solver_id)

    def keys(self) -> frozenset[tuple[str, int]]:
        return frozenset(key for key, _ in self._by_key)

    def to_worker_init_dict(self) -> dict[tuple[str, int], dict[str, Any]]:
        """供子行程 initializer pickle；與主行程快照內容一致之深拷貝。"""
        return {key: copy.deepcopy(cfg) for key, cfg in self._by_key}
