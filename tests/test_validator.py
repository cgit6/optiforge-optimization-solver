from __future__ import annotations

import numpy as np

from mkp.contracts import ProblemModel, RunResult
from mkp.validator import Validator


def _build_problem() -> ProblemModel:
    return ProblemModel(
        problem_id="weish01",
        dataset="WEISH",
        items=3,
        dim=2,
        values=np.array([10, 20, 30]),
        weights=np.array([[2, 1], [3, 2], [4, 3]]),
        capacities=np.array([10, 8]),
        best_known=50,
    )


def _build_run_result(best_solution: np.ndarray, best_objective: int) -> RunResult:
    return RunResult(
        problem_id="weish01",
        solver_id="stub_solver",
        repeat_index=0,
        seed=42,
        best_solution=best_solution,
        best_objective=best_objective,
        feasible=True,
        evaluation_count=10,
        stop_reason="max_iterations_reached",
        runtime=0.1,
        error=None,
    )


def test_validator_feasible_solution_passes():
    validator = Validator()
    problem = _build_problem()
    solution = np.array([1, 1, 1])  # weights per dim: [9, 6]
    result = _build_run_result(best_solution=solution, best_objective=60)

    report = validator.validate(problem, result)

    assert report.is_feasible is True
    assert report.feasibility_violations == ()


def test_validator_detects_infeasible_solution_and_violated_dims():
    validator = Validator()
    problem = _build_problem()
    solution = np.array([0, 0, 3])  # weights per dim: [12, 9]
    result = _build_run_result(best_solution=solution, best_objective=90)

    report = validator.validate(problem, result)

    assert report.is_feasible is False
    assert report.feasibility_violations == (0, 1)


def test_validator_detects_objective_mismatch():
    validator = Validator()
    problem = _build_problem()
    solution = np.array([1, 0, 1])  # recomputed objective: 40
    result = _build_run_result(best_solution=solution, best_objective=41)

    report = validator.validate(problem, result)

    assert report.recomputed_objective == 40
    assert report.objective_valid is False
    assert report.objective_mismatch is True


def test_validator_best_known_status_and_gap():
    validator = Validator()
    problem = _build_problem()

    reached_result = _build_run_result(best_solution=np.array([1, 1, 1]), best_objective=60)
    reached_report = validator.validate(problem, reached_result)
    assert reached_report.best_known_reached is True
    assert reached_report.best_known_gap == -10

    not_reached_result = _build_run_result(best_solution=np.array([1, 0, 1]), best_objective=40)
    not_reached_report = validator.validate(problem, not_reached_result)
    assert not_reached_report.best_known_reached is False
    assert not_reached_report.best_known_gap == 10
