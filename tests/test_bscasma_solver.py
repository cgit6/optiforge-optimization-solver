from __future__ import annotations

import numpy as np
import pytest

from mkp.engine.models import ProblemModel
from mkp.solver.BSCASMA import BRLSMASCATestSolver
from mkp.solver.registry import SolverRegistry


def _build_problem(*, best_known: int = 4554) -> ProblemModel:
    """以 WEISH01 真實題目作為 unit test 基底。

    BSCASMA test 版在 S=0（族群 fitness 全等）時 update_sma_weight 會除以 0 → NaN，
    這是 old/BSCASMA.py 的已知 bug（註解說要加 1e-8 但實作沒加），bit-identical
    fidelity 下不能修；故 unit test 改用 WEISH01 規模（30 items, 5 dims）以避免在
    第 0 個 iter 觸發此 bug。
    """
    from pathlib import Path

    from mkp.engine.repository import ProblemRepository

    repo_root = Path(__file__).resolve().parents[1]
    repository = ProblemRepository(config_root=repo_root / "configs/problems")
    problem = repository.load("WEISH", "weish01")
    if best_known == problem.best_known:
        return problem
    return ProblemModel(
        problem_id=problem.problem_id,
        dataset=problem.dataset,
        items=problem.items,
        dim=problem.dim,
        values=problem.values,
        weights=problem.weights,
        capacities=problem.capacities,
        best_known=best_known,
    )


def _build_config(max_iterations: int = 60) -> dict:
    return {
        "solver_id": "brlsmasca",
        "solver_class": "BRLSMASCATestSolver",
        "stop_condition": {"type": "max_iterations", "max_iterations": max_iterations},
        "params": {},
    }


def test_bscasma_solver_can_be_created_by_registry():
    registry = SolverRegistry()
    registry.register(
        "brlsmasca",
        lambda: BRLSMASCATestSolver(),
    )
    solver = registry.create("brlsmasca")
    assert isinstance(solver, BRLSMASCATestSolver)


def test_bscasma_solver_returns_valid_solve_result():
    solver = BRLSMASCATestSolver()
    problem = _build_problem(best_known=10**9)  # 確保不會早停，全程跑滿 max_iter
    rng = np.random.default_rng(123)
    result = solver.solve(problem, _build_config(max_iterations=20), rng)

    assert result.problem_id == "weish01"
    assert result.solver_id == "brlsmasca"
    assert result.stop_reason in {"max_iterations_reached", "best_known_reached"}
    assert result.evaluation_count >= 20
    assert result.best_solution.shape == (problem.items,)


def test_bscasma_reproducibility_same_seed_same_result():
    solver = BRLSMASCATestSolver()
    problem = _build_problem(best_known=10**9)
    config = _build_config(max_iterations=20)

    result_a = solver.solve(problem, config, np.random.default_rng(999))
    result_b = solver.solve(problem, config, np.random.default_rng(999))

    assert result_a.seed == result_b.seed
    assert result_a.best_objective == result_b.best_objective
    assert np.array_equal(result_a.best_solution, result_b.best_solution)


def test_bscasma_reproducibility_different_seed_can_differ():
    solver = BRLSMASCATestSolver()
    problem = _build_problem(best_known=10**9)
    config = _build_config(max_iterations=20)

    result_a = solver.solve(problem, config, np.random.default_rng(100))
    result_b = solver.solve(problem, config, np.random.default_rng(200))

    assert result_a.seed != result_b.seed


def test_bscasma_stop_condition_max_iterations_reached():
    solver = BRLSMASCATestSolver()
    problem = _build_problem(best_known=10**9)
    config = _build_config(max_iterations=15)
    result = solver.solve(problem, config, np.random.default_rng(1234))

    assert result.stop_reason == "max_iterations_reached"
    assert result.evaluation_count >= 20


def test_bscasma_params_pop_size_from_config_affects_evaluation_count():
    solver = BRLSMASCATestSolver()
    problem = _build_problem(best_known=10**9)
    # 用較大 pop_size 降低 S=0 機率（avoid old NaN bug）
    pop_size = 20
    max_iter = 5
    config = {
        "solver_id": "brlsmasca",
        "solver_class": "BRLSMASCATestSolver",
        "stop_condition": {"type": "max_iterations", "max_iterations": max_iter},
        "params": {
            "pop_size": pop_size,
            "a": 2.0,
            "z": 0.03,
            "prob_arr": [0.04, 0.46, 0.25, 0.25],
        },
    }
    result = solver.solve(problem, config, np.random.default_rng(1))
    assert result.evaluation_count == pop_size + max_iter * pop_size


def test_bscasma_rejects_invalid_params():
    solver = BRLSMASCATestSolver()
    problem = _build_problem()
    rng = np.random.default_rng(1)
    base = {
        "solver_id": "brlsmasca",
        "solver_class": "BRLSMASCATestSolver",
        "stop_condition": {"type": "max_iterations", "max_iterations": 5},
    }

    with pytest.raises(ValueError, match="params.pop_size"):
        solver.solve(problem, {**base, "params": {"pop_size": 0}}, rng)

    with pytest.raises(ValueError, match="params.a"):
        solver.solve(problem, {**base, "params": {"a": 0}}, rng)

    with pytest.raises(ValueError, match="params.z"):
        solver.solve(problem, {**base, "params": {"z": 0.0}}, rng)

    with pytest.raises(ValueError, match="prob_arr"):
        solver.solve(
            problem,
            {**base, "params": {"prob_arr": [0.5, 0.5, 0.0]}},
            rng,
        )

    with pytest.raises(ValueError, match="non-negative"):
        solver.solve(
            problem,
            {**base, "params": {"prob_arr": [0.5, 0.5, 0.5, -0.5]}},
            rng,
        )
