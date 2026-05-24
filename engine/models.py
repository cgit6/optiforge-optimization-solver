from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

import numpy as np

from ..problem.validation import ObjectiveValue, normalize_objective_value


@dataclass(frozen=True)
class ExperimentSpec:
    """實驗規格"""
    experiment_name: str # 實驗名稱
    dataset: str # 題庫
    problem_ids: tuple[str, ...] # 題目 id 清單
    solver_ids: tuple[str, ...] # 求解器
    repeat: int # 重複次數
    problem_type: str = "mkp" # 優化問題
    worker_count: int = 1 # 併發數
    base_seed: int | None = None # 這次模擬執行使用的 immutable base seed；執行 Simulator 前需設定

    def __post_init__(self) -> None:
        if not self.experiment_name.strip():
            raise ValueError("experiment_name cannot be empty.")
        if not self.problem_type.strip():
            raise ValueError("problem_type cannot be empty.")
        if not self.dataset.strip():
            raise ValueError("dataset cannot be empty.")
        if self.repeat <= 0:
            raise ValueError("repeat must be > 0.")
        if self.worker_count <= 0:
            raise ValueError("worker_count must be > 0.")
        if not self.problem_ids:
            raise ValueError("problem_ids cannot be empty.")
        if not self.solver_ids:
            raise ValueError("solver_ids cannot be empty.")
        if any(not problem_id.strip() for problem_id in self.problem_ids):
            raise ValueError("problem_ids cannot contain empty value.")
        if any(not solver_id.strip() for solver_id in self.solver_ids):
            raise ValueError("solver_ids cannot contain empty value.")
        if len(set(self.problem_ids)) != len(self.problem_ids):
            raise ValueError("problem_ids cannot contain duplicate value.")
        if len(set(self.solver_ids)) != len(self.solver_ids):
            raise ValueError("solver_ids cannot contain duplicate value.")
        if self.base_seed is not None:
            base_seed = int(self.base_seed)
            if base_seed < 0:
                raise ValueError("base_seed must be >= 0.")
            object.__setattr__(self, "base_seed", base_seed)

@dataclass(frozen=True)
class RunTask:
    problem_id: str # 題目
    dataset: str # 題庫
    solver_id: str # 求解器
    repeat_index: int # 重複第幾次
    task_seed: int # seed
    param_set_index: int # 參數設定
    problem_type: str = "mkp"

    def __post_init__(self) -> None:
        if not self.problem_type.strip():
            raise ValueError("problem_type cannot be empty.")
        if not self.problem_id.strip():
            raise ValueError("problem_id cannot be empty.")
        if not self.dataset.strip():
            raise ValueError("dataset cannot be empty.")
        if not self.solver_id.strip():
            raise ValueError("solver_id cannot be empty.")
        if self.repeat_index < 0:
            raise ValueError("repeat_index must be >= 0.")
        if self.task_seed < 0:
            raise ValueError("task_seed must be >= 0.")
        if self.param_set_index < 0:
            raise ValueError("param_set_index must be >= 0.")


@dataclass(frozen=True)
class SolveResult:
    problem_id: str
    solver_id: str
    run_seed: int
    best_solution: np.ndarray
    best_objective: ObjectiveValue
    feasible: bool
    evaluation_count: int
    stop_reason: str
    runtime: float
    linprog_runtime: float = 0.0
    error: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.problem_id.strip():
            raise ValueError("problem_id cannot be empty.")
        if not self.solver_id.strip():
            raise ValueError("solver_id cannot be empty.")
        if self.run_seed < 0:
            raise ValueError("run_seed must be >= 0.")
        if self.evaluation_count < 0:
            raise ValueError("evaluation_count must be >= 0.")
        if self.runtime < 0:
            raise ValueError("runtime must be >= 0.")
        if self.linprog_runtime < 0:
            raise ValueError("linprog_runtime must be >= 0.")
        if not self.stop_reason.strip():
            raise ValueError("stop_reason cannot be empty.")
        object.__setattr__(
            self,
            "best_objective",
            normalize_objective_value(self.best_objective, name="best_objective"),
        )

        best_solution = np.asarray(self.best_solution)
        if best_solution.ndim != 1:
            raise ValueError("best_solution must be a 1D array.")
        best_solution.setflags(write=False)
        object.__setattr__(self, "best_solution", best_solution)
        object.__setattr__(self, "metadata", dict(self.metadata))
