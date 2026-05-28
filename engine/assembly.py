"""SimulationBundle、`build` 與 `Engine` 組裝介面。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping

from ..solver.registry import SolverBuilder, SolverRegistry
from ..problem import buildProblemRegistry, problemBuilders
from ..rng import RngFactory, SeedStrategy, make_numpy_rng
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



# 這邊有個需要特別判斷的事情，就是收入的題庫範圍
def build(
    *,
    spec: ExperimentSpec, # 實驗規格
    problem_root: Path, # 題庫資料夾的路徑
    solver_root: Path, # 算法的參數設定
    seed_strategy: SeedStrategy,
    rng_factory: RngFactory = make_numpy_rng,
    solver_param_set_indices: Mapping[str, tuple[int, ...]] | None = None,
    solver_configs: SolverConfigsSnapshot | None = None,
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
    solver_configs = solver_configs or SolverConfigsSnapshot.build(
        spec,
        Path(solver_root),
        param_set_indices=solver_param_set_indices,
    )
    # 讀 problem_repository 的 cacha 抓這次要實驗的題庫和題目，返回 ProblemBank 物件
    # 這裡也會放進 share memory 中
    problem_bank = ProblemBank.build(repository=problem_repository, spec=spec, registry=problem_registry)
    
    # 求解器註冊清單
    builders = solverBuilders()


    return SimulationBundle(
        spec=spec, # 實驗設定
        catalog_summary=summary, # 題庫索引摘要
        catalog=tuple(catalog), # 掃描整個題庫後得到的題目索引清單
        problem_bank=problem_bank, # 題目緩存
        solver_configs=solver_configs, # 求解器參數設定
        solver_builders=builders, # 求解器註冊清單
        seed_strategy=seed_strategy, # task_seed 產生器
        rng_factory=rng_factory,
        solver_root=Path(solver_root),
        # 實驗模組物件
    )


@dataclass(frozen=True)
class SimulationBundle:
    """Engine 組裝結果：catalog、ProblemBank、預載 solver 設定、求解器建構子與 RNG 工廠；`Simulator` 由 `new_simulator` 建立。"""

    spec: ExperimentSpec # 實驗規格
    catalog_summary: CatalogSummary # 題庫索引摘要
    catalog: tuple[ProblemCatalogEntry, ...] # 
    problem_bank: ProblemBank # 題目清單
    solver_configs: SolverConfigsSnapshot # 算法的設定
    solver_builders: dict[str, SolverBuilder] # 建構算法函數的函數
    seed_strategy: SeedStrategy # task seed 派生策略
    rng_factory: RngFactory # RNG 工廠函數
    solver_root: Path # 求解器根路徑
    exp_cfg: Any = None # 實驗模組的設定(選填，如果執行 cil.exp 的時候會把 exp_cfg.yaml 的設定保存至此地)

    def new_simulator(self) -> Simulator:
        """以目前 bundle 的題庫設定建立 `Simulator`；輸出由 caller 透過 stat 模組處理。

        呼叫端應以 :meth:`Simulator.run_sequential` 或 :meth:`Simulator.run_batch` 執行；
        seed 由 `spec.base_seed` 提供，模擬期間不可變。
        """
        if len(self.spec.solver_ids) != 1:
            raise ValueError("new_simulator requires exactly one solver; use new_simulators for multi-solver specs.")
        from ..simulator.core import Simulator

        registry = self._new_solver_registry()

        return Simulator(
            spec=self.spec,
            problem_bank=self.problem_bank,
            solver_registry=registry,
            solver_configs=self.solver_configs,
            seed_strategy=self.seed_strategy,
            rng_factory=self.rng_factory,
        )

    def new_simulators(self) -> tuple[Simulator, ...]:
        """依 solver_id 拆成多個 single-solver Simulator，並共享同一份 bundle 資源。"""
        from ..simulator.core import Simulator

        simulators: list[Simulator] = []
        for solver_id in self.spec.solver_ids:
            # 拆成單一 solver 的實驗規格
            single_solver_spec = replace(self.spec, solver_ids=(solver_id,))
            simulators.append(
                Simulator(
                    spec=single_solver_spec,
                    problem_bank=self.problem_bank,
                    solver_registry=self._new_solver_registry(),
                    solver_configs=self.solver_configs,
                    seed_strategy=self.seed_strategy,
                    rng_factory=self.rng_factory,
                )
            )
        return tuple(simulators)

    def _new_solver_registry(self) -> SolverRegistry:
        registry = SolverRegistry()
        for sid, builder in self.solver_builders.items():
            registry.register(sid, builder)
        return registry

    # 這方法的意義是什麼應該只需要保留 new 或是 new_simulator 擇一
    def new(self) -> Simulator:
        return self.new_simulator()

class Engine:
    """將 Repository、Registry、Loader、Writer 與 Simulator 組成一個可跑批次。"""

    @staticmethod
    def build(
        *,
        spec: ExperimentSpec,
        problem_root: Path,
        solver_root: Path,
        seed_strategy: SeedStrategy,
        rng_factory: RngFactory = make_numpy_rng,
        solver_param_set_indices: Mapping[str, tuple[int, ...]] | None = None,
        solver_configs: SolverConfigsSnapshot | None = None,
    ) -> SimulationBundle:
        return build(
            spec=spec,
            problem_root=problem_root,
            solver_root=solver_root,
            seed_strategy=seed_strategy,
            rng_factory=rng_factory,
            solver_param_set_indices=solver_param_set_indices,
            solver_configs=solver_configs,
        )
