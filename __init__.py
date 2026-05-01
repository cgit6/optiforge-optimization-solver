"""MKP simulation system package."""

from .cli.convert import getConverter, listConverters, register
from .cli.run import executeSimulator
from .converter import transformToMomery, transformToYaml
from .engine import Engine, SimulationBundle, SolverConfigsSnapshot, build
from .engine.models import ExecutionMode, ExperimentSpec, ProblemModel, RunResult, RunTask
from .engine.repository import ProblemRepository
from .simulator import Simulator
from .solver.BSMA import BSMAV1008Core, BSMAV1008Solver
from .solver.registry import SolverRegistry, StubMaxIterationsSolver
from .solver.validator import ValidationReport, Validator
from .tools.result_writer import ResultEntry, ResultWriter
from .tools.solver_config_loader import SolverConfigLoader


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
    "SolverConfigsSnapshot",
    "build",
    "executeSimulator",
    "BSMAV1008Core",
    "BSMAV1008Solver",
    "main",
    "ProblemModel",
    "RunResult",
    "RunTask",
    "getConverter",
    "listConverters",
    "register",
    "transformToMomery",
    "transformToYaml",
    "ProblemRepository",
    "ResultEntry",
    "ResultWriter",
    "Simulator",
    "SolverConfigLoader",
    "SolverRegistry",
    "StubMaxIterationsSolver",
    "ValidationReport",
    "Validator",
]
