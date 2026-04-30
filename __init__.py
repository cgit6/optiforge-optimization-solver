"""MKP simulation system package."""

from .cli.convert import list_converters
from .cli.run import executeSimulator
from .converter import ensure_problem_yaml_from_dat, load_problem_model_from_repo_dat
from .engine import Engine, SimulationBundle, SolverConfigsSnapshot, build
from .engine.models import ExecutionMode, ExperimentSpec, ProblemModel, RunResult, RunTask
from .engine.repository import ProblemRepository
from .simulator import Simulator
from .solver.BSMA import BSMAV1008Core, BSMAV1008Solver
from .solver.solver_registry import SolverRegistry, StubMaxIterationsSolver
from .solver.validator import ValidationReport, Validator
from .tools.result_writer import ResultEntry, ResultWriter
from .tools.solver_config_loader import SolverConfigLoader
from .valid.bsma_equivalence import EquivalenceReport, verify_equivalence, write_equivalence_report
from .valid.stage1_validation import run_stage1_validation


def __getattr__(name: str):
    """延遲載入 `main`（實作於 `mkp.cli.run`），避免未使用 `main` 時額外載入 CLI 模組。"""
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
    "EquivalenceReport",
    "main",
    "ProblemModel",
    "RunResult",
    "RunTask",
    "load_problem_model_from_repo_dat",
    "ensure_problem_yaml_from_dat",
    "list_converters",
    "ProblemRepository",
    "ResultEntry",
    "ResultWriter",
    "Simulator",
    "run_stage1_validation",
    "SolverConfigLoader",
    "SolverRegistry",
    "StubMaxIterationsSolver",
    "ValidationReport",
    "Validator",
    "verify_equivalence",
    "write_equivalence_report",
]
