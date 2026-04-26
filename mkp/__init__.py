"""MKP simulation system package."""

from .bsma_equivalence import EquivalenceReport, verify_equivalence, write_equivalence_report
from .bsma_v1_008_solver import BSMAV1008Core, BSMAV1008Solver
from .contracts import ExecutionMode, ExperimentSpec, ProblemModel, RunResult, RunTask
from .engine import Engine, SimulationBundle
from .converter import ensure_problem_yaml_from_dat, list_converters, load_problem_model_from_repo_dat
from .problem_repository import ProblemRepository
from .result_writer import ResultEntry, ResultWriter
from .simulator import Simulator
from .stage1_validation import run_stage1_validation
from .solver_config_loader import SolverConfigLoader
from .solver_registry import SolverRegistry, StubMaxIterationsSolver
from .validator import ValidationReport, Validator


def __getattr__(name: str):
    """延遲載入 `main`，避免 `python -m mkp.app` 時 runpy 對先載入子模組發出 RuntimeWarning。"""
    if name == "main":
        from .app import main as _main

        return _main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Engine",
    "ExecutionMode",
    "ExperimentSpec",
    "SimulationBundle",
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
