"""``BRLSMASCA2V100320050TestNumbaCore`` 與參考 Core 在 GK 題上的數值對齊（需安裝 optional ``numba``）。"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("numba")

from mkp.engine.repository import ProblemRepository
from mkp.solver.BSCASMA import BRLSMASCA2V100320050TestCore
from mkp.solver.BSCASMA_numby import BRLSMASCA2V100320050TestNumbaCore


def _load_gk(repo_root: Path, problem_id: str):
    return ProblemRepository(config_root=repo_root / "configs" / "problems").load(
        "GK", problem_id, "mkp"
    )


def _assert_cores_match_after_init(ref: BRLSMASCA2V100320050TestCore, numba: BRLSMASCA2V100320050TestNumbaCore) -> None:
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
    pop_size: int,
    a: float,
    z: float,
    max_iter: int,
    prob_arr: tuple[float, float, float, float] = (0.04, 0.46, 0.25, 0.25),
) -> tuple[BRLSMASCA2V100320050TestCore, BRLSMASCA2V100320050TestNumbaCore]:
    np.random.seed(seed)
    ref = BRLSMASCA2V100320050TestCore(
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
        max_iter=max_iter,
        prob_arr=prob_arr,
    )
    np.random.seed(seed)
    numba_c = BRLSMASCA2V100320050TestNumbaCore(
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
        max_iter=max_iter,
        prob_arr=prob_arr,
    )
    return ref, numba_c


@pytest.mark.parametrize("problem_id", ("mk_gk01", "mk_gk02"))
@pytest.mark.parametrize("repeat_idx", (0, 9))
def test_bscasma_numba_matches_reference_gk_initial_and_result(
    tmp_path: Path, problem_id: str, repeat_idx: int
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    problem = _load_gk(repo_root, problem_id)
    seed = 100 + repeat_idx
    max_iter = 50
    pop_size = 20
    a = 2.0
    z = 0.03

    ref, numba_c = _build_cores(
        problem, seed=seed, pop_size=pop_size, a=a, z=z, max_iter=max_iter
    )
    _assert_cores_match_after_init(ref, numba_c)

    sol_r, fit_r = ref.run()
    sol_n, fit_n = numba_c.run()

    assert int(fit_r) == int(fit_n)
    assert np.array_equal(np.asarray(sol_r, dtype=np.int64), np.asarray(sol_n, dtype=np.int64))


def test_bscasma_numba_warmup_jit_smoke(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    problem = _load_gk(repo_root, "mk_gk01")
    ref, numba_c = _build_cores(
        problem, seed=1, pop_size=10, a=2.0, z=0.03, max_iter=5
    )
    _assert_cores_match_after_init(ref, numba_c)
    sol_n, fit_n = numba_c.run()
    assert sol_n.shape == (problem.items,)
    assert isinstance(fit_n, int)
