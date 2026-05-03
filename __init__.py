"""MKP simulation system package."""

from .cli.convert import getConverter, listConverters, register
from .cli.run import executeSimulator
from .converter import transformToMomery, transformToYaml
from .engine import Engine, SimulationBundle, SolverConfigsSnapshot, build
from .engine.models import BaseProblem, ExecutionMode, ExperimentSpec, MKPProblem, ProblemModel, SolveResult, TSPProblem, RunTask
from .engine.problem_registry import ProblemRegistry, ProblemTypeSpec
from .engine.repository import ProblemRepository
from .simulator import Simulator, SimulatorResult, SimulatorRunRow
from .solver.BSCA2 import BSCA2V120Core, BSCA2V120Solver
from .solver.BSCASMA import BRLSMASCA2V100320050TestCore, BRLSMASCA2V100320050TestSolver
from .solver.BSMA import BSMACore, BSMASolver
from .solver.nearest_neighbor_tsp import NearestNeighborTSPSolver
from .solver.registry import SolverRegistry, StubMaxIterationsSolver
from .solver.sma_mkp_modular import SMAMKPModularV1Solver
from .solver.sma_tsp_modular import SMATSPModularV1Solver
from .solver.validator import ValidationReport, Validator
from .tools.solver_config_loader import SolverConfigLoader
from .tools.stat import ResultEntry, write_simulator_result


def __getattr__(name: str):
    """延遲載入 `main`（實作於 `mkp.cli.run`）。"""
    if name == "main":
        from .cli.run.main import main as _main

        return _main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Engine",
    "ExecutionMode",
    "ExperimentSpec",
    "SimulationBundle",
    "SimulatorResult",
    "SimulatorRunRow",
    "SolverConfigsSnapshot",
    "build",
    "executeSimulator",
    "BSCA2V120Core",
    "BSCA2V120Solver",
    "BRLSMASCA2V100320050TestCore",
    "BRLSMASCA2V100320050TestSolver",
    "BSMACore",
    "BSMASolver",
    "SMAMKPModularV1Solver",
    "SMATSPModularV1Solver",
    "NearestNeighborTSPSolver",
    "main",
    "ProblemModel",
    "BaseProblem",
    "MKPProblem",
    "TSPProblem",
    "ProblemRegistry",
    "ProblemTypeSpec",
    "SolveResult",
    "RunTask",
    "getConverter",
    "listConverters",
    "register",
    "transformToMomery",
    "transformToYaml",
    "ProblemRepository",
    "ResultEntry",
    "Simulator",
    "SolverConfigLoader",
    "SolverRegistry",
    "StubMaxIterationsSolver",
    "ValidationReport",
    "Validator",
    "write_simulator_result",
]
