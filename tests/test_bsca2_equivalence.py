from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("numba")

from mkp.engine.repository import ProblemRepository
from mkp.solver.BSCA import BSCACore
from mkp.solver.BSCA_numba import BSCANumbaCore


def _load_weish01(repo_root: Path):
    return ProblemRepository(config_root=repo_root / "configs" / "problems").load(
        "WEISH", "weish01", "mkp"
    )


def _assert_cores_match_after_init(ref: BSCACore, numba: BSCANumbaCore) -> None:
    assert np.array_equal(ref.pop_sol, numba.pop_sol)
    assert np.array_equal(ref.pop_fit, numba.pop_fit)
    assert np.array_equal(ref.cp_list, numba.cp_list)


def _build_cores(
    problem, *, seed: int, max_iterations: int, pop_size: int, a: float
) -> tuple[BSCACore, BSCANumbaCore]:
    np.random.seed(seed)
    ref = BSCACore(
        problem.items,
        problem.dim,
        problem.best_known,
        problem.values,
        problem.weights,
        problem.capacities,
        seed=seed,
        pop_size=pop_size,
        a=a,
        max_iter=max_iterations,
    )
    np.random.seed(seed)
    numba_c = BSCANumbaCore(
        problem.items,
        problem.dim,
        problem.best_known,
        problem.values,
        problem.weights,
        problem.capacities,
        seed=seed,
        pop_size=pop_size,
        a=a,
        max_iter=max_iterations,
    )
    return ref, numba_c


def test_bsca2_python_numba_weish01_seed_101_bit_identical():
    """WEISH/weish01 + seed 101 + max_iter 30：參考 ``BSCACore`` 與 ``BSCANumbaCore`` 應完全一致。"""
    repo_root = Path(__file__).resolve().parents[1]
    problem = _load_weish01(repo_root)
    seed = 101
    max_iter = 30
    pop_size = 20
    a = 2.0

    ref, numba_c = _build_cores(problem, seed=seed, max_iterations=max_iter, pop_size=pop_size, a=a)
    _assert_cores_match_after_init(ref, numba_c)

    sol_r, fit_r = ref.run()
    sol_n, fit_n = numba_c.run()

    assert int(fit_r) == int(fit_n)
    assert np.array_equal(np.asarray(sol_r, dtype=np.int64), np.asarray(sol_n, dtype=np.int64))


def test_bsca2_python_numba_weish01_three_seeds_bit_identical():
    """WEISH/weish01 + seeds 101 / 202 / 303、max_iter 30：Python 與 Numba 本體逐解一致。"""
    repo_root = Path(__file__).resolve().parents[1]
    problem = _load_weish01(repo_root)
    max_iter = 30
    pop_size = 20
    a = 2.0

    for seed in (101, 202, 303):
        ref, numba_c = _build_cores(problem, seed=seed, max_iterations=max_iter, pop_size=pop_size, a=a)
        _assert_cores_match_after_init(ref, numba_c)
        sol_r, fit_r = ref.run()
        sol_n, fit_n = numba_c.run()
        assert int(fit_r) == int(fit_n), f"seed={seed}"
        assert np.array_equal(np.asarray(sol_r, dtype=np.int64), np.asarray(sol_n, dtype=np.int64)), f"seed={seed}"
