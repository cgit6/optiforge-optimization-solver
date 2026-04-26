from __future__ import annotations

import numpy as np

from mkp.engine.contracts import ProblemModel
from mkp.solver.bsma_v1_008_solver import BSMAV1008Solver
from mkp.solver.solver_registry import SolverRegistry


def _build_problem() -> ProblemModel:
    return ProblemModel(
        problem_id="weish01",
        dataset="WEISH",
        items=6,
        dim=2,
        values=np.array([20, 18, 14, 10, 8, 7]),
        weights=np.array(
            [
                [7, 3],
                [6, 5],
                [5, 4],
                [3, 2],
                [2, 3],
                [1, 2],
            ]
        ),
        capacities=np.array([14, 11]),
        best_known=34,
    )


def _build_config(max_iterations: int = 60) -> dict:
    return {
        "solver_id": "bsma_v1_008",
        "solver_class": "BSMAV1008Solver",
        "stop_condition": {"type": "max_iterations", "max_iterations": max_iterations},
        "params": {},
    }


def test_bsma_solver_can_be_created_by_registry():
    registry = SolverRegistry()
    registry.register("bsma_v1_008", lambda: BSMAV1008Solver())
    solver = registry.create("bsma_v1_008")
    assert isinstance(solver, BSMAV1008Solver)


def test_bsma_solver_returns_valid_run_result():
    solver = BSMAV1008Solver()
    problem = _build_problem()
    rng = np.random.default_rng(123)
    result = solver.solve(problem, _build_config(), rng)

    assert result.problem_id == "weish01"
    assert result.solver_id == "bsma_v1_008"
    assert result.stop_reason == "max_iterations_reached"
    assert result.evaluation_count >= 20
    assert result.best_solution.shape == (problem.items,)


def test_bsma_reproducibility_same_seed_same_result():
    solver = BSMAV1008Solver()
    problem = _build_problem()
    config = _build_config()

    result_a = solver.solve(problem, config, np.random.default_rng(999))
    result_b = solver.solve(problem, config, np.random.default_rng(999))

    assert result_a.seed == result_b.seed
    assert result_a.best_objective == result_b.best_objective
    assert np.array_equal(result_a.best_solution, result_b.best_solution)


def test_bsma_reproducibility_different_seed_can_differ():
    solver = BSMAV1008Solver()
    problem = _build_problem()
    config = _build_config()

    result_a = solver.solve(problem, config, np.random.default_rng(100))
    result_b = solver.solve(problem, config, np.random.default_rng(200))

    assert result_a.seed != result_b.seed


def test_bsma_stop_condition_max_iterations_reached():
    solver = BSMAV1008Solver()
    problem = _build_problem()
    config = _build_config(max_iterations=10)
    result = solver.solve(problem, config, np.random.default_rng(1234))

    assert result.stop_reason == "max_iterations_reached"
    assert result.evaluation_count >= 20
