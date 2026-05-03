from __future__ import annotations

import tempfile
from pathlib import Path

from mkp.valid.bsca2_population_trace import _compare_problem


def test_bsca2_population_trace_weish01_seed_101_bit_identical():
    """回歸錨點：WEISH/weish01 + seed 101 + max_iter 30，old 與 new 應逐代 bit-identical。"""
    repo_root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as td:
        summary = _compare_problem(
            repo_root=repo_root,
            output_dir=Path(td),
            dataset="WEISH",
            problem_id="weish01",
            seed=101,
            max_iterations=30,
            pop_size=20,
            a=2.0,
        )
    assert summary.initial_unsorted_match is True
    assert summary.initial_sorted_match is True
    assert summary.population_trace_match is True
    assert summary.final_solution_match is True
    assert summary.final_objective_old == summary.final_objective_new
    assert summary.all_match is True


def test_bsca2_population_trace_weish01_three_seeds_bit_identical():
    """計畫驗收：WEISH/weish01 + 三個固定 seeds（101 / 202 / 303）、max_iter 30，逐代 bit-identical。"""
    repo_root = Path(__file__).resolve().parents[1]
    for seed in (101, 202, 303):
        with tempfile.TemporaryDirectory() as td:
            summary = _compare_problem(
                repo_root=repo_root,
                output_dir=Path(td),
                dataset="WEISH",
                problem_id="weish01",
                seed=seed,
                max_iterations=30,
                pop_size=20,
                a=2.0,
            )
        assert summary.population_trace_match is True, f"seed={seed}"
        assert summary.final_solution_match is True, f"seed={seed}"
        assert summary.final_objective_old == summary.final_objective_new, f"seed={seed}"
        assert summary.all_match is True, f"seed={seed}"
