from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

ExecutionMode = Literal["grid", "worker_curriculum"]

import numpy as np

# 將輸入的資料轉換為整數陣列
def _as_int_array(name: str, data: np.ndarray | list[int]) -> np.ndarray:
    arr = np.asarray(data, dtype=int)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be a 1D integer array.")
    return arr


# 將輸入的資料轉換為整數矩陣
def _as_int_matrix(name: str, data: np.ndarray | list[list[int]]) -> np.ndarray:
    arr = np.asarray(data, dtype=int)
    if arr.ndim != 2:
        raise ValueError(f"{name} must be a 2D integer matrix.")
    return arr


# 實驗規格
@dataclass(frozen=True)
class ExperimentSpec:
    experiment_id: str # 實驗ID
    dataset: str # 資料集
    problem_ids: tuple[str, ...] # 問題ID
    solver_ids: tuple[str, ...] # 求解器ID
    repeat: int  # 獨立實驗次數；worker_curriculum 時亦為同時 worker 線數
    seed: int # 基礎種子
    output_dir: Path # 輸出目錄
    benchmark_enabled: bool = False # 是否啟用benchmark
    execution_mode: ExecutionMode = "grid"  # 任務展開與執行順序

    def __post_init__(self) -> None:
        if not self.experiment_id.strip():
            raise ValueError("experiment_id cannot be empty.")
        if not self.dataset.strip():
            raise ValueError("dataset cannot be empty.")
        if self.repeat <= 0:
            raise ValueError("repeat must be > 0.")
        if not self.problem_ids:
            raise ValueError("problem_ids cannot be empty.")
        if not self.solver_ids:
            raise ValueError("solver_ids cannot be empty.")
        if any(not problem_id.strip() for problem_id in self.problem_ids):
            raise ValueError("problem_ids cannot contain empty value.")
        if any(not solver_id.strip() for solver_id in self.solver_ids):
            raise ValueError("solver_ids cannot contain empty value.")
        if self.execution_mode not in ("grid", "worker_curriculum"):
            raise ValueError(
                "execution_mode must be 'grid' or 'worker_curriculum'."
            )


# 問題模型
@dataclass(frozen=True)
class ProblemModel:
    problem_id: str # 問題ID
    dataset: str # 資料集
    items: int # 物品數量
    dim: int # 限制維度數量
    values: np.ndarray # 物品價值
    weights: np.ndarray # 物品重量
    capacities: np.ndarray # 限制容量
    best_known: int # 最佳已知解

    def __post_init__(self) -> None:
        if not self.problem_id.strip():
            raise ValueError("problem_id cannot be empty.")
        if not self.dataset.strip():
            raise ValueError("dataset cannot be empty.")
        if self.items <= 0:
            raise ValueError("items must be > 0.")
        if self.dim <= 0:
            raise ValueError("dim must be > 0.")
        if self.best_known < 0:
            raise ValueError("best_known must be >= 0.")

        values = _as_int_array("values", self.values)
        weights = _as_int_matrix("weights", self.weights)
        capacities = _as_int_array("capacities", self.capacities)

        if len(values) != self.items:
            raise ValueError("len(values) must equal items.")
        if weights.shape != (self.items, self.dim):
            raise ValueError("weights shape must be (items, dim).")
        if len(capacities) != self.dim:
            raise ValueError("len(capacities) must equal dim.")

        values.setflags(write=False)
        weights.setflags(write=False)
        capacities.setflags(write=False)

        object.__setattr__(self, "values", values)
        object.__setattr__(self, "weights", weights)
        object.__setattr__(self, "capacities", capacities)


# 執行任務
@dataclass(frozen=True)
class RunTask:
    problem_id: str
    dataset: str
    solver_id: str
    repeat_index: int
    seed: int

    def __post_init__(self) -> None:
        if not self.problem_id.strip():
            raise ValueError("problem_id cannot be empty.")
        if not self.dataset.strip():
            raise ValueError("dataset cannot be empty.")
        if not self.solver_id.strip():
            raise ValueError("solver_id cannot be empty.")
        if self.repeat_index < 0:
            raise ValueError("repeat_index must be >= 0.")
        if self.seed < 0:
            raise ValueError("seed must be >= 0.")


# 執行結果（僅演算法輸出；第幾次 repeat 由 RunTask / Simulator 管）
@dataclass(frozen=True)
class RunResult:
    problem_id: str
    solver_id: str
    seed: int
    best_solution: np.ndarray
    best_objective: int
    feasible: bool
    evaluation_count: int
    stop_reason: str
    runtime: float
    linprog_runtime: float = 0.0
    error: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.problem_id.strip():
            raise ValueError("problem_id cannot be empty.")
        if not self.solver_id.strip():
            raise ValueError("solver_id cannot be empty.")
        if self.seed < 0:
            raise ValueError("seed must be >= 0.")
        if self.evaluation_count < 0:
            raise ValueError("evaluation_count must be >= 0.")
        if self.runtime < 0:
            raise ValueError("runtime must be >= 0.")
        if self.linprog_runtime < 0:
            raise ValueError("linprog_runtime must be >= 0.")
        if not self.stop_reason.strip():
            raise ValueError("stop_reason cannot be empty.")

        best_solution = _as_int_array("best_solution", self.best_solution)
        best_solution.setflags(write=False)
        object.__setattr__(self, "best_solution", best_solution)
