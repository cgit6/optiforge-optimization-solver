"""MKP simulation system package."""

from .app import main
from .bsma_equivalence import EquivalenceReport, verify_equivalence, write_equivalence_report
from .bsma_v1_008_solver import BSMAV1008Core, BSMAV1008Solver
from .contracts import ExperimentSpec, ProblemModel, RunResult, RunTask
from .problem_repository import ProblemRepository
from .result_writer import ResultEntry, ResultWriter
from .simulator import Simulator
from .stage1_validation import run_stage1_validation
from .solver_config_loader import SolverConfigLoader
from .solver_registry import SolverRegistry, StubMaxIterationsSolver
from .validator import ValidationReport, Validator

__all__ = [
    "ExperimentSpec",
    "BSMAV1008Core",
    "BSMAV1008Solver",
    "EquivalenceReport",
    "main",
    "ProblemModel",
    "RunResult",
    "RunTask",
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
