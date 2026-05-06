"""``BSCANumbaCore`` 與 ``BSCACore`` 在 GK 題上的數值對齊（需安裝 optional ``numba``）。"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("numba")

from mkp.engine.repository import ProblemRepository
from mkp.solver.BSCA import BSCACore
from mkp.solver.BSCA_numba import BSCANumbaCore


def _load_gk(repo_root: Path, problem_id: str):
    return ProblemRepository(config_root=repo_root / "configs" / "problems").load(
        "GK", problem_id, "mkp"
    )


def _assert_cores_match_after_init(ref: BSCACore, numba: BSCANumbaCore) -> None:
    assert np.array_equal(ref.pop_sol, numba.pop_sol)
    assert np.array_equal(ref.pop_fit, numba.pop_fit)
    assert np.array_equal(ref.cp_list, numba.cp_list)


def _build_cores(
    problem, *, seed: int, pop_size: int, a: float, max_iter: int
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
        max_iter=max_iter,
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
        max_iter=max_iter,
    )
    return ref, numba_c


@pytest.mark.parametrize("problem_id", ("mk_gk01", "mk_gk02"))
@pytest.mark.parametrize("repeat_idx", (0, 19))
def test_bsca_numba_matches_reference_gk_initial_and_result(
    tmp_path: Path, problem_id: str, repeat_idx: int
) -> None:
    """同一 seed 下初始族群與最終 (best_sol, best_fit) 與參考 ``BSCACore`` 一致。"""
    repo_root = Path(__file__).resolve().parents[1]
    problem = _load_gk(repo_root, problem_id)
    seed = 42 + repeat_idx
    max_iter = 80
    pop_size = 20
    a = 2.0

    ref, numba_c = _build_cores(problem, seed=seed, pop_size=pop_size, a=a, max_iter=max_iter)
    _assert_cores_match_after_init(ref, numba_c)

    sol_r, fit_r = ref.run()
    sol_n, fit_n = numba_c.run()

    assert int(fit_r) == int(fit_n)
    assert np.array_equal(np.asarray(sol_r, dtype=np.int64), np.asarray(sol_n, dtype=np.int64))


def test_bsca_numba_warmup_jit_smoke(tmp_path: Path) -> None:
    """最短 smoke：確保 njit 可編譯執行。"""
    repo_root = Path(__file__).resolve().parents[1]
    problem = _load_gk(repo_root, "mk_gk01")
    ref, numba_c = _build_cores(problem, seed=1, pop_size=10, a=2.0, max_iter=5)
    _assert_cores_match_after_init(ref, numba_c)
    sol_n, fit_n = numba_c.run()
    assert sol_n.shape == (problem.items,)
    assert isinstance(fit_n, int)
