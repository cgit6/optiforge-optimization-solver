"""SimulationBundle、`build` 與 `Engine` 組裝介面。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, cast

import numpy as np

from ..simulator import Simulator
from ..solver.registry import SolverBuilder, SolverRegistry
from ..solver.validator import Validator
from ..tools.result_writer import ResultWriter
from .models import ExperimentSpec
from .configs import SolverConfigsSnapshot
from .bank import (
    GameSetting,
    ProblemBank,
    ProblemCatalogEntry,
    assert_spec_problems_in_catalog,
    scan_problem_catalog,
    validate_catalog_entries,
)
from .repository import ProblemRepository
from .builders import default_solver_builders

DefaultRngFactory = Callable[..., np.random.Generator]


def build(
    *,
    spec: ExperimentSpec,
    problem_root: Path,
    solver_root: Path,
    output_root: Path,
    solver_builders: dict[str, SolverBuilder] | None = None,
) -> SimulationBundle:
    """掃描與驗證題庫、建 ProblemBank 與 bundle；不在此建立 `Simulator`。"""
    problem_repository = ProblemRepository(config_root=problem_root)
    raw_catalog, game_setting = scan_problem_catalog(problem_root)
    validate_catalog_entries(problem_repository, list(raw_catalog))
    assert_spec_problems_in_catalog(spec, list(raw_catalog))
    solver_configs = SolverConfigsSnapshot.build(spec, Path(solver_root))
    problem_bank = ProblemBank.build_for_spec(repository=problem_repository, spec=spec)
    builders = dict(solver_builders) if solver_builders is not None else default_solver_builders()
    return SimulationBundle(
        spec=spec,
        game_setting=game_setting,
        catalog=tuple(raw_catalog),
        problem_bank=problem_bank,
        solver_configs=solver_configs,
        solver_builders=builders,
        default_rng=cast(DefaultRngFactory, np.random.default_rng),
        solver_root=Path(solver_root),
        output_root=Path(output_root),
    )


@dataclass(frozen=True)
class SimulationBundle:
    """Engine 組裝結果：catalog、ProblemBank、預載 solver 設定、求解器建構子與 RNG 工廠；`Simulator` 由 `NewSimulatorWithSeed` 建立。"""

    spec: ExperimentSpec
    game_setting: GameSetting
    catalog: tuple[ProblemCatalogEntry, ...]
    problem_bank: ProblemBank
    solver_configs: SolverConfigsSnapshot
    solver_builders: dict[str, SolverBuilder]
    default_rng: DefaultRngFactory
    solver_root: Path
    output_root: Path

    def NewSimulatorWithSeed(self, solver_id: str, base_seed: int) -> Simulator:
        """以目前 bundle 的題庫與輸出設定建立 `Simulator`。

        呼叫端應以 :meth:`Simulator.run_sequential` 或（僅 ``worker_curriculum`` 且 ``repeat>1``）:meth:`Simulator.run_batch` 執行；若需覆寫種子可 ``dataclasses.replace(self.spec, seed=seed)`` 與此處一致。
        """
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
            result_writer=ResultWriter(
                experiment_id=self.spec.experiment_id,
                output_root=self.output_root,
            ),
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
