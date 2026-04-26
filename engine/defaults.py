"""內建求解器建構子（可由 `build(..., solver_builders=...)` 覆寫）。"""

from __future__ import annotations

from ..solver.bsma_v1_008_solver import BSMAV1008Solver
from ..solver.solver_registry import SolverBuilder, StubMaxIterationsSolver


def default_solver_builders() -> dict[str, SolverBuilder]:
    return {
        "stub_solver": lambda: StubMaxIterationsSolver(),
        "bsma_v1_008": lambda: BSMAV1008Solver(),
    }
