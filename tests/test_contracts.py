from pathlib import Path

import numpy as np
import pytest

from mkp.contracts import ExperimentSpec, ProblemModel, RunResult, RunTask


def test_experiment_spec_valid():
    spec = ExperimentSpec(
        experiment_id="exp_001",
        dataset="WEISH",
        problem_ids=("weish01", "weish02"),
        solver_ids=("solver_a",),
        repeat=3,
        base_seed=42,
        output_dir=Path("mkp/output/exp_001"),
        benchmark_enabled=True,
    )
    assert spec.repeat == 3
    assert spec.problem_ids == ("weish01", "weish02")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"experiment_id": ""},
        {"dataset": ""},
        {"problem_ids": tuple()},
        {"solver_ids": tuple()},
        {"repeat": 0},
    ],
)
def test_experiment_spec_invalid(kwargs):
    base = dict(
        experiment_id="exp_001",
        dataset="WEISH",
        problem_ids=("weish01",),
        solver_ids=("solver_a",),
        repeat=1,
        base_seed=1,
        output_dir=Path("mkp/output/exp_001"),
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
        seed=999,
    )
    assert task.seed == 999


@pytest.mark.parametrize(
    "kwargs",
    [
        {"problem_id": ""},
        {"dataset": ""},
        {"solver_id": ""},
        {"repeat_index": -1},
        {"seed": -1},
    ],
)
def test_run_task_invalid(kwargs):
    base = dict(
        problem_id="weish01",
        dataset="WEISH",
        solver_id="solver_a",
        repeat_index=0,
        seed=1,
    )
    base.update(kwargs)
    with pytest.raises(ValueError):
        RunTask(**base)


def test_run_result_valid_and_readonly_solution():
    result = RunResult(
        problem_id="weish01",
        solver_id="solver_a",
        repeat_index=0,
        seed=7,
        best_solution=np.array([1, 0, 1]),
        best_objective=123,
        feasible=True,
        evaluation_count=50,
        stop_reason="max_iterations_reached",
        runtime=0.25,
        error=None,
    )
    assert result.best_objective == 123
    assert result.best_solution.flags.writeable is False


@pytest.mark.parametrize(
    "kwargs",
    [
        {"problem_id": ""},
        {"solver_id": ""},
        {"repeat_index": -1},
        {"seed": -1},
        {"evaluation_count": -1},
        {"runtime": -0.1},
        {"stop_reason": ""},
    ],
)
def test_run_result_invalid(kwargs):
    base = dict(
        problem_id="weish01",
        solver_id="solver_a",
        repeat_index=0,
        seed=7,
        best_solution=np.array([1, 0, 1]),
        best_objective=123,
        feasible=True,
        evaluation_count=50,
        stop_reason="max_iterations_reached",
        runtime=0.25,
        error=None,
    )
    base.update(kwargs)
    with pytest.raises(ValueError):
        RunResult(**base)
