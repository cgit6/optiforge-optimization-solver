"""系統組裝層：依 ExperimentSpec 與路徑建立可執行的 Simulator。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .bsma_v1_008_solver import BSMAV1008Solver
from .contracts import ExperimentSpec
from .problem_bank import (
    GameSetting,
    ProblemBank,
    ProblemCatalogEntry,
    assert_spec_problems_in_catalog,
    scan_problem_catalog,
    validate_catalog_entries,
)
from .problem_repository import ProblemRepository
from .result_writer import ResultWriter
from .simulator import Simulator
from .solver_config_loader import SolverConfigLoader
from .solver_registry import SolverRegistry, StubMaxIterationsSolver
from .validator import Validator


@dataclass(frozen=True)
class SimulationBundle:
    """Engine 組裝結果：`spec` 描述本次實驗，`simulator` 為已注入依賴的可執行編排器。"""

    spec: ExperimentSpec
    simulator: Simulator
    game_setting: GameSetting | None = None
    catalog_entries: tuple[ProblemCatalogEntry, ...] | None = None
    problem_bank: ProblemBank | None = None


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
        problem_repository = ProblemRepository(config_root=problem_root)
        catalog_list, game_setting = scan_problem_catalog(problem_root)
        validate_catalog_entries(problem_repository, catalog_list)
        assert_spec_problems_in_catalog(spec, catalog_list)
        problem_bank = ProblemBank.build_for_spec(repository=problem_repository, spec=spec)

        solver_registry = SolverRegistry()
        solver_registry.register("stub_solver", lambda: StubMaxIterationsSolver())
        solver_registry.register("bsma_v1_008", lambda: BSMAV1008Solver())
        solver_config_loader = SolverConfigLoader(config_root=solver_root)
        validator = Validator()
        result_writer = ResultWriter(experiment_id=spec.experiment_id, output_root=output_root)
        simulator = Simulator(
            problem_bank=problem_bank,
            solver_registry=solver_registry,
            solver_config_loader=solver_config_loader,
            validator=validator,
            result_writer=result_writer,
        )
        return SimulationBundle(
            spec=spec,
            simulator=simulator,
            game_setting=game_setting,
            catalog_entries=tuple(catalog_list),
            problem_bank=problem_bank,
        )
