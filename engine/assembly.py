"""SimulationBundle、`build` 與 `Engine` 組裝介面。"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable, cast

import numpy as np

from ..solver.registry import SolverBuilder, SolverRegistry
from ..solver.validator import Validator
from .models import ExperimentSpec
from .configs import SolverConfigsSnapshot
from .bank import (
    CatalogSummary,
    ProblemBank,
    ProblemCatalogEntry,
    assert_spec_problems_in_catalog,
    scan_problem_catalog,
    validate_spec_problems_in_repository,
)
from .repository import ProblemRepository
from .builders import default_solver_builders

if TYPE_CHECKING:
    from ..simulator.core import Simulator

DefaultRngFactory = Callable[..., np.random.Generator]


def build(
    *,
    spec: ExperimentSpec, # 實驗規格
    problem_root: Path, # 題庫資料夾的路徑
    solver_root: Path, # 算法的參數設定
    output_root: Path, # 輸出資料夾的論竟
    solver_builders: dict[str, SolverBuilder] | None = None,
) -> SimulationBundle:
    """掃描與驗證題庫、建 ProblemBank 與 bundle；不在此建立 `Simulator`。"""

    type = spec.problem_type # 問題類型(這個需要經過合法性測試)
    problem_repository = ProblemRepository(config_root=problem_root)
    print(f"[{type}] scanning problem catalog under {problem_root} ...", file=sys.stderr, flush=True)
    raw_catalog, catalog_summary = scan_problem_catalog(problem_root)
    assert_spec_problems_in_catalog(spec, list(raw_catalog))
    n_problems = len(set(spec.problem_ids))
    print(
        f"[{type}] loading {n_problems} experiment problem(s) ...",
        file=sys.stderr,
        flush=True,
    )
    validate_spec_problems_in_repository(problem_repository, spec)
    print(f"[{type}] loading solver configs ...", file=sys.stderr, flush=True)
    solver_configs = SolverConfigsSnapshot.build(spec, Path(solver_root))
    print(f"[{type}] building shared-memory problem bank ...", file=sys.stderr, flush=True)
    problem_bank = ProblemBank.build_for_spec(repository=problem_repository, spec=spec)
    print(f"[{type}] engine build done.", file=sys.stderr, flush=True)
    builders = dict(solver_builders) if solver_builders is not None else default_solver_builders()
    return SimulationBundle(
        spec=spec, # 實驗設定
        catalog_summary=catalog_summary, # 題庫索引摘要
        catalog=tuple(raw_catalog), # 
        problem_bank=problem_bank, # 題庫
        solver_configs=solver_configs, # 算法設定
        solver_builders=builders, 
        default_rng=cast(DefaultRngFactory, np.random.default_rng),
        solver_root=Path(solver_root),
        output_root=Path(output_root),
    )


@dataclass(frozen=True)
class SimulationBundle:
    """Engine 組裝結果：catalog、ProblemBank、預載 solver 設定、求解器建構子與 RNG 工廠；`Simulator` 由 `NewSimulatorWithSeed` 建立。"""

    spec: ExperimentSpec # 實驗規格
    catalog_summary: CatalogSummary # 題庫索引摘要
    catalog: tuple[ProblemCatalogEntry, ...]
    problem_bank: ProblemBank # 題庫
    solver_configs: SolverConfigsSnapshot # 算法的設定
    solver_builders: dict[str, SolverBuilder]
    default_rng: DefaultRngFactory
    solver_root: Path
    output_root: Path

    def NewSimulatorWithSeed(self, solver_id: str, base_seed: int) -> Simulator:
        """以目前 bundle 的題庫設定建立 `Simulator`；輸出由 caller 透過 stat 模組處理。

        呼叫端應以 :meth:`Simulator.run_sequential` 或（僅 ``worker_curriculum`` 且 ``repeat>1``）:meth:`Simulator.run_batch` 執行；若需覆寫種子可 ``dataclasses.replace(self.spec, seed=seed)`` 與此處一致。
        """
        from ..simulator.core import Simulator

        if solver_id not in self.solver_builders:
            raise KeyError(
                f"Unknown solver (not in solver_builders): {solver_id!r} "
                f"(intended run_batch base_seed={base_seed!r})"
            )
        registry = SolverRegistry()
        for sid, builder in self.solver_builders.items():
            registry.register(sid, builder)
        return Simulator(
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
        output_root: Path,
    ) -> SimulationBundle:
        return build(
            spec=spec,
            problem_root=problem_root,
            solver_root=solver_root,
            output_root=output_root,
        )
