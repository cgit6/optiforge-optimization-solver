from __future__ import annotations

import numpy as np
import pytest

from mkp.problem import ProblemModel
from mkp.solver.BSMA import BSMASolver
from mkp.solver.registry import SolverRegistry


def _build_problem(*, best_known: int = 34) -> ProblemModel:
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
        best_known=best_known,
    )


def _build_config(max_iterations: int = 60) -> dict:
    return {
        "solver_id": "bsma",
        "solver_class": "BSMASolver",
        "stop_condition": {"type": "max_iterations", "max_iterations": max_iterations},
        "params": {},
    }


def test_bsma_solver_can_be_created_by_registry():
    registry = SolverRegistry()
    registry.register("bsma", lambda: BSMASolver())
    solver = registry.create("bsma")
    assert isinstance(solver, BSMASolver)


def test_bsma_solver_returns_valid_run_result():
    solver = BSMASolver()
    problem = _build_problem()
    rng = np.random.default_rng(123)
    result = solver.solve(problem, _build_config(), rng)

    assert result.problem_id == "weish01"
    assert result.solver_id == "bsma"
    assert result.stop_reason == "max_iterations_reached"
    assert result.evaluation_count >= 20
    assert result.best_solution.shape == (problem.items,)


def test_bsma_reproducibility_same_seed_same_result():
    solver = BSMASolver()
    problem = _build_problem()
    config = _build_config()

    result_a = solver.solve(problem, config, np.random.default_rng(999))
    result_b = solver.solve(problem, config, np.random.default_rng(999))

    assert result_a.seed == result_b.seed
    assert result_a.best_objective == result_b.best_objective
    assert np.array_equal(result_a.best_solution, result_b.best_solution)


def test_bsma_reproducibility_different_seed_can_differ():
    solver = BSMASolver()
    problem = _build_problem()
    config = _build_config()

    result_a = solver.solve(problem, config, np.random.default_rng(100))
    result_b = solver.solve(problem, config, np.random.default_rng(200))

    assert result_a.seed != result_b.seed


def test_bsma_stop_condition_max_iterations_reached():
    solver = BSMASolver()
    problem = _build_problem()
    config = _build_config(max_iterations=10)
    result = solver.solve(problem, config, np.random.default_rng(1234))

    assert result.stop_reason == "max_iterations_reached"
    assert result.evaluation_count >= 20


def test_bsma_params_pop_size_from_config_affects_evaluation_count():
    """params.pop_size 與 stop_condition.max_iterations 一併決定 evaluation_count 上界公式。"""
    solver = BSMASolver()
    problem = _build_problem()
    pop_size = 7
    max_iter = 5
    config = {
        "solver_id": "bsma",
        "solver_class": "BSMASolver",
        "stop_condition": {"type": "max_iterations", "max_iterations": max_iter},
        "params": {"pop_size": pop_size, "z": 0.08},
    }
    result = solver.solve(problem, config, np.random.default_rng(1))
    assert result.evaluation_count == pop_size + max_iter * pop_size


def test_problem_model_rejects_unknown_best_known_before_bsma_runs():
    with pytest.raises(ValueError, match="best_known must be a positive integer"):
        _build_problem(best_known=None)  # type: ignore[arg-type]
