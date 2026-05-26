from __future__ import annotations

import numpy as np
import pytest

from mkp.problem import ProblemModel
from mkp.solver.BSCASMA import BRLSMASCATestSolver
from mkp.solver.BSCA_numba import BSCANumbaCore, _repair_bsca_row_inplace
from mkp.solver.BSMA_numba import BSMANumbaCore
from mkp.solver.BSCASMA_rl_numba import (
    BRLSMASCARLNumbaCore,
    BRLSMASCARLNumbaSolver,
    _copy_row_bits,
    _init_density_state,
    _population_density_from_counts,
    _repair_bscasma_row_inplace as _repair_bscasma_rl_row_inplace,
    _sort_bscasma_rl_desc_deterministic_inplace,
    _update_density_state_for_row,
)
from mkp.solver.BSCASMA_test_numba import (
    BRLSMASCATestNumbaCore,
    BRLSMASCATestNumbaSolver,
    _repair_bscasma_row_inplace as _repair_bscasma_test_row_inplace,
)
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
    assert "cp_list_cache_hit" in result.metadata
    assert result.metadata["z"] == 0.03
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


def test_bscasma_rl_numba_z_one_forces_global_action_gate():
    solver = BRLSMASCARLNumbaSolver()
    problem = _build_problem(best_known=10**9)
    config = _build_numba_config(
        solver_id="brlsmasca_rl_numba",
        solver_class="BRLSMASCARLNumbaSolver",
        max_iterations=5,
        params={"pop_size": 20, "z": 1.0},
    )

    result = solver.solve(problem, config, np.random.default_rng(321))

    action_counts = result.metadata["action_counts"]
    assert action_counts[0] > 0
    assert action_counts[1:] == [0, 0, 0]
    assert result.metadata["z"] == 1.0


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
    assert "cp_list_cache_hit" in result.metadata


def test_bscasma_test_numba_reproducibility_same_seed_same_result():
    solver = BRLSMASCATestNumbaSolver()
    problem = _build_problem(best_known=10**9)
    config = _build_numba_config(
        solver_id="brlsmasca_test_numba",
        solver_class="BRLSMASCATestNumbaSolver",
        max_iterations=10,
        params={"pop_size": 20},
    )

    result_a = solver.solve(problem, config, np.random.default_rng(999))
    result_b = solver.solve(problem, config, np.random.default_rng(999))

    assert result_a.run_seed == result_b.run_seed
    assert result_a.best_objective == result_b.best_objective
    assert np.array_equal(result_a.best_solution, result_b.best_solution)


def test_bscasma_rl_incremental_density_matches_full_density():
    pop_sol = np.array(
        [
            [1, 0, 1, 0, 1, 0],
            [0, 1, 1, 0, 0, 1],
            [1, 1, 0, 0, 1, 0],
            [0, 0, 0, 1, 1, 1],
        ],
        dtype=np.float64,
    )
    pop_size, items = pop_sol.shape
    ones_count = np.empty(items, dtype=np.int64)
    avg_bits = np.empty(items, dtype=np.float64)
    row_hamming = np.empty(pop_size, dtype=np.float64)
    sqrt_lookup = np.sqrt(np.arange(items + 1, dtype=np.float64))

    density_sum = _init_density_state(
        pop_sol, ones_count, avg_bits, row_hamming, sqrt_lookup, pop_size, items
    )
    full_density = _population_density_from_counts(pop_sol, ones_count, sqrt_lookup, pop_size, items)
    assert density_sum / (pop_size * items) == pytest.approx(full_density)

    old_row = np.empty(items, dtype=np.float64)
    _copy_row_bits(pop_sol, 1, old_row, items)
    pop_sol[1] = np.array([1, 1, 0, 1, 0, 0], dtype=np.float64)
    density_sum = _update_density_state_for_row(
        pop_sol,
        1,
        old_row,
        ones_count,
        avg_bits,
        row_hamming,
        density_sum,
        sqrt_lookup,
        pop_size,
        items,
    )

    check_ones = np.empty(items, dtype=np.int64)
    check_avg = np.empty(items, dtype=np.float64)
    check_hamming = np.empty(pop_size, dtype=np.float64)
    check_sum = _init_density_state(
        pop_sol, check_ones, check_avg, check_hamming, sqrt_lookup, pop_size, items
    )

    assert np.array_equal(ones_count, check_ones)
    assert np.array_equal(avg_bits, check_avg)
    assert np.array_equal(row_hamming, check_hamming)
    assert density_sum == pytest.approx(check_sum)

    pop_fit = np.array([10.0, 40.0, 20.0, 30.0], dtype=np.float64)
    individual_ids = np.arange(pop_size, dtype=np.int64)
    tmp_sol = np.empty_like(pop_sol)
    tmp_fit = np.empty_like(pop_fit)
    tmp_ids = np.empty_like(individual_ids)
    tmp_hamming = np.empty_like(row_hamming)
    idx_work = np.empty(pop_size, dtype=np.int64)
    _sort_bscasma_rl_desc_deterministic_inplace(
        pop_sol,
        pop_fit,
        individual_ids,
        row_hamming,
        tmp_sol,
        tmp_fit,
        tmp_ids,
        tmp_hamming,
        idx_work,
        pop_size,
        items,
    )
    sorted_ones = np.empty(items, dtype=np.int64)
    sorted_avg = np.empty(items, dtype=np.float64)
    sorted_hamming = np.empty(pop_size, dtype=np.float64)
    _init_density_state(pop_sol, sorted_ones, sorted_avg, sorted_hamming, sqrt_lookup, pop_size, items)
    assert np.array_equal(row_hamming, sorted_hamming)


def test_numba_cp_list_caches_are_per_solver_core():
    problem = _build_problem(best_known=10**9)
    core_specs = [
        (BSMANumbaCore, {"pop_size": 6, "z": 0.08, "max_iter": 2}),
        (BSCANumbaCore, {"pop_size": 6, "a": 1.5, "max_iter": 2}),
        (
            BRLSMASCARLNumbaCore,
            {"pop_size": 6, "a": 2.5, "z": 0.08, "max_iter": 2, "alpha": 0.1, "gamma": 0.9},
        ),
        (BRLSMASCATestNumbaCore, {"pop_size": 6, "a": 2.5, "max_iter": 2}),
    ]

    for core_cls, _ in core_specs:
        core_cls._cp_list_cache.clear()

    first_cp_lists = {}
    for core_cls, kwargs in core_specs:
        core = core_cls(
            problem.items,
            problem.dim,
            problem.best_known,
            problem.values,
            problem.weights,
            problem.capacities,
            seed=123,
            **kwargs,
        )
        assert core.cp_list_cache_hit is False
        assert len(core_cls._cp_list_cache) == 1
        first_cp_lists[core_cls] = core.cp_list.copy()

    for core_cls, kwargs in core_specs:
        core = core_cls(
            problem.items,
            problem.dim,
            problem.best_known,
            problem.values,
            problem.weights,
            problem.capacities,
            seed=123,
            **kwargs,
        )
        assert core.cp_list_cache_hit is True
        assert core.linprog_runtime == 0.0
        assert np.array_equal(core.cp_list, first_cp_lists[core_cls])


@pytest.mark.parametrize(
    "repair_func",
    [_repair_bscasma_rl_row_inplace, _repair_bscasma_test_row_inplace],
)
def test_bscasma_local_repair_matches_bsca_repair(repair_func):
    values = np.array([10, 7, 9, 6, 12, 4], dtype=np.int64)
    weights = np.array(
        [
            [4, 2],
            [3, 3],
            [5, 2],
            [2, 4],
            [6, 5],
            [1, 2],
        ],
        dtype=np.int64,
    )
    capacities = np.array([10, 8], dtype=np.int64)
    cp_list = np.array([4, 0, 2, 1, 3, 5], dtype=np.int64)
    pop_sol_ref = np.array([[1, 1, 1, 0, 1, 0]], dtype=np.float64)
    pop_sol_local = pop_sol_ref.copy()
    pop_fit_ref = np.array([0.0], dtype=np.float64)
    pop_fit_local = np.array([0.0], dtype=np.float64)
    resource_ref = np.zeros(2, dtype=np.float64)
    resource_local = np.zeros(2, dtype=np.float64)

    _repair_bsca_row_inplace(
        pop_sol_ref,
        0,
        pop_fit_ref,
        values,
        weights,
        capacities,
        cp_list,
        resource_ref,
        values.size,
        capacities.size,
    )
    repair_func(
        pop_sol_local,
        0,
        pop_fit_local,
        values,
        weights,
        capacities,
        cp_list,
        resource_local,
        values.size,
        capacities.size,
    )

    assert np.array_equal(pop_sol_local, pop_sol_ref)
    assert pop_fit_local[0] == pytest.approx(pop_fit_ref[0])


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
