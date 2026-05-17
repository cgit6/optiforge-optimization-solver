#!/usr/bin/env python3
"""比對 ``bsma`` 與 ``bsma_numba`` 在 GK 前兩題、repeat=1 / 20 的結果與總耗時。

用法（在倉庫根目錄，已啟用 venv 並 ``pip install numba``）::

    .venv/bin/python -m mkp.valid.bsma_numba_gk_benchmark

或指定迭代數（預設 1000，與 YAML 一致；測試可改小以縮短時間）::

    MKP_BENCH_MAX_ITER=200 .venv/bin/python -m mkp.valid.bsma_numba_gk_benchmark
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import numpy as np

try:
    import numba  # noqa: F401
except ImportError as exc:
    raise SystemExit("請先安裝 numba：pip install numba") from exc

from mkp.engine.repository import ProblemRepository
from mkp.problem import buildProblemRegistry, problemBuilders
from mkp.solver.BSMA import BSMASolver
from mkp.solver.BSMA_numba import BSMANumbaSolver


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_problem(problem_id: str):
    registry = buildProblemRegistry(problemBuilders())
    return ProblemRepository(config_root=_repo_root() / "configs" / "problems", registry=registry).load(
        "GK", problem_id, "mkp"
    )


def _max_iter() -> int:
    return int(os.environ.get("MKP_BENCH_MAX_ITER", "1000"))


def _bench_pair(problem_id: str, *, seed: int, max_iter: int) -> dict[str, object]:
    problem = _load_problem(problem_id)
    pop_size, z = 20, 0.08
    cfg = {
        "solver_id": "bench",
        "stop_condition": {"type": "max_iterations", "max_iterations": max_iter},
        "params": {"pop_size": pop_size, "z": z},
        "run_seed": seed,
    }

    rng = np.random.default_rng(seed)

    t0 = time.perf_counter()
    ref = BSMASolver().solve(problem, {**cfg, "solver_id": "bsma"}, rng)
    t_ref = time.perf_counter() - t0

    rng = np.random.default_rng(seed)
    t1 = time.perf_counter()
    nb = BSMANumbaSolver().solve(problem, {**cfg, "solver_id": "bsma_numba"}, rng)
    t_nb = time.perf_counter() - t1

    init_match = True
    proc_note = "主迴圈在 Numba 內；若需逐代 digest 請另開 _loop_trace（預設關閉）"

    same_obj = int(ref.best_objective) == int(nb.best_objective)
    same_sol = np.array_equal(
        np.asarray(ref.best_solution, dtype=np.int64),
        np.asarray(nb.best_solution, dtype=np.int64),
    )

    return {
        "problem_id": problem_id,
        "seed": seed,
        "max_iter": max_iter,
        "ref_objective": int(ref.best_objective),
        "nb_objective": int(nb.best_objective),
        "same_objective": same_obj,
        "same_solution": same_sol,
        "ref_runtime_s": t_ref,
        "nb_runtime_s": t_nb,
        "speedup": t_ref / t_nb if t_nb > 0 else float("inf"),
        "initial_pop_match_checked_in_tests": init_match,
        "process_note": proc_note,
    }


def main() -> None:
    max_iter = _max_iter()
    print("BSMA vs BSMA_numba — GK mk_gk01 / mk_gk02\n")
    print(f"max_iterations={max_iter} (環境變數 MKP_BENCH_MAX_ITER 可覆寫)\n")

    for rep in (1, 20):
        print(f"--- repeat 語意：seed 偏移 0..{rep-1}（共 {rep} 組）---")
        for pid in ("mk_gk01", "mk_gk02"):
            times_ref: list[float] = []
            times_nb: list[float] = []
            all_match = True
            for r in range(rep):
                seed = 42 + r
                row = _bench_pair(pid, seed=seed, max_iter=max_iter)
                times_ref.append(float(row["ref_runtime_s"]))
                times_nb.append(float(row["nb_runtime_s"]))
                all_match = all_match and bool(row["same_objective"] and row["same_solution"])
                if not row["same_objective"] or not row["same_solution"]:
                    print(f"  MISMATCH {pid} seed={seed} ref_obj={row['ref_objective']} nb_obj={row['nb_objective']}")
            tot_ref = sum(times_ref)
            tot_nb = sum(times_nb)
            print(
                f"  {pid} repeat={rep}: all_match={all_match} "
                f"total_ref={tot_ref:.4f}s total_nb={tot_nb:.4f}s "
                f"overall_speedup={tot_ref/tot_nb:.2f}x"
            )
        print()

    print("CLI 等價實驗（process worker，需 bsma_numba 已註冊）範例：\n")
    print(
        "  .venv/bin/python -m mkp.cli.run \\\n"
        "    --experiment-name bsma_numba_gk_worker \\\n"
        "    --type mkp --dataset GK \\\n"
        "    --problems mk_gk01,mk_gk02 \\\n"
        "    --solver bsma_numba --repeat 20 --seed 42 --worker 4\n"
    )
    print("參考（純 bsma）：將 --solver bsma 與 experiment-name 改名即可。\n")


if __name__ == "__main__":
    main()
