"""內建求解器建構子（可由 `build(..., solver_builders=...)` 覆寫）。"""

from __future__ import annotations

from ..solver.BSCA import BSCASolver
from ..solver.BSCA_numba_v2 import BSCANumbaSolver
from ..solver.BSCASMA import BRLSMASCATestSolver
from ..solver.BSCASMA_numba_v2 import BRLSMASCATestNumbaSolver
from ..solver.BSMA import BSMASolver
from ..solver.BSMA_numba_v2 import BSMANumbaSolver
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
        "brlsmasca_numba": lambda: BRLSMASCATestNumbaSolver(),
    }
