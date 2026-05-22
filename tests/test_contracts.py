import numpy as np
import pytest

from mkp.engine.models import ExperimentSpec, SolveResult, RunTask
from mkp.problem import Problem, ProblemModel


def test_experiment_spec_valid():
    spec = ExperimentSpec(
        experiment_name="exp_001",
        dataset="WEISH",
        problem_ids=("weish01", "weish02"),
        solver_ids=("solver_a",),
        repeat=3,
        worker_count=2,
    )
    assert spec.repeat == 3
    assert spec.problem_ids == ("weish01", "weish02")
    assert spec.worker_count == 2


@pytest.mark.parametrize(
    "kwargs",
    [
        {"experiment_name": ""},
        {"dataset": ""},
        {"problem_ids": tuple()},
        {"solver_ids": tuple()},
        {"problem_ids": ("weish01", "weish01")},
        {"solver_ids": ("solver_a", "solver_a")},
        {"repeat": 0},
        {"worker_count": 0},
    ],
)
def test_experiment_spec_invalid(kwargs):
    base = dict(
        experiment_name="exp_001",
        dataset="WEISH",
        problem_ids=("weish01",),
        solver_ids=("solver_a",),
        repeat=1,
    )
    base.update(kwargs)
    with pytest.raises(ValueError):
        ExperimentSpec(**base)


def test_problem_model_valid_and_readonly_arrays():
    model = ProblemModel(
        problem_id="weish01",
        dataset="WEISH",
        items=3,
        dim=2,
        values=np.array([10, 20, 30]),
        weights=np.array([[1, 2], [3, 4], [5, 6]]),
        capacities=np.array([7, 8]),
        best_known=100,
    )
    assert model.weights.shape == (3, 2)
    assert model.values.flags.writeable is False
    assert model.weights.flags.writeable is False
    assert model.capacities.flags.writeable is False


def test_problem_model_invalid_shape():
    with pytest.raises(ValueError):
        ProblemModel(
            problem_id="weish01",
            dataset="WEISH",
            items=3,
            dim=2,
            values=np.array([10, 20]),
            weights=np.array([[1, 2], [3, 4], [5, 6]]),
            capacities=np.array([7, 8]),
            best_known=100,
        )


def test_run_task_valid():
    task = RunTask(
        problem_id="weish01",
        dataset="WEISH",
        solver_id="solver_a",
        repeat_index=0,
        task_seed=999,
        param_set_index=0,
    )
    assert task.task_seed == 999


@pytest.mark.parametrize(
    "kwargs",
    [
        {"problem_id": ""},
        {"dataset": ""},
        {"solver_id": ""},
        {"repeat_index": -1},
        {"task_seed": -1},
        {"param_set_index": -1},
    ],
)
def test_run_task_invalid(kwargs):
    base = dict(
        problem_id="weish01",
        dataset="WEISH",
        solver_id="solver_a",
        repeat_index=0,
        task_seed=1,
        param_set_index=0,
    )
    base.update(kwargs)
    with pytest.raises(ValueError):
        RunTask(**base)


def test_run_result_valid_and_readonly_solution():
    result = SolveResult(
        problem_id="weish01",
        solver_id="solver_a",
        run_seed=7,
        best_solution=np.array([1, 0, 1]),
        best_objective=123,
        feasible=True,
        evaluation_count=50,
        stop_reason="max_iterations_reached",
        runtime=0.25,
        linprog_runtime=0.01,
        error=None,
    )
    assert result.best_objective == 123
    assert result.linprog_runtime == 0.01
    assert result.best_solution.flags.writeable is False


def test_run_result_accepts_vector_objective():
    result = SolveResult(
        problem_id="multi01",
        solver_id="solver_a",
        run_seed=7,
        best_solution=np.array([1, 0, 1]),
        best_objective=(123, 4.5),
        feasible=True,
        evaluation_count=50,
        stop_reason="done",
        runtime=0.25,
    )

    assert result.best_objective == (123, 4.5)


def test_problem_requires_validate_implementation():
    class MissingValidateProblem(Problem):
        def fitness(self, solution: np.ndarray):
            return 0

        def violates_constraints(self, solution: np.ndarray) -> bool:
            return False

    with pytest.raises(TypeError):
        MissingValidateProblem(
            problem_id="p",
            dataset="D",
            best_known=None,
            problem_type="demo",
            encoding="continuous",
            direction="min",
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"problem_id": ""},
        {"solver_id": ""},
        {"run_seed": -1},
        {"evaluation_count": -1},
        {"runtime": -0.1},
        {"linprog_runtime": -0.01},
        {"stop_reason": ""},
    ],
)
def test_run_result_invalid(kwargs):
    base = dict(
        problem_id="weish01",
        solver_id="solver_a",
        run_seed=7,
        best_solution=np.array([1, 0, 1]),
        best_objective=123,
        feasible=True,
        evaluation_count=50,
        stop_reason="max_iterations_reached",
        runtime=0.25,
        linprog_runtime=0.0,
        error=None,
    )
    base.update(kwargs)
    with pytest.raises(ValueError):
        SolveResult(**base)
