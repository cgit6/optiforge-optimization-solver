from __future__ import annotations

import numpy as np
import pytest

from mkp.problem import ProblemModel
from mkp.solver.BSCASMA import BRLSMASCATestSolver
from mkp.solver.BSCA_numba import BSCANumbaCore, _repair_bsca_row_inplace
from mkp.solver.BSMA_numba import BSMANumbaCore
from mkp.solver.BSCASMA_rl_rc_numba import (
    BRLSMASCARLRCNumbaCore,
    BRLSMASCARLRCNumbaSolver,
    _archive_add_vector,
    _build_core_score_cp_payload,
    _build_freq_gated_v2_payload,
    _build_lp_rc_item_eval_payload,
    _dual_efficiency_fallback,
    _guided_probability,
    _local_search_bscasma_row_inplace,
    _path_relink_bscasma_inplace,
    _repair_bscasma_row_inplace as _repair_bscasma_rl_rc_row_inplace,
    _repair_bscasma_row_v2_inplace,
    _shuffle_efficiency_groups,
)
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
    registry.register("brlsmasca_rl_rc_numba", lambda: BRLSMASCARLRCNumbaSolver())
    registry.register("brlsmasca_test_numba", lambda: BRLSMASCATestNumbaSolver())

    assert isinstance(registry.create("brlsmasca_rl_numba"), BRLSMASCARLNumbaSolver)
    assert isinstance(registry.create("brlsmasca_rl_rc_numba"), BRLSMASCARLRCNumbaSolver)
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


def test_bscasma_rl_rc_numba_returns_valid_solve_result_and_metadata():
    BRLSMASCARLRCNumbaCore._cp_list_cache.clear()
    solver = BRLSMASCARLRCNumbaSolver()
    problem = _build_problem(best_known=10**9)
    config = _build_numba_config(
        solver_id="brlsmasca_rl_rc_numba",
        solver_class="BRLSMASCARLRCNumbaSolver",
        max_iterations=10,
        params={"pop_size": 20, "alpha": 0.1, "gamma": 0.9, "eval_group_decimals": 1},
    )

    result = solver.solve(problem, config, np.random.default_rng(123))

    assert result.problem_id == "weish01"
    assert result.solver_id == "brlsmasca_rl_rc_numba"
    assert result.stop_reason in {"max_iterations_reached", "best_known_reached"}
    assert result.best_solution.shape == (problem.items,)
    assert result.metadata["numba"] is True
    assert result.metadata["rl"] is True
    assert result.metadata["item_eval_method"] == "lp_rc_ordered"
    assert result.metadata["item_eval_fallback"] is False
    assert result.metadata["eval_group_decimals"] == 1
    assert result.metadata["eval_group_shuffle"] is False
    assert result.metadata["repair_passes"] == 1
    assert result.metadata["repair_swap_limit"] == 0
    assert result.metadata["repair_swap_accepts"] == 0
    assert result.metadata["mixed_init_enabled"] is False
    assert result.metadata["restart_enabled"] is False
    assert result.metadata["restart_window"] == 40
    assert result.metadata["restart_ratio"] == 0.25
    assert result.metadata["restart_count"] == 0
    assert result.metadata["restart_rows"] == 0
    assert result.metadata["guided_binary_enabled"] is False
    assert result.metadata["local_search_enabled"] is False
    assert result.metadata["archive_pr_enabled"] is False
    assert result.metadata["local_search_calls"] == 0
    assert result.metadata["local_search_moves"] == 0
    assert result.metadata["local_search_improvements"] == 0
    assert result.metadata["ls_obj_evals"] == 0
    assert result.metadata["archive_size"] == 8
    assert result.metadata["pr_calls"] == 0
    assert result.metadata["pr_steps"] == 0
    assert result.metadata["pr_improvements"] == 0
    assert result.metadata["total_obj_eval_count"] == result.evaluation_count
    assert isinstance(result.metadata["lp_fractional_count"], int)
    assert isinstance(result.metadata["eff_group_count"], int)
    assert "cp_list_cache_hit" in result.metadata
    assert sum(result.metadata["action_counts"]) > 0


def test_bscasma_rl_rc_numba_reproducibility_same_seed_same_result():
    BRLSMASCARLRCNumbaCore._cp_list_cache.clear()
    solver = BRLSMASCARLRCNumbaSolver()
    problem = _build_problem(best_known=10**9)
    config = _build_numba_config(
        solver_id="brlsmasca_rl_rc_numba",
        solver_class="BRLSMASCARLRCNumbaSolver",
        max_iterations=10,
        params={"pop_size": 20},
    )

    result_a = solver.solve(problem, config, np.random.default_rng(999))
    result_b = solver.solve(problem, config, np.random.default_rng(999))

    assert result_a.run_seed == result_b.run_seed
    assert result_a.best_objective == result_b.best_objective
    assert np.array_equal(result_a.best_solution, result_b.best_solution)


def test_bscasma_rl_rc_numba_cp_list_is_complete_permutation():
    BRLSMASCARLRCNumbaCore._cp_list_cache.clear()
    problem = _build_problem(best_known=10**9)
    np.random.seed(123)

    core = BRLSMASCARLRCNumbaCore(
        problem.items,
        problem.dim,
        problem.best_known,
        problem.values,
        problem.weights,
        problem.capacities,
        seed=123,
        pop_size=20,
        a=2.0,
        z=0.03,
        max_iter=1,
        alpha=0.1,
        gamma=0.9,
    )

    assert np.array_equal(np.sort(core.cp_list), np.arange(problem.items))
    assert core.item_eval_payload["base_order"].shape == (problem.items,)
    assert core.item_eval_fallback is False


def test_bscasma_rl_rc_core_score_cp_payload_builds_complete_order():
    problem = _build_problem(best_known=10**9)
    base_payload = _build_lp_rc_item_eval_payload(
        problem.values,
        problem.weights,
        problem.capacities,
        eval_group_decimals=1,
        eval_rc_eps=1.0e-9,
        eval_x_eps=1.0e-9,
    )

    payload = _build_core_score_cp_payload(
        base_payload,
        core_w_x_lp=0.40,
        core_w_rc=0.25,
        core_w_eff=0.20,
        core_w_bucket=0.15,
    )

    assert payload["item_eval_method"] == "core_score_cp"
    assert np.array_equal(np.sort(payload["cp_list"]), np.arange(problem.items))
    assert payload["core_score"].shape == (problem.items,)
    assert np.all(np.isfinite(payload["core_score"]))


def test_bscasma_rl_rc_freq_gated_v2_payload_is_reproducible_with_seed():
    problem = _build_problem(best_known=10**9)
    base_payload = _build_lp_rc_item_eval_payload(
        problem.values,
        problem.weights,
        problem.capacities,
        eval_group_decimals=1,
        eval_rc_eps=1.0e-9,
        eval_x_eps=1.0e-9,
    )
    kwargs = {
        "core_w_x_lp": 0.40,
        "core_w_rc": 0.25,
        "core_w_eff": 0.20,
        "core_w_bucket": 0.15,
        "eval_group_decimals": 1,
        "eval_rc_eps": 1.0e-9,
        "eval_x_eps": 1.0e-9,
        "freq_cp_noise": 0.03,
        "freq_elite_ratio": 0.995,
        "freq_quality_power": 4.0,
        "freq_samples_dim5": 2,
        "freq_samples_dim10": 2,
        "freq_samples_dim30": 2,
        "freq_blend_rho_dim5": 0.50,
        "freq_blend_rho_dim10": 0.70,
        "freq_blend_rho_dim30": 0.75,
        "freq_gate_probe_margin": 0.0002,
        "freq_gate_min_elites": 1,
        "freq_gate_min_std": 0.0,
        "freq_gate_min_topk_overlap": 0.0,
        "repair_passes": 1,
        "repair_swap_limit": 0,
    }

    payload_a = _build_freq_gated_v2_payload(
        problem.values,
        problem.weights,
        problem.capacities,
        base_payload,
        np.random.default_rng(123),
        **kwargs,
    )
    payload_b = _build_freq_gated_v2_payload(
        problem.values,
        problem.weights,
        problem.capacities,
        base_payload,
        np.random.default_rng(123),
        **kwargs,
    )

    assert np.array_equal(payload_a["cp_list"], payload_b["cp_list"])
    assert np.array_equal(np.sort(payload_a["cp_list"]), np.arange(problem.items))
    assert payload_a["freq_samples"] == 2
    assert "freq_fallback" in payload_a


@pytest.mark.parametrize(
    "method",
    [
        "core_score_cp",
        "freq_cp",
        "freq_cp_gbc",
        "elite_freq_cp",
        "elite_freq_gated",
        "freq_gated",
        "freq_gated_v2",
        "freq_gated_v2_gbc",
        "sbl_lite_cp",
        "score_cnd_rank",
        "score_dual_weight",
        "score_rc_rank",
        "score_hyb_weight",
        "score_lag_rank",
    ],
)
def test_bscasma_rl_rc_item_eval_methods_solve_and_report_metadata(method: str):
    solver = BRLSMASCARLRCNumbaSolver()
    problem = _build_problem(best_known=10**9)
    params = {
        "pop_size": 8,
        "item_eval_method": method,
        "freq_samples_dim5": 2,
        "freq_samples_dim10": 2,
        "freq_samples_dim30": 2,
        "sbl_candidate_limit": 2,
    }
    config = _build_numba_config(
        solver_id="brlsmasca_rl_rc_numba",
        solver_class="BRLSMASCARLRCNumbaSolver",
        max_iterations=3,
        params=params,
    )

    result = solver.solve(problem, config, np.random.default_rng(123))

    assert set(result.best_solution.tolist()) <= {0, 1}
    assert np.all(result.best_solution @ problem.weights <= problem.capacities)
    assert result.metadata["requested_item_eval_method"] == method
    if method == "core_score_cp":
        assert result.metadata["item_eval_method"] == "core_score_cp"
    if method.endswith("_gbc") or method.endswith("_weight"):
        assert result.metadata["guided_binary_enabled"] is True


def test_bscasma_rl_rc_numba_default_cp_list_is_ordered_and_seed_independent():
    BRLSMASCARLRCNumbaCore._cp_list_cache.clear()
    problem = _build_problem(best_known=10**9)

    core_a = BRLSMASCARLRCNumbaCore(
        problem.items,
        problem.dim,
        problem.best_known,
        problem.values,
        problem.weights,
        problem.capacities,
        seed=111,
        pop_size=20,
        a=2.0,
        z=0.03,
        max_iter=1,
        alpha=0.1,
        gamma=0.9,
    )
    core_b = BRLSMASCARLRCNumbaCore(
        problem.items,
        problem.dim,
        problem.best_known,
        problem.values,
        problem.weights,
        problem.capacities,
        seed=222,
        pop_size=20,
        a=2.0,
        z=0.03,
        max_iter=1,
        alpha=0.1,
        gamma=0.9,
    )

    assert core_a.eval_group_shuffle is False
    assert core_a.item_eval_method == "lp_rc_ordered"
    assert np.array_equal(core_a.cp_list, core_a.item_eval_payload["base_order"])
    assert np.array_equal(core_a.cp_list, core_b.cp_list)


def test_bscasma_rl_rc_dual_price_matches_legacy_dual_formulation():
    problem = _build_problem(best_known=10**9)

    payload = _build_lp_rc_item_eval_payload(
        problem.values,
        problem.weights,
        problem.capacities,
        eval_group_decimals=1,
        eval_rc_eps=1.0e-9,
        eval_x_eps=1.0e-9,
    )
    legacy = _dual_efficiency_fallback(
        problem.values,
        problem.weights,
        problem.capacities,
        eval_group_decimals=1,
    )

    assert payload["fallback"] is False
    assert np.allclose(payload["dual_price"], legacy["dual_price"], rtol=1.0e-7, atol=1.0e-7)
    assert payload["lp_fractional_count"] > 0


def test_bscasma_rl_rc_group_shuffle_is_seeded_and_stays_inside_groups():
    base_order = np.array([0, 1, 2, 3, 4, 5, 6, 7], dtype=np.int64)
    bucket = np.array([0, 0, 0, 0, 1, 1, 1, 2], dtype=np.int64)
    rounded_efficiency = np.array([1.0, 1.0, 1.0, 1.0, 0.5, 0.5, 0.5, 0.1], dtype=np.float64)

    np.random.seed(10)
    shuffled_a, group_count_a = _shuffle_efficiency_groups(base_order, bucket, rounded_efficiency)
    np.random.seed(10)
    shuffled_b, group_count_b = _shuffle_efficiency_groups(base_order, bucket, rounded_efficiency)

    different_seed_can_differ = False
    for seed in range(11, 30):
        np.random.seed(seed)
        shuffled_c, _ = _shuffle_efficiency_groups(base_order, bucket, rounded_efficiency)
        if not np.array_equal(shuffled_a, shuffled_c):
            different_seed_can_differ = True
            break

    assert np.array_equal(shuffled_a, shuffled_b)
    assert group_count_a == group_count_b == 2
    assert different_seed_can_differ is True
    assert set(shuffled_a[:4]) == {0, 1, 2, 3}
    assert set(shuffled_a[4:7]) == {4, 5, 6}
    assert shuffled_a[7] == 7


def test_bscasma_rl_rc_numba_explicit_group_shuffle_uses_group_method():
    BRLSMASCARLRCNumbaCore._cp_list_cache.clear()
    problem = _build_problem(best_known=10**9)

    core = BRLSMASCARLRCNumbaCore(
        problem.items,
        problem.dim,
        problem.best_known,
        problem.values,
        problem.weights,
        problem.capacities,
        seed=123,
        pop_size=20,
        a=2.0,
        z=0.03,
        max_iter=1,
        alpha=0.1,
        gamma=0.9,
        eval_group_shuffle=True,
    )

    assert core.eval_group_shuffle is True
    assert core.item_eval_method == "lp_rc_groups"
    assert np.array_equal(np.sort(core.cp_list), np.arange(problem.items))


def test_bscasma_rl_rc_initial_pop_does_not_keep_rejected_item_resource(monkeypatch):
    BRLSMASCARLRCNumbaCore._cp_list_cache.clear()
    values = np.array([100, 1, 50], dtype=np.int64)
    weights = np.array([[11], [1], [9]], dtype=np.int64)
    capacities = np.array([10], dtype=np.int64)
    core = BRLSMASCARLRCNumbaCore(
        3,
        1,
        10**9,
        values,
        weights,
        capacities,
        seed=123,
        pop_size=3,
        a=2.0,
        z=0.03,
        max_iter=1,
        alpha=0.1,
        gamma=0.9,
    )
    core.cp_list = np.array([0, 1, 2], dtype=np.int64)
    monkeypatch.setattr(np.random, "random", lambda: 0.0)

    core.initial_pop()

    assert np.all(core.pop_sol[:, 0] == 0)
    assert np.all(core.pop_sol[:, 1] == 1)
    assert np.all(core.pop_sol[:, 2] == 1)
    assert np.all(core.pop_fit == 51)


def test_bscasma_rl_rc_default_init_flags_match_implicit_defaults():
    BRLSMASCARLRCNumbaCore._cp_list_cache.clear()
    solver = BRLSMASCARLRCNumbaSolver()
    problem = _build_problem(best_known=10**9)
    base_config = _build_numba_config(
        solver_id="brlsmasca_rl_rc_numba",
        solver_class="BRLSMASCARLRCNumbaSolver",
        max_iterations=8,
        params={"pop_size": 20},
    )
    explicit_config = _build_numba_config(
        solver_id="brlsmasca_rl_rc_numba",
        solver_class="BRLSMASCARLRCNumbaSolver",
        max_iterations=8,
        params={"pop_size": 20, "mixed_init_enabled": False, "restart_enabled": False},
    )

    result_a = solver.solve(problem, base_config, np.random.default_rng(777))
    result_b = solver.solve(problem, explicit_config, np.random.default_rng(777))

    assert result_a.best_objective == result_b.best_objective
    assert np.array_equal(result_a.best_solution, result_b.best_solution)
    assert result_b.metadata["mixed_init_enabled"] is False
    assert result_b.metadata["restart_enabled"] is False


def test_bscasma_rl_rc_mixed_init_is_feasible_binary_and_reproducible():
    BRLSMASCARLRCNumbaCore._cp_list_cache.clear()
    problem = _build_problem(best_known=10**9)

    core_a = BRLSMASCARLRCNumbaCore(
        problem.items,
        problem.dim,
        problem.best_known,
        problem.values,
        problem.weights,
        problem.capacities,
        seed=444,
        pop_size=20,
        a=2.0,
        z=0.03,
        max_iter=1,
        alpha=0.1,
        gamma=0.9,
        mixed_init_enabled=True,
    )
    core_b = BRLSMASCARLRCNumbaCore(
        problem.items,
        problem.dim,
        problem.best_known,
        problem.values,
        problem.weights,
        problem.capacities,
        seed=444,
        pop_size=20,
        a=2.0,
        z=0.03,
        max_iter=1,
        alpha=0.1,
        gamma=0.9,
        mixed_init_enabled=True,
    )

    assert core_a.mixed_init_enabled is True
    assert np.array_equal(core_a.pop_sol, core_b.pop_sol)
    assert np.array_equal(core_a.pop_fit, core_b.pop_fit)
    assert np.all((core_a.pop_sol == 0.0) | (core_a.pop_sol == 1.0))
    assert np.all(core_a.pop_sol @ problem.weights <= problem.capacities)


def test_bscasma_rl_rc_restart_triggers_after_stagnation_and_keeps_best_feasible():
    BRLSMASCARLRCNumbaCore._cp_list_cache.clear()
    values = np.array([10, 8, 6], dtype=np.int64)
    weights = np.array([[2], [2], [2]], dtype=np.int64)
    capacities = np.array([0], dtype=np.int64)

    core = BRLSMASCARLRCNumbaCore(
        3,
        1,
        10**9,
        values,
        weights,
        capacities,
        seed=123,
        pop_size=4,
        a=2.0,
        z=1.0,
        max_iter=3,
        alpha=0.1,
        gamma=0.9,
        restart_enabled=True,
        restart_window=1,
        restart_ratio=0.5,
        restart_strong_p=1.0,
        restart_core_p=1.0,
        restart_weak_p=1.0,
    )

    best_sol, best_fit = core.run()

    assert core.restart_count >= 1
    assert core.restart_rows >= 2
    assert best_fit == 0
    assert np.array_equal(best_sol, np.zeros(3, dtype=np.int64))
    assert np.all(best_sol @ weights <= capacities)


def test_bscasma_rl_rc_guided_probability_is_finite_and_clipped():
    probability = _guided_probability(
        1,
        100.0,
        1.0,
        0,
        100.0,
        True,
        10.0,
        10.0,
        10.0,
    )
    assert probability == pytest.approx(1.0)

    probability = _guided_probability(
        1,
        -100.0,
        0.0,
        2,
        -100.0,
        True,
        10.0,
        10.0,
        10.0,
    )
    assert probability == pytest.approx(0.0)


def test_bscasma_rl_rc_local_search_improves_toy_solution_and_keeps_feasible():
    values = np.array([10, 12, 1], dtype=np.int64)
    weights = np.array([[10], [10], [1]], dtype=np.int64)
    capacities = np.array([10], dtype=np.int64)
    cp_list = np.array([1, 0, 2], dtype=np.int64)
    pop_sol = np.array([[1.0, 0.0, 0.0]], dtype=np.float64)
    pop_fit = np.array([10.0], dtype=np.float64)
    resource = np.zeros(1, dtype=np.float64)
    repair_stats = np.zeros(1, dtype=np.int64)
    ls_stats = np.zeros(4, dtype=np.int64)
    work_row = np.empty(3, dtype=np.float64)
    drop_score = np.ones(values.size, dtype=np.float64)

    _local_search_bscasma_row_inplace(
        pop_sol,
        0,
        pop_fit,
        values,
        weights,
        capacities,
        cp_list,
        resource,
        values.size,
        capacities.size,
        1,
        0,
        repair_stats,
        0,
        drop_score,
        work_row,
        2,
        3,
        3,
        10,
        ls_stats,
    )

    assert pop_fit[0] == 12
    assert np.array_equal(pop_sol[0], np.array([0.0, 1.0, 0.0]))
    assert np.all(pop_sol[0] @ weights <= capacities)
    assert ls_stats[0] == 1
    assert ls_stats[1] >= 1
    assert ls_stats[2] == 1
    assert ls_stats[3] >= 1


def test_bscasma_rl_rc_archive_path_relink_improves_without_downgrading_best():
    values = np.array([10, 12], dtype=np.int64)
    weights = np.array([[10], [10]], dtype=np.int64)
    capacities = np.array([10], dtype=np.int64)
    cp_list = np.array([1, 0], dtype=np.int64)
    bucket = np.array([1, 1], dtype=np.int64)
    archive_sol = np.zeros((2, 2), dtype=np.float64)
    archive_fit = np.zeros(2, dtype=np.float64)
    archive_count = np.zeros(1, dtype=np.int64)
    gbest_sol = np.array([1.0, 0.0], dtype=np.float64)
    donor_sol = np.array([0.0, 1.0], dtype=np.float64)

    _archive_add_vector(archive_sol, archive_fit, archive_count, gbest_sol, 10.0, 2, 2)
    _archive_add_vector(archive_sol, archive_fit, archive_count, donor_sol, 12.0, 2, 2)
    pr_sol = np.zeros((1, 2), dtype=np.float64)
    pr_fit = np.zeros(1, dtype=np.float64)
    resource = np.zeros(1, dtype=np.float64)
    repair_stats = np.zeros(1, dtype=np.int64)
    pr_stats = np.zeros(3, dtype=np.int64)
    drop_score = np.ones(values.size, dtype=np.float64)

    best_fit = _path_relink_bscasma_inplace(
        archive_sol,
        archive_fit,
        archive_count,
        2,
        gbest_sol,
        10.0,
        values,
        weights,
        capacities,
        cp_list,
        bucket,
        pr_sol,
        pr_fit,
        resource,
        1,
        0,
        repair_stats,
        0,
        drop_score,
        2,
        True,
        pr_stats,
        2,
        1,
    )

    assert best_fit == 12
    assert np.array_equal(gbest_sol, donor_sol)
    assert pr_stats[0] == 1
    assert pr_stats[1] >= 1
    assert pr_stats[2] == 1


def test_bscasma_rl_rc_new_feature_flags_are_reproducible_and_report_metadata():
    solver = BRLSMASCARLRCNumbaSolver()
    problem = _build_problem(best_known=10**9)
    config = _build_numba_config(
        solver_id="brlsmasca_rl_rc_numba",
        solver_class="BRLSMASCARLRCNumbaSolver",
        max_iterations=6,
        params={
            "pop_size": 20,
            "guided_binary_enabled": True,
            "local_search_enabled": True,
            "archive_pr_enabled": True,
            "ls_budget_per_run": 20,
            "ls_cooldown": 0,
            "pr_interval": 1,
            "pr_max_steps": 3,
        },
    )

    result_a = solver.solve(problem, config, np.random.default_rng(2026))
    result_b = solver.solve(problem, config, np.random.default_rng(2026))

    assert result_a.best_objective == result_b.best_objective
    assert np.array_equal(result_a.best_solution, result_b.best_solution)
    assert result_a.metadata["guided_binary_enabled"] is True
    assert result_a.metadata["local_search_enabled"] is True
    assert result_a.metadata["archive_pr_enabled"] is True
    assert result_a.metadata["total_obj_eval_count"] >= result_a.evaluation_count
    assert set(result_a.best_solution.tolist()) <= {0, 1}
    assert np.all(result_a.best_solution @ problem.weights <= problem.capacities)


def test_bscasma_rl_rc_repair_v2_default_matches_current_repair():
    values = np.array([9, 8, 7, 6], dtype=np.int64)
    weights = np.array([[6, 4], [5, 4], [4, 5], [3, 3]], dtype=np.int64)
    capacities = np.array([10, 8], dtype=np.int64)
    cp_list = np.array([0, 1, 2, 3], dtype=np.int64)
    pop_sol_old = np.array([[1.0, 1.0, 1.0, 0.0]], dtype=np.float64)
    pop_sol_v2 = pop_sol_old.copy()
    pop_fit_old = np.array([24.0], dtype=np.float64)
    pop_fit_v2 = pop_fit_old.copy()
    resource_old = np.zeros(2, dtype=np.float64)
    resource_v2 = np.zeros(2, dtype=np.float64)
    repair_stats = np.zeros(1, dtype=np.int64)
    drop_score = np.ones(values.size, dtype=np.float64)

    _repair_bscasma_rl_rc_row_inplace(
        pop_sol_old,
        0,
        pop_fit_old,
        values,
        weights,
        capacities,
        cp_list,
        resource_old,
        values.size,
        capacities.size,
    )
    _repair_bscasma_row_v2_inplace(
        pop_sol_v2,
        0,
        pop_fit_v2,
        values,
        weights,
        capacities,
        cp_list,
        resource_v2,
        values.size,
        capacities.size,
        1,
        0,
        repair_stats,
        0,
        drop_score,
    )

    assert np.array_equal(pop_sol_v2, pop_sol_old)
    assert pop_fit_v2[0] == pytest.approx(pop_fit_old[0])
    assert repair_stats[0] == 0


def test_bscasma_rl_rc_repair_v2_repairs_infeasible_solution():
    values = np.array([10, 7, 5], dtype=np.int64)
    weights = np.array([[8], [5], [5]], dtype=np.int64)
    capacities = np.array([10], dtype=np.int64)
    cp_list = np.array([0, 1, 2], dtype=np.int64)
    pop_sol = np.array([[1.0, 1.0, 0.0]], dtype=np.float64)
    pop_fit = np.array([17.0], dtype=np.float64)
    resource = np.zeros(1, dtype=np.float64)
    repair_stats = np.zeros(1, dtype=np.int64)
    drop_score = np.ones(values.size, dtype=np.float64)

    _repair_bscasma_row_v2_inplace(
        pop_sol,
        0,
        pop_fit,
        values,
        weights,
        capacities,
        cp_list,
        resource,
        values.size,
        capacities.size,
        2,
        3,
        repair_stats,
        0,
        drop_score,
    )

    assert set(pop_sol[0].tolist()) <= {0.0, 1.0}
    assert np.all(pop_sol[0] @ weights <= capacities)
    assert pop_fit[0] == pytest.approx(float(np.dot(values, pop_sol[0])))


def test_bscasma_rl_rc_repair_v2_can_improve_with_bounded_swap():
    values = np.array([10, 12, 1], dtype=np.int64)
    weights = np.array([[10], [10], [1]], dtype=np.int64)
    capacities = np.array([10], dtype=np.int64)
    cp_list = np.array([1, 0, 2], dtype=np.int64)
    pop_sol = np.array([[1.0, 0.0, 0.0]], dtype=np.float64)
    pop_fit = np.array([10.0], dtype=np.float64)
    resource = np.zeros(1, dtype=np.float64)
    repair_stats = np.zeros(1, dtype=np.int64)
    drop_score = np.ones(values.size, dtype=np.float64)

    _repair_bscasma_row_v2_inplace(
        pop_sol,
        0,
        pop_fit,
        values,
        weights,
        capacities,
        cp_list,
        resource,
        values.size,
        capacities.size,
        2,
        3,
        repair_stats,
        0,
        drop_score,
    )

    assert pop_fit[0] == 12
    assert np.array_equal(pop_sol[0], np.array([0.0, 1.0, 0.0]))
    assert np.all(pop_sol[0] @ weights <= capacities)
    assert repair_stats[0] == 1


def test_bscasma_rl_rc_numba_rejects_invalid_repair_params():
    solver = BRLSMASCARLRCNumbaSolver()
    problem = _build_problem()
    rng = np.random.default_rng(1)
    base = {
        "solver_id": "brlsmasca_rl_rc_numba",
        "solver_class": "BRLSMASCARLRCNumbaSolver",
        "stop_condition": {"type": "max_iterations", "max_iterations": 5},
    }

    with pytest.raises(ValueError, match="params.repair_passes"):
        solver.solve(problem, {**base, "params": {"repair_passes": 0}}, rng)

    with pytest.raises(ValueError, match="params.repair_swap_limit"):
        solver.solve(problem, {**base, "params": {"repair_swap_limit": -1}}, rng)


def test_bscasma_rl_rc_numba_rejects_invalid_init_restart_params():
    solver = BRLSMASCARLRCNumbaSolver()
    problem = _build_problem()
    rng = np.random.default_rng(1)
    base = {
        "solver_id": "brlsmasca_rl_rc_numba",
        "solver_class": "BRLSMASCARLRCNumbaSolver",
        "stop_condition": {"type": "max_iterations", "max_iterations": 5},
    }

    with pytest.raises(ValueError, match="params.restart_window"):
        solver.solve(problem, {**base, "params": {"restart_window": 0}}, rng)

    with pytest.raises(ValueError, match="params.restart_ratio"):
        solver.solve(problem, {**base, "params": {"restart_ratio": 0.0}}, rng)

    with pytest.raises(ValueError, match="params.restart_ratio"):
        solver.solve(problem, {**base, "params": {"restart_ratio": 1.1}}, rng)

    with pytest.raises(ValueError, match="params.restart_strong_p"):
        solver.solve(problem, {**base, "params": {"restart_strong_p": -0.1}}, rng)

    with pytest.raises(ValueError, match="params.restart_core_p"):
        solver.solve(problem, {**base, "params": {"restart_core_p": 1.1}}, rng)

    with pytest.raises(ValueError, match="params.restart_weak_p"):
        solver.solve(problem, {**base, "params": {"restart_weak_p": -0.1}}, rng)

    with pytest.raises(ValueError, match="params.mixed_init_enabled"):
        solver.solve(problem, {**base, "params": {"mixed_init_enabled": "maybe"}}, rng)

    with pytest.raises(ValueError, match="params.restart_enabled"):
        solver.solve(problem, {**base, "params": {"restart_enabled": "maybe"}}, rng)


def test_bscasma_rl_rc_numba_rejects_invalid_remaining_strategy_params():
    solver = BRLSMASCARLRCNumbaSolver()
    problem = _build_problem()
    rng = np.random.default_rng(1)
    base = {
        "solver_id": "brlsmasca_rl_rc_numba",
        "solver_class": "BRLSMASCARLRCNumbaSolver",
        "stop_condition": {"type": "max_iterations", "max_iterations": 5},
    }

    invalid_cases = [
        ({"item_eval_method": "unknown"}, "params.item_eval_method"),
        ({"core_w_x_lp": -0.1}, "params.core_w_x_lp"),
        ({"core_w_x_lp": 0, "core_w_rc": 0, "core_w_eff": 0, "core_w_bucket": 0}, "params.core score weights"),
        ({"freq_cp_noise": -0.1}, "params.freq_cp_noise"),
        ({"freq_elite_ratio": 0}, "params.freq_elite_ratio"),
        ({"freq_quality_power": 0}, "params.freq_quality_power"),
        ({"freq_samples_dim5": 0}, "params.freq_samples_dim5"),
        ({"freq_blend_rho_dim5": -0.1}, "params.freq_blend_rho_dim5"),
        ({"freq_gate_probe_margin": -0.1}, "params.freq_gate_probe_margin"),
        ({"freq_gate_min_elites": 0}, "params.freq_gate_min_elites"),
        ({"freq_gate_min_std": -0.1}, "params.freq_gate_min_std"),
        ({"freq_gate_min_topk_overlap": 1.1}, "params.freq_gate_min_topk_overlap"),
        ({"sbl_candidate_limit": 0}, "params.sbl_candidate_limit"),
        ({"repair_drop_mode": "unknown"}, "params.repair_drop_mode"),
        ({"repair_drop_score_mode": "unknown"}, "params.repair_drop_score_mode"),
        ({"guided_binary_enabled": "maybe"}, "params.guided_binary_enabled"),
        ({"guided_lambda_lp": -0.1}, "params.guided_lambda_lp"),
        ({"guided_lambda_bucket": -0.1}, "params.guided_lambda_bucket"),
        ({"guided_lambda_slack": -0.1}, "params.guided_lambda_slack"),
        ({"local_search_enabled": "maybe"}, "params.local_search_enabled"),
        ({"ls_budget_per_run": -1}, "params.ls_budget_per_run"),
        ({"ls_max_passes": 0}, "params.ls_max_passes"),
        ({"ls_cooldown": -1}, "params.ls_cooldown"),
        ({"ls_add_cap": 0}, "params.ls_add_cap"),
        ({"ls_drop_cap": 0}, "params.ls_drop_cap"),
        ({"archive_pr_enabled": "maybe"}, "params.archive_pr_enabled"),
        ({"archive_size": 1}, "params.archive_size"),
        ({"pr_interval": 0}, "params.pr_interval"),
        ({"pr_max_steps": 0}, "params.pr_max_steps"),
        ({"pr_core_only": "maybe"}, "params.pr_core_only"),
    ]
    for params, match in invalid_cases:
        with pytest.raises(ValueError, match=match):
            solver.solve(problem, {**base, "params": params}, rng)


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
