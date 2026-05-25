from __future__ import annotations

import numpy as np
import pytest

from mkp.problem import ProblemModel
from mkp.solver.BSCASMA import BRLSMASCATestSolver
from mkp.solver.BSCASMA_rl_numba import BRLSMASCARLNumbaSolver
from mkp.solver.BSCASMA_test_numba import BRLSMASCATestNumbaSolver
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
    from mkp.problem import buildProblemRegistry, problemBuilders

    repo_root = Path(__file__).resolve().parents[1]
    repository = ProblemRepository(
        config_root=repo_root / "configs/problems",
        registry=buildProblemRegistry(problemBuilders()),
    )
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


def _build_numba_config(
    *,
    solver_id: str,
    solver_class: str,
    max_iterations: int = 20,
    params: dict | None = None,
) -> dict:
    return {
        "solver_id": solver_id,
        "solver_class": solver_class,
        "stop_condition": {"type": "max_iterations", "max_iterations": max_iterations},
        "params": params or {},
    }


def test_bscasma_solver_can_be_created_by_registry():
    registry = SolverRegistry()
    registry.register(
        "brlsmasca",
        lambda: BRLSMASCATestSolver(),
    )
    solver = registry.create("brlsmasca")
    assert isinstance(solver, BRLSMASCATestSolver)


def test_bscasma_numba_solvers_can_be_created_by_registry():
    registry = SolverRegistry()
    registry.register("brlsmasca_rl_numba", lambda: BRLSMASCARLNumbaSolver())
    registry.register("brlsmasca_test_numba", lambda: BRLSMASCATestNumbaSolver())

    assert isinstance(registry.create("brlsmasca_rl_numba"), BRLSMASCARLNumbaSolver)
    assert isinstance(registry.create("brlsmasca_test_numba"), BRLSMASCATestNumbaSolver)


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

    assert result_a.run_seed == result_b.run_seed
    assert result_a.best_objective == result_b.best_objective
    assert np.array_equal(result_a.best_solution, result_b.best_solution)


def test_bscasma_reproducibility_different_seed_can_differ():
    solver = BRLSMASCATestSolver()
    problem = _build_problem(best_known=10**9)
    config = _build_config(max_iterations=20)

    result_a = solver.solve(problem, config, np.random.default_rng(100))
    result_b = solver.solve(problem, config, np.random.default_rng(200))

    assert result_a.run_seed != result_b.run_seed


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


def test_bscasma_rl_numba_returns_valid_solve_result_and_metadata():
    solver = BRLSMASCARLNumbaSolver()
    problem = _build_problem(best_known=10**9)
    config = _build_numba_config(
        solver_id="brlsmasca_rl_numba",
        solver_class="BRLSMASCARLNumbaSolver",
        max_iterations=10,
        params={"pop_size": 20, "alpha": 0.1, "gamma": 0.9},
    )

    result = solver.solve(problem, config, np.random.default_rng(123))

    assert result.problem_id == "weish01"
    assert result.solver_id == "brlsmasca_rl_numba"
    assert result.stop_reason in {"max_iterations_reached", "best_known_reached"}
    assert result.best_solution.shape == (problem.items,)
    assert result.metadata["numba"] is True
    assert result.metadata["rl"] is True
    assert result.metadata["q_table_nonzero"] > 0
    assert sum(result.metadata["action_counts"]) > 0


def test_bscasma_rl_numba_reproducibility_same_seed_same_result():
    solver = BRLSMASCARLNumbaSolver()
    problem = _build_problem(best_known=10**9)
    config = _build_numba_config(
        solver_id="brlsmasca_rl_numba",
        solver_class="BRLSMASCARLNumbaSolver",
        max_iterations=10,
        params={"pop_size": 20},
    )

    result_a = solver.solve(problem, config, np.random.default_rng(999))
    result_b = solver.solve(problem, config, np.random.default_rng(999))

    assert result_a.run_seed == result_b.run_seed
    assert result_a.best_objective == result_b.best_objective
    assert np.array_equal(result_a.best_solution, result_b.best_solution)


def test_bscasma_test_numba_uses_new_solver_id():
    solver = BRLSMASCATestNumbaSolver()
    problem = _build_problem(best_known=10**9)
    config = _build_numba_config(
        solver_id="brlsmasca_test_numba",
        solver_class="BRLSMASCATestNumbaSolver",
        max_iterations=5,
        params={"pop_size": 20},
    )

    result = solver.solve(problem, config, np.random.default_rng(123))

    assert result.solver_id == "brlsmasca_test_numba"
    assert result.metadata["numba"] is True
    assert result.metadata["rl"] is False


def test_bscasma_rl_numba_rejects_invalid_params():
    solver = BRLSMASCARLNumbaSolver()
    problem = _build_problem()
    rng = np.random.default_rng(1)
    base = {
        "solver_id": "brlsmasca_rl_numba",
        "solver_class": "BRLSMASCARLNumbaSolver",
        "stop_condition": {"type": "max_iterations", "max_iterations": 5},
    }

    with pytest.raises(ValueError, match="params.pop_size"):
        solver.solve(problem, {**base, "params": {"pop_size": 2}}, rng)

    with pytest.raises(ValueError, match="params.a"):
        solver.solve(problem, {**base, "params": {"a": 0}}, rng)

    with pytest.raises(ValueError, match="params.z"):
        solver.solve(problem, {**base, "params": {"z": 0.0}}, rng)

    with pytest.raises(ValueError, match="params.alpha"):
        solver.solve(problem, {**base, "params": {"alpha": 0.0}}, rng)

    with pytest.raises(ValueError, match="params.gamma"):
        solver.solve(problem, {**base, "params": {"gamma": 1.5}}, rng)
