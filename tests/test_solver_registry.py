from __future__ import annotations

import numpy as np
import pytest

from mkp.engine.models import ProblemModel
from mkp.solver.solver_registry import SolverRegistry, StubMaxIterationsSolver


def _build_problem() -> ProblemModel:
    return ProblemModel(
        problem_id="weish01",
        dataset="WEISH",
        items=3,
        dim=2,
        values=np.array([10, 20, 30]),
        weights=np.array([[1, 2], [3, 4], [5, 6]]),
        capacities=np.array([7, 8]),
        best_known=100,
    )


def test_registry_can_register_and_create_solver():
    registry = SolverRegistry()
    registry.register("stub_solver", lambda: StubMaxIterationsSolver())

    solver = registry.create("stub_solver")
    assert isinstance(solver, StubMaxIterationsSolver)


def test_registry_rejects_unregistered_solver():
    registry = SolverRegistry()
    with pytest.raises(KeyError, match="Solver is not registered"):
        registry.create("unknown_solver")


def test_stub_solver_returns_run_result_required_fields():
    solver = StubMaxIterationsSolver()
    problem = _build_problem()
    rng = np.random.default_rng(123)
    config = {
        "solver_id": "stub_solver",
        "stop_condition": {"type": "max_iterations", "max_iterations": 10},
        "params": {},
    }

    result = solver.solve(problem, config, rng)

    assert result.problem_id == "weish01"
    assert result.solver_id == "stub_solver"
    assert result.feasible is True
    assert result.evaluation_count == 10
    assert result.stop_reason == "max_iterations_reached"
    assert result.runtime >= 0
    assert result.error is None


def test_stub_solver_honors_max_iterations_stop_condition():
    solver = StubMaxIterationsSolver()
    problem = _build_problem()
    rng = np.random.default_rng(1)
    config = {
        "solver_id": "stub_solver",
        "stop_condition": {"type": "max_iterations", "max_iterations": 10},
        "params": {},
    }

    result = solver.solve(problem, config, rng)

    assert result.evaluation_count == 10
    assert result.stop_reason == "max_iterations_reached"
