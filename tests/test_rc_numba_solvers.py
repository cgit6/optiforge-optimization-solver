from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from mkp.engine.builders import solverBuilders
from mkp.engine.repository import ProblemRepository
from mkp.problem import ProblemModel, buildProblemRegistry, problemBuilders
from mkp.solver.BSCA_rc_numba import BSCARCNumbaCore, BSCARCNumbaSolver
from mkp.solver.BSMA_rc_numba import BSMARCNumbaCore, BSMARCNumbaSolver
from mkp.solver.registry import SolverRegistry
from mkp.tools.solver_config_loader import SolverConfigLoader


def _build_problem(*, best_known: int = 10**9) -> ProblemModel:
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


def _config(solver_id: str, solver_class: str, *, max_iterations: int = 6, params: dict | None = None) -> dict:
    return {
        "solver_id": solver_id,
        "solver_class": solver_class,
        "stop_condition": {"type": "max_iterations", "max_iterations": max_iterations},
        "params": params or {},
    }


def test_rc_numba_solvers_can_be_created_by_registry():
    registry = SolverRegistry()
    builders = solverBuilders()
    registry.register("bsma_rc_numba", builders["bsma_rc_numba"])
    registry.register("bsca_rc_numba", builders["bsca_rc_numba"])

    assert isinstance(registry.create("bsma_rc_numba"), BSMARCNumbaSolver)
    assert isinstance(registry.create("bsca_rc_numba"), BSCARCNumbaSolver)


def test_rc_numba_solver_configs_load_param_0_and_last():
    loader = SolverConfigLoader()

    bsma_first = loader.load("bsma_rc_numba", param_set_index=0)
    bsma_last = loader.load("bsma_rc_numba", param_set_index=8)
    bsca_first = loader.load("bsca_rc_numba", param_set_index=0)
    bsca_last = loader.load("bsca_rc_numba", param_set_index=8)

    assert bsma_first["solver_class"] == "BSMARCNumbaSolver"
    assert bsma_first["params"]["z"] == 0.01
    assert bsma_last["params"]["z"] == 0.15
    assert bsma_last["params"]["ctf"] == "abs_pow_16"
    assert bsca_first["solver_class"] == "BSCARCNumbaSolver"
    assert bsca_first["params"]["a"] == 1.5
    assert bsca_last["params"]["a"] == 2.5
    for cfg in (bsma_first, bsma_last, bsca_first, bsca_last):
        assert cfg["params"]["eval_group_shuffle"] is False
        assert cfg["params"]["repair_passes"] == 2
        assert cfg["params"]["repair_swap_limit"] == 4
        assert cfg["params"]["mixed_init_enabled"] is True
        assert cfg["params"]["restart_enabled"] is True


@pytest.mark.parametrize(
    ("solver", "solver_id", "solver_class", "params"),
    (
        (BSMARCNumbaSolver(), "bsma_rc_numba", "BSMARCNumbaSolver", {"pop_size": 6, "z": 0.08}),
        (BSCARCNumbaSolver(), "bsca_rc_numba", "BSCARCNumbaSolver", {"pop_size": 6, "a": 2.0}),
    ),
)
def test_rc_numba_solvers_return_valid_solve_result_and_metadata(solver, solver_id, solver_class, params):
    BSMARCNumbaCore._item_eval_cache.clear()
    BSCARCNumbaCore._item_eval_cache.clear()
    problem = _build_problem()
    config = _config(solver_id, solver_class, params=params)

    result = solver.solve(problem, config, np.random.default_rng(123))

    assert result.problem_id == "weish01"
    assert result.solver_id == solver_id
    assert result.best_solution.shape == (problem.items,)
    assert set(result.best_solution.tolist()) <= {0, 1}
    assert np.all(result.best_solution @ problem.weights <= problem.capacities)
    assert result.best_objective == int(result.best_solution @ problem.values)
    assert result.metadata["numba"] is True
    assert result.metadata["rc"] is True
    assert result.metadata["item_eval_method"] == "lp_rc_ordered"
    assert result.metadata["item_eval_fallback"] is False
    assert isinstance(result.metadata["lp_fractional_count"], int)
    assert isinstance(result.metadata["eff_group_count"], int)
    assert result.metadata["repair_passes"] == 1
    assert result.metadata["repair_swap_limit"] == 0
    assert result.metadata["mixed_init_enabled"] is False
    assert result.metadata["restart_enabled"] is False


@pytest.mark.parametrize(
    ("solver", "solver_id", "solver_class", "params"),
    (
        (BSMARCNumbaSolver(), "bsma_rc_numba", "BSMARCNumbaSolver", {"pop_size": 6, "z": 0.08}),
        (BSCARCNumbaSolver(), "bsca_rc_numba", "BSCARCNumbaSolver", {"pop_size": 6, "a": 2.0}),
    ),
)
def test_rc_numba_solvers_are_reproducible_with_same_seed(solver, solver_id, solver_class, params):
    problem = _build_problem()
    config = _config(solver_id, solver_class, params=params)

    result_a = solver.solve(problem, config, np.random.default_rng(999))
    result_b = solver.solve(problem, config, np.random.default_rng(999))

    assert result_a.run_seed == result_b.run_seed
    assert result_a.best_objective == result_b.best_objective
    assert np.array_equal(result_a.best_solution, result_b.best_solution)


@pytest.mark.parametrize(
    ("core_cls", "params"),
    (
        (BSMARCNumbaCore, {"pop_size": 6, "z": 0.08, "max_iter": 1}),
        (BSCARCNumbaCore, {"pop_size": 6, "a": 2.0, "max_iter": 1}),
    ),
)
def test_rc_numba_core_cp_list_is_complete_permutation(core_cls, params):
    problem = _build_problem()
    core = core_cls(
        problem.items,
        problem.dim,
        problem.best_known,
        problem.values,
        problem.weights,
        problem.capacities,
        seed=321,
        **params,
    )

    assert np.array_equal(np.sort(core.cp_list), np.arange(problem.items))
    assert core.item_eval_payload["base_order"].shape == (problem.items,)
    assert core.item_eval_fallback is False


@pytest.mark.parametrize(
    ("core_cls", "params"),
    (
        (BSMARCNumbaCore, {"pop_size": 10, "z": 0.08, "max_iter": 1}),
        (BSCARCNumbaCore, {"pop_size": 10, "a": 2.0, "max_iter": 1}),
    ),
)
def test_rc_numba_mixed_init_is_feasible_binary_and_reproducible(core_cls, params):
    problem = _build_problem()
    core_a = core_cls(
        problem.items,
        problem.dim,
        problem.best_known,
        problem.values,
        problem.weights,
        problem.capacities,
        seed=444,
        mixed_init_enabled=True,
        **params,
    )
    core_b = core_cls(
        problem.items,
        problem.dim,
        problem.best_known,
        problem.values,
        problem.weights,
        problem.capacities,
        seed=444,
        mixed_init_enabled=True,
        **params,
    )

    assert np.array_equal(core_a.pop_sol, core_b.pop_sol)
    assert np.array_equal(core_a.pop_fit, core_b.pop_fit)
    assert np.all((core_a.pop_sol == 0.0) | (core_a.pop_sol == 1.0))
    assert np.all(core_a.pop_sol @ problem.weights <= problem.capacities)


@pytest.mark.parametrize(
    ("core_cls", "params"),
    (
        (BSMARCNumbaCore, {"pop_size": 4, "z": 1.0, "max_iter": 3}),
        (BSCARCNumbaCore, {"pop_size": 4, "a": 2.0, "max_iter": 3}),
    ),
)
def test_rc_numba_restart_triggers_after_stagnation_and_keeps_best_feasible(core_cls, params):
    values = np.array([10, 8, 6], dtype=np.int64)
    weights = np.array([[2], [2], [2]], dtype=np.int64)
    capacities = np.array([0], dtype=np.int64)
    core = core_cls(
        3,
        1,
        10**9,
        values,
        weights,
        capacities,
        seed=123,
        restart_enabled=True,
        restart_window=1,
        restart_ratio=0.5,
        restart_strong_p=1.0,
        restart_core_p=1.0,
        restart_weak_p=1.0,
        **params,
    )

    best_sol, best_fit = core.run()

    assert core.restart_count >= 1
    assert core.restart_rows >= 2
    assert best_fit == 0
    assert np.array_equal(best_sol, np.zeros(3, dtype=np.int64))
    assert np.all(best_sol @ weights <= capacities)


@pytest.mark.parametrize(
    ("solver", "solver_id", "solver_class", "valid_params"),
    (
        (BSMARCNumbaSolver(), "bsma_rc_numba", "BSMARCNumbaSolver", {"pop_size": 6, "z": 0.08}),
        (BSCARCNumbaSolver(), "bsca_rc_numba", "BSCARCNumbaSolver", {"pop_size": 6, "a": 2.0}),
    ),
)
def test_rc_numba_solvers_reject_invalid_repair_restart_params(solver, solver_id, solver_class, valid_params):
    problem = _build_problem()
    base = _config(solver_id, solver_class, params=valid_params)
    rng = np.random.default_rng(1)

    invalid_cases = (
        ("repair_passes", 0),
        ("repair_swap_limit", -1),
        ("restart_window", 0),
        ("restart_ratio", 0.0),
        ("restart_ratio", 1.1),
        ("restart_strong_p", -0.1),
        ("restart_core_p", 1.1),
        ("restart_weak_p", -0.1),
        ("mixed_init_enabled", "maybe"),
        ("restart_enabled", "maybe"),
    )
    for key, value in invalid_cases:
        cfg = {
            **base,
            "params": {**valid_params, key: value},
        }
        with pytest.raises(ValueError, match=f"params.{key}"):
            solver.solve(problem, cfg, rng)
