"""內建求解器建構子（可由 `build(..., solver_builders=...)` 覆寫）。"""

from __future__ import annotations

from ..solver.BSCA import BSCASolver
from ..solver.BSCA_numba import BSCANumbaSolver
from ..solver.BSCASMA import BRLSMASCATestSolver
from ..solver.BSCASMA_numba import BRLSMASCATestNumbaSolver
from ..solver.BSMA import BSMASolver
from ..solver.BSMA_numba import BSMANumbaSolver
from ..solver.nearest_neighbor_tsp import NearestNeighborTSPSolver
from ..solver.registry import SolverBuilder, StubMaxIterationsSolver
from ..solver.sma_mkp_modular import SMAMKPModularV1Solver
from ..solver.sma_tsp_modular import SMATSPModularV1Solver


# 註冊新求解
def default_solver_builders() -> dict[str, SolverBuilder]:
    return {
        "stub_solver": lambda: StubMaxIterationsSolver(),
        "bsma": lambda: BSMASolver(),
        "bsma_numba": lambda: BSMANumbaSolver(),
        "bsca": lambda: BSCASolver(),
        "bsca_numba": lambda: BSCANumbaSolver(),
        "brlsmasca": lambda: BRLSMASCATestSolver(),
        "brlsmasca_numba": lambda: BRLSMASCATestNumbaSolver(),
        "sma_mkp_modular_v1": lambda: SMAMKPModularV1Solver(),
        "sma_tsp_modular_v1": lambda: SMATSPModularV1Solver(),
        "nn_tsp_v1": lambda: NearestNeighborTSPSolver(),
    }
