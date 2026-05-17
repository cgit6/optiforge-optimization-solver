from __future__ import annotations

import numpy as np
import pytest

from mkp.problem import MKPProblem, TSPProblem, buildProblemRegistry, problemBuilders
from mkp.problem.registry import ProblemRegistry, ProblemTypeSpec


def test_problem_builders_registry_lists_mkp_and_tsp() -> None:
    registry = buildProblemRegistry(problemBuilders())

    assert registry.get("mkp").encoding == "binary"
    assert registry.get("tsp").direction == "min"
    assert registry.list_problem_types() == ("mkp", "tsp")


def test_problem_registry_rejects_duplicate_problem_type() -> None:
    registry = ProblemRegistry()
    spec = ProblemTypeSpec(
        problem_type="demo",
        encoding="binary",
        direction="max",
        model_type=MKPProblem,
        loader=lambda data, dataset, problem_id, path: MKPProblem(
            problem_id=problem_id,
            dataset=dataset,
            items=1,
            dim=1,
            best_known=1,
            values=np.array([1]),
            weights=np.array([[1]]),
            capacities=np.array([1]),
        ),
        yaml_required_fields=("problem_id",),
        make_shm_pack=lambda model, shm_blocks: None,  # type: ignore[return-value]
        attach_shm_pack=lambda pack, shm_blocks: None,  # type: ignore[return-value]
    )

    registry.register(spec)

    try:
        registry.register(spec)
    except ValueError as exc:
        assert "already registered" in str(exc)
    else:
        raise AssertionError("duplicate problem type was accepted")


def test_problem_registry_rejects_non_problem_model_type() -> None:
    registry = ProblemRegistry()
    with pytest.raises(TypeError, match="model_type must inherit Problem"):
        registry.register(
            ProblemTypeSpec(
                problem_type="bad",
                encoding="binary",
                direction="max",
                model_type=object,  # type: ignore[arg-type]
                loader=lambda data, dataset, problem_id, path: None,  # type: ignore[return-value]
                yaml_required_fields=(),
                make_shm_pack=lambda model, shm_blocks: None,  # type: ignore[return-value]
                attach_shm_pack=lambda pack, shm_blocks: None,  # type: ignore[return-value]
            )
        )


def test_mkp_problem_fitness_and_constraint_methods() -> None:
    problem = MKPProblem(
        problem_id="p1",
        dataset="D",
        items=3,
        dim=2,
        best_known=60,
        values=np.array([10, 20, 30]),
        weights=np.array([[2, 1], [3, 2], [4, 3]]),
        capacities=np.array([5, 4]),
    )

    assert problem.fitness(np.array([1, 1, 0])) == 30
    assert problem.violates_constraints(np.array([1, 1, 0])) is False
    assert problem.violates_constraints(np.array([1, 1, 1])) is True


def test_tsp_problem_fitness_and_constraint_methods() -> None:
    problem = TSPProblem(
        problem_id="tsp5",
        dataset="SMALL",
        n_cities=5,
        best_known=26,
        distance_matrix=np.array(
            [
                [0, 2, 9, 10, 7],
                [2, 0, 6, 4, 3],
                [9, 6, 0, 8, 5],
                [10, 4, 8, 0, 6],
                [7, 3, 5, 6, 0],
            ]
        ),
    )

    assert problem.fitness(np.array([0, 1, 3, 2, 4])) == 26
    assert problem.violates_constraints(np.array([0, 1, 3, 2, 4])) is False
    assert problem.violates_constraints(np.array([0, 1, 1, 2, 4])) is True
