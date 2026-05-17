"""SimulationBundle、`build` 與 `Engine` 組裝介面。"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable, cast

import numpy as np

from ..solver.registry import SolverBuilder, SolverRegistry
from ..solver.validator import Validator
from ..problem import buildProblemRegistry, problemBuilders
from .models import ExperimentSpec
from .configs import SolverConfigsSnapshot
from .bank import (
    CatalogSummary,
    ProblemBank,
    ProblemCatalogEntry,
    assert_spec_problems_in_catalog,
    scanProblemCatalog,
    validate_spec_problems_in_repository,
)
from .repository import ProblemRepository
from .builders import solverBuilders

if TYPE_CHECKING:
    from ..simulator.core import Simulator

DefaultRngFactory = Callable[..., np.random.Generator]



# 這邊有個需要特別判斷的事情，就是收入的題庫範圍
def build(
    *,
    spec: ExperimentSpec, # 實驗規格
    problem_root: Path, # 題庫資料夾的路徑
    solver_root: Path, # 算法的參數設定
    # solver_builders: dict[str, SolverBuilder],
) -> SimulationBundle:
    """掃描與驗證題庫、建 ProblemBank 與 bundle；不在此建立 `Simulator`。"""

    # 建立優化問題註冊清單
    problem_registry = buildProblemRegistry(problemBuilders())
    # 建立一個讀題目檔的工具物件
    problem_repository = ProblemRepository(problem_root=problem_root, registry=problem_registry)
    # 掃描題庫資料夾做成摘要還有題目清單
    catalog, summary = scanProblemCatalog(problem_root, problem_registry)
    # 檢查這次要跑的題庫和題目掃描的時候都有找到
    assert_spec_problems_in_catalog(spec, list(catalog))
    # 把實驗要用的題目載入並驗證檔案可以被解析，沒問題就存入 problem_repository  中
    validate_spec_problems_in_repository(problem_repository, spec)
    # 預先把這次會用到的 solver YAML 設定全部載好，封裝成唯讀快照，讓後面模擬執行時直接從記憶體拿
    solver_configs = SolverConfigsSnapshot.build(spec, Path(solver_root))
    # 讀 problem_repository 的 cacha 抓這次要實驗的題庫和題目，返回 ProblemBank 物件
    problem_bank = ProblemBank.build(repository=problem_repository, spec=spec, registry=problem_registry)
    
    # 求解器註冊清單
    builders = solverBuilders()


    return SimulationBundle(
        spec=spec, # 實驗設定
        catalog_summary=summary, # 題庫索引摘要
        catalog=tuple(catalog), # 掃描整個題庫後得到的題目索引清單
        problem_bank=problem_bank, # 題庫
        solver_configs=solver_configs, # 求解器參數設定
        solver_builders=builders, # 求解器註冊清單
        default_rng=cast(DefaultRngFactory, np.random.default_rng),
        solver_root=Path(solver_root),
        # 實驗模組物件
    )


@dataclass(frozen=True)
class SimulationBundle:
    """Engine 組裝結果：catalog、ProblemBank、預載 solver 設定、求解器建構子與 RNG 工廠；`Simulator` 由 `new_simulator` 建立。"""

    spec: ExperimentSpec # 實驗規格
    catalog_summary: CatalogSummary # 題庫索引摘要
    catalog: tuple[ProblemCatalogEntry, ...] # 
    problem_bank: ProblemBank # 題庫
    solver_configs: SolverConfigsSnapshot # 算法的設定
    solver_builders: dict[str, SolverBuilder] # 建構算法函數的函數
    default_rng: DefaultRngFactory # RNG 工廠函數
    solver_root: Path # 求解器根路徑

    def new_simulator(self) -> Simulator:
        """以目前 bundle 的題庫設定建立 `Simulator`；輸出由 caller 透過 stat 模組處理。

        呼叫端應以 :meth:`Simulator.run_sequential` 或 :meth:`Simulator.run_batch` 執行；
        若需覆寫種子應建立新的 :class:`ExperimentSpec` 與 bundle。
        """
        from ..simulator.core import Simulator

        registry = SolverRegistry()
        for sid, builder in self.solver_builders.items():
            registry.register(sid, builder)
        return Simulator(
            spec=self.spec,
            problem_bank=self.problem_bank,
            solver_registry=registry,
            solver_configs=self.solver_configs,
            validator=Validator(),
        )

class Engine:
    """將 Repository、Registry、Loader、Validator、Writer 與 Simulator 組成一個可跑批次。"""

    @staticmethod
    def build(
        *,
        spec: ExperimentSpec,
        problem_root: Path,
        solver_root: Path,
    ) -> SimulationBundle:
        return build(
            spec=spec,
            problem_root=problem_root,
            solver_root=solver_root,
        )
