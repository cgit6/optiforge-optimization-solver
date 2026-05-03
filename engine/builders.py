"""內建求解器建構子（可由 `build(..., solver_builders=...)` 覆寫）。"""

from __future__ import annotations

from ..solver.BSCA2 import BSCA2V120Solver
from ..solver.BSCASMA import BRLSMASCA2V100320050TestSolver
from ..solver.BSMA import BSMAV1008Solver
from ..solver.nearest_neighbor_tsp import NearestNeighborTSPSolver
from ..solver.registry import SolverBuilder, StubMaxIterationsSolver
from ..solver.sma_mkp_modular import SMAMKPModularV1Solver
from ..solver.sma_tsp_modular import SMATSPModularV1Solver


def default_solver_builders() -> dict[str, SolverBuilder]:
    return {
        "stub_solver": lambda: StubMaxIterationsSolver(),
        "bsma_v1_008": lambda: BSMAV1008Solver(),
        "bsca2_v1_20": lambda: BSCA2V120Solver(),
        "brlsmasca2_v1_003_20_050_test": lambda: BRLSMASCA2V100320050TestSolver(),
        "sma_mkp_modular_v1": lambda: SMAMKPModularV1Solver(),
        "sma_tsp_modular_v1": lambda: SMATSPModularV1Solver(),
        "nn_tsp_v1": lambda: NearestNeighborTSPSolver(),
    }
