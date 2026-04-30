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
    """`spec.solver_ids` 對應之設定；建構時讀檔並深拷貝，對外 `get` 再給副本以免求解改寫快照。"""

    _by_id: tuple[tuple[str, dict[str, Any]], ...]

    @classmethod
    def build(cls, spec: ExperimentSpec, solver_root: Path | str) -> SolverConfigsSnapshot:
        loader = SolverConfigLoader(config_root=solver_root)
        pairs: list[tuple[str, dict[str, Any]]] = []
        for solver_id in spec.solver_ids:
            raw = loader.load(solver_id)
            pairs.append((solver_id, copy.deepcopy(raw)))
        return cls(_by_id=tuple(pairs))

    def get(self, solver_id: str) -> dict[str, Any]:
        for sid, cfg in self._by_id:
            if sid == solver_id:
                return copy.deepcopy(cfg)
        raise KeyError(f"solver_id not in snapshot: {solver_id!r}")

    def solver_ids(self) -> frozenset[str]:
        return frozenset(sid for sid, _ in self._by_id)

    def to_worker_init_dict(self) -> dict[str, dict[str, Any]]:
        """供子行程 initializer pickle；與主行程快照內容一致之深拷貝。"""
        return {sid: copy.deepcopy(cfg) for sid, cfg in self._by_id}
