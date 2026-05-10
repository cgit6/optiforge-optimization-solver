"""於 engine 階段預載 solver YAML，執行期僅從記憶體讀取（與題庫預載對齊）。"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..tools.solver_config_loader import SolverConfigLoader
from .models import ExperimentSpec


@dataclass(frozen=True)
class SolverConfigsSnapshot:
    """`spec.solver_ids` 對應的所有參數組設定；對外 `get` 再給副本以免求解改寫快照。"""

    _by_key: tuple[tuple[tuple[str, int], dict[str, Any]], ...]

    @classmethod
    def build(cls, spec: ExperimentSpec, solver_root: Path | str) -> SolverConfigsSnapshot:
        loader = SolverConfigLoader(config_root=solver_root)
        pairs: list[tuple[tuple[str, int], dict[str, Any]]] = []
        for solver_id in spec.solver_ids:
            for raw in loader.load_all(solver_id):
                param_set_index = int(raw["param_set_index"])
                pairs.append(((solver_id, param_set_index), copy.deepcopy(raw)))
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
