"""內建求解器建構子（可由 `build(..., solver_builders=...)` 覆寫）。"""

from __future__ import annotations

from ..solver.BSCA import BSCASolver
from ..solver.BSCA_numba import BSCANumbaSolver
from ..solver.BSCASMA import BRLSMASCATestSolver
from ..solver.BSCASMA_rl_numba import BRLSMASCARLNumbaSolver
from ..solver.BSCASMA_test_numba import BRLSMASCATestNumbaSolver
from ..solver.BSMA import BSMASolver
from ..solver.BSMA_numba import BSMANumbaSolver
from ..solver.registry import SolverBuilder, StubMaxIterationsSolver


# 註冊新求解
def solverBuilders() -> dict[str, SolverBuilder]:
    return {
        "stub_solver": lambda: StubMaxIterationsSolver(),
        "bsma": lambda: BSMASolver(),
        "bsma_numba": lambda: BSMANumbaSolver(),
        "bsca": lambda: BSCASolver(),
        "bsca_numba": lambda: BSCANumbaSolver(),
        "brlsmasca": lambda: BRLSMASCATestSolver(),
        "brlsmasca_rl_numba": lambda: BRLSMASCARLNumbaSolver(),
        "brlsmasca_test_numba": lambda: BRLSMASCATestNumbaSolver(),
    }
