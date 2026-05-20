"""MKP simulation system package."""

if __name__ == "__init__" and not __package__:
    import os as _os

    __package__ = "mkp"
    if __spec__ is not None:
        __spec__.name = "mkp"
        __spec__.submodule_search_locations = [_os.path.dirname(__file__)]
    del _os

from .cli.convert import getConverter, listConverters, register
from .cli.run import executeSimulator
from .converter import transformToMomery, transformToYaml
from .engine import Engine, SimulationBundle, SolverConfigsSnapshot, build
from .engine.models import ExperimentSpec, SolveResult, RunTask
from .engine.repository import ProblemRepository
from .problem import Problem, MKPProblem, ProblemModel, ProblemRegistry, ProblemTypeSpec, TSPProblem
from .simulator import Simulator, SimulatorResult, SimulatorRunRow
from .solver.BSCA import BSCACore, BSCASolver
from .solver.BSCASMA import BRLSMASCATestCore, BRLSMASCATestSolver
from .solver.BSMA import BSMACore, BSMASolver
from .solver.nearest_neighbor_tsp import NearestNeighborTSPSolver
from .solver.registry import SolverRegistry, StubMaxIterationsSolver
from .solver.sma_mkp_modular import SMAMKPModularV1Solver
from .solver.sma_tsp_modular import SMATSPModularV1Solver
from .solver.validator import ValidationReport, Validator
from .tools.show import write_simulator_result
from .tools.solver_config_loader import SolverConfigLoader
from .tools.stat import ResultEntry


def __getattr__(name: str):
    """延遲載入 `main`（實作於 `mkp.cli.run`）。"""
    if name == "main":
        from .cli.run.main import main as _main

        return _main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Engine",
    "ExperimentSpec",
    "SimulationBundle",
    "SimulatorResult",
    "SimulatorRunRow",
    "SolverConfigsSnapshot",
    "build",
    "executeSimulator",
    "BSCACore",
    "BSCASolver",
    "BRLSMASCATestCore",
    "BRLSMASCATestSolver",
    "BSMACore",
    "BSMASolver",
    "SMAMKPModularV1Solver",
    "SMATSPModularV1Solver",
    "NearestNeighborTSPSolver",
    "main",
    "ProblemModel",
    "Problem",
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
