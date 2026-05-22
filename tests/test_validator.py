from __future__ import annotations

import numpy as np

from mkp.engine.models import SolveResult
from mkp.problem import ProblemModel
from mkp.problem.validation import best_known_status_and_gap, objective_values_equal


def _build_problem(*, best_known: int = 50) -> ProblemModel:
    return ProblemModel(
        problem_id="weish01",
        dataset="WEISH",
        items=3,
        dim=2,
        values=np.array([10, 20, 30]),
        weights=np.array([[2, 1], [3, 2], [4, 3]]),
        capacities=np.array([10, 8]),
        best_known=best_known,
    )


def _build_run_result(best_solution: np.ndarray, best_objective: int) -> SolveResult:
    return SolveResult(
        problem_id="weish01",
        solver_id="stub_solver",
        run_seed=42,
        best_solution=best_solution,
        best_objective=best_objective,
        feasible=True,
        evaluation_count=10,
        stop_reason="max_iterations_reached",
        runtime=0.1,
        linprog_runtime=0.0,
        error=None,
    )


def test_problem_validate_feasible_solution_passes():
    problem = _build_problem()
    solution = np.array([1, 1, 1])  # weights per dim: [9, 6]
    result = _build_run_result(best_solution=solution, best_objective=60)

    report = problem.validate(result)

    assert report.is_feasible is True
    assert report.feasibility_violations == ()


def test_problem_validate_detects_infeasible_solution_and_violated_dims():
    problem = _build_problem()
    solution = np.array([0, 0, 3])  # weights per dim: [12, 9]
    result = _build_run_result(best_solution=solution, best_objective=90)

    report = problem.validate(result)

    assert report.is_feasible is False
    assert report.feasibility_violations == (0,)


def test_problem_validate_detects_objective_mismatch():
    problem = _build_problem()
    solution = np.array([1, 0, 1])  # recomputed objective: 40
    result = _build_run_result(best_solution=solution, best_objective=41)

    report = problem.validate(result)

    assert report.recomputed_objective == 40
    assert report.objective_valid is False
    assert report.objective_mismatch is True


def test_problem_validate_best_known_status_and_gap():
    problem = _build_problem()

    reached_result = _build_run_result(best_solution=np.array([1, 1, 1]), best_objective=60)
    reached_report = problem.validate(reached_result)
    assert reached_report.best_known_reached is True
    assert reached_report.best_known_gap == -10

    not_reached_result = _build_run_result(best_solution=np.array([1, 0, 1]), best_objective=40)
    not_reached_report = problem.validate(not_reached_result)
    assert not_reached_report.best_known_reached is False
    assert not_reached_report.best_known_gap == 10


def test_objective_values_equal_uses_float_tolerance():
    assert objective_values_equal(1.0, 1.0 + 1e-10) is True
    assert objective_values_equal(1.0, 1.1) is False


def test_vector_objective_equality_and_best_known_gap():
    assert objective_values_equal((10, 2.0), (10, 2.0 + 1e-10)) is True
    assert objective_values_equal((10, 2), (10, 3)) is False

    reached, gap = best_known_status_and_gap(
        best_known=(10, 5),
        objective=(11, 4),
        direction=("max", "min"),
    )

    assert reached is True
    assert gap == (-1, -1)


def test_scalar_min_best_known_status_and_gap():
    reached, gap = best_known_status_and_gap(best_known=10, objective=9, direction="min")
    assert reached is True
    assert gap == -1

    reached, gap = best_known_status_and_gap(best_known=10, objective=12, direction="min")
    assert reached is False
    assert gap == 2
