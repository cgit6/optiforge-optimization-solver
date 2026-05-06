from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("numba")

from mkp.engine.repository import ProblemRepository
from mkp.solver.BSCASMA import BRLSMASCATestCore
from mkp.solver.BSCASMA_numba import BRLSMASCATestNumbaCore


def _load_weish01(repo_root: Path):
    return ProblemRepository(config_root=repo_root / "configs" / "problems").load(
        "WEISH", "weish01", "mkp"
    )


def _assert_cores_match_after_init(ref: BRLSMASCATestCore, numba: BRLSMASCATestNumbaCore) -> None:
    assert np.array_equal(ref.pop_sol, numba.pop_sol)
    assert np.array_equal(ref.pop_fit, numba.pop_fit)
    assert np.array_equal(ref.cp_list, numba.cp_list)
    assert np.array_equal(ref.best_method, numba.best_method)
    assert np.array_equal(ref.individual_best_sol, numba.individual_best_sol)
    assert np.array_equal(ref.individual_best_fit, numba.individual_best_fit)


def _build_cores(
    problem,
    *,
    seed: int,
    max_iterations: int,
    pop_size: int,
    a: float,
    z: float,
    prob_arr: tuple[float, float, float, float],
) -> tuple[BRLSMASCATestCore, BRLSMASCATestNumbaCore]:
    np.random.seed(seed)
    ref = BRLSMASCATestCore(
        problem.items,
        problem.dim,
        problem.best_known,
        problem.values,
        problem.weights,
        problem.capacities,
        seed=seed,
        pop_size=pop_size,
        a=a,
        z=z,
        max_iter=max_iterations,
        prob_arr=prob_arr,
    )
    np.random.seed(seed)
    numba_c = BRLSMASCATestNumbaCore(
        problem.items,
        problem.dim,
        problem.best_known,
        problem.values,
        problem.weights,
        problem.capacities,
        seed=seed,
        pop_size=pop_size,
        a=a,
        z=z,
        max_iter=max_iterations,
        prob_arr=prob_arr,
    )
    return ref, numba_c


def test_bscasma_python_numba_weish01_seed_101_bit_identical():
    """WEISH/weish01 + seed 101 + max_iter 30：參考 Core 與 Numba Core 應完全一致。"""
    repo_root = Path(__file__).resolve().parents[1]
    problem = _load_weish01(repo_root)
    prob_arr = (0.04, 0.46, 0.25, 0.25)
    ref, numba_c = _build_cores(
        problem,
        seed=101,
        max_iterations=30,
        pop_size=20,
        a=2.0,
        z=0.03,
        prob_arr=prob_arr,
    )
    _assert_cores_match_after_init(ref, numba_c)

    sol_r, fit_r = ref.run()
    sol_n, fit_n = numba_c.run()

    assert int(fit_r) == int(fit_n)
    assert np.array_equal(np.asarray(sol_r, dtype=np.int64), np.asarray(sol_n, dtype=np.int64))


def test_bscasma_python_numba_weish01_three_seeds_bit_identical():
    repo_root = Path(__file__).resolve().parents[1]
    problem = _load_weish01(repo_root)
    prob_arr = (0.04, 0.46, 0.25, 0.25)
    for seed in (101, 202, 303):
        ref, numba_c = _build_cores(
            problem,
            seed=seed,
            max_iterations=30,
            pop_size=20,
            a=2.0,
            z=0.03,
            prob_arr=prob_arr,
        )
        _assert_cores_match_after_init(ref, numba_c)
        sol_r, fit_r = ref.run()
        sol_n, fit_n = numba_c.run()
        assert int(fit_r) == int(fit_n), f"seed={seed}"
        assert np.array_equal(np.asarray(sol_r, dtype=np.int64), np.asarray(sol_n, dtype=np.int64)), f"seed={seed}"
