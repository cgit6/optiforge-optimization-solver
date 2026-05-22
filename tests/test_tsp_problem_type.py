from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from mkp.cli.run import validate_execute_args
from mkp.engine.models import ExperimentSpec, SolveResult
from mkp.engine.repository import ProblemRepository
from mkp.problem import TSPProblem, buildProblemRegistry, problemBuilders


def _write_tsp(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
problem_id: tsp5
dataset: SMALL
problem_type: tsp
n_cities: 5
best_known: 26
distance_matrix:
  - [0, 2, 9, 10, 7]
  - [2, 0, 6, 4, 3]
  - [9, 6, 0, 8, 5]
  - [10, 4, 8, 0, 6]
  - [7, 3, 5, 6, 0]
""".strip(),
        encoding="utf-8",
    )


def _write_solver(path: Path, *, solver_id: str, problem_type: str, encoding: str, direction: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""
solver_id: {solver_id}
solver_class: Dummy
capabilities:
  problem_types: [{problem_type}]
  encodings: [{encoding}]
  directions: [{direction}]
stop_condition:
  type: max_iterations
  max_iterations: 20
  max_seconds: null
params:
  - {{}}
""".strip(),
        encoding="utf-8",
    )


def test_tsp_canonical_repository_loads_problem(tmp_path: Path) -> None:
    root = tmp_path / "problems"
    _write_tsp(root / "tsp" / "SMALL" / "tsp5.yaml")

    registry = buildProblemRegistry(problemBuilders())
    problem = ProblemRepository(root, registry=registry).load("SMALL", "tsp5", "tsp")

    assert isinstance(problem, TSPProblem)
    assert problem.problem_type == "tsp"
    assert problem.encoding == "permutation"
    assert problem.direction == "min"


def test_tsp_problem_validate_checks_permutation_and_cost() -> None:
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
    result = SolveResult(
        problem_id="tsp5",
        solver_id="tsp_solver",
        run_seed=0,
        best_solution=np.array([0, 1, 3, 2, 4]),
        best_objective=26,
        feasible=True,
        evaluation_count=5,
        stop_reason="done",
        runtime=0.0,
    )

    report = problem.validate(result)

    assert report.is_feasible is True
    assert report.objective_valid is True
    assert report.best_known_reached is True
    assert report.best_known_gap == 0


def test_compatibility_check_rejects_mkp_solver_for_tsp(tmp_path: Path) -> None:
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    _write_tsp(problem_root / "tsp" / "SMALL" / "tsp5.yaml")
    _write_solver(
        solver_root / "bsma.yaml",
        solver_id="bsma",
        problem_type="mkp",
        encoding="binary",
        direction="max",
    )
    spec = ExperimentSpec(
        experiment_name="bad",
        problem_type="tsp",
        dataset="SMALL",
        problem_ids=("tsp5",),
        solver_ids=("bsma",),
        repeat=1,
    )

    with pytest.raises(ValueError, match="incompatible"):
        validate_execute_args(spec, problem_root, solver_root)
