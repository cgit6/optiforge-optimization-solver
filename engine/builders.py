"""內建求解器建構子（可由 `build(..., solver_builders=...)` 覆寫）。"""

from __future__ import annotations

from ..solver.BSCA2 import BSCA2V120Solver
from ..solver.BSCA2_numby import BSCA2V120NumbaSolver
from ..solver.BSCASMA import BRLSMASCA2V100320050TestSolver
from ..solver.BSCASMA_numby import BRLSMASCA2V100320050TestNumbaSolver
from ..solver.BSMA import BSMASolver
from ..solver.BSMA_numby import BSMANumbaSolver
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
        "bsca2_v1_20": lambda: BSCA2V120Solver(),
        "bsca2_numba": lambda: BSCA2V120NumbaSolver(),
        "brlsmasca2_v1_003_20_050_test": lambda: BRLSMASCA2V100320050TestSolver(),
        "brlsmasca2_numba": lambda: BRLSMASCA2V100320050TestNumbaSolver(),
        "sma_mkp_modular_v1": lambda: SMAMKPModularV1Solver(),
        "sma_tsp_modular_v1": lambda: SMATSPModularV1Solver(),
        "nn_tsp_v1": lambda: NearestNeighborTSPSolver(),
    }
