"""內建求解器建構子（可由 `build(..., solver_builders=...)` 覆寫）。"""

from __future__ import annotations

from ..solver.BSCA import BSCASolver
from ..solver.BSCA_numba import BSCANumbaSolver
from ..solver.BSCA_rc_numba import BSCARCNumbaSolver
from ..solver.BSCASMA import BRLSMASCATestSolver
from ..solver.BSCASMA_rl_rc_numba import BRLSMASCARLRCNumbaSolver
from ..solver.BSCASMA_rl_numba import BRLSMASCARLNumbaSolver
from ..solver.BSCASMA_test_numba import BRLSMASCATestNumbaSolver
from ..solver.BSMA import BSMASolver
from ..solver.BSMA_numba import BSMANumbaSolver
from ..solver.BSMA_rc_numba import BSMARCNumbaSolver
from ..solver.registry import SolverBuilder, StubMaxIterationsSolver


# 註冊新求解
def solverBuilders() -> dict[str, SolverBuilder]:
    return {
        "stub_solver": lambda: StubMaxIterationsSolver(),
        "bsma": lambda: BSMASolver(),
        "bsma_numba": lambda: BSMANumbaSolver(),
        "bsma_rc_numba": lambda: BSMARCNumbaSolver(),
        "bsca": lambda: BSCASolver(),
        "bsca_numba": lambda: BSCANumbaSolver(),
        "bsca_rc_numba": lambda: BSCARCNumbaSolver(),
        "brlsmasca": lambda: BRLSMASCATestSolver(),
        "brlsmasca_rl_numba": lambda: BRLSMASCARLNumbaSolver(),
        "brlsmasca_rl_rc_numba": lambda: BRLSMASCARLRCNumbaSolver(),
        "brlsmasca_test_numba": lambda: BRLSMASCATestNumbaSolver(),
    }
