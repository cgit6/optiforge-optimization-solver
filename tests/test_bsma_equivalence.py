from __future__ import annotations

from pathlib import Path

from mkp.valid.bsma_equivalence import verify_equivalence


def test_verify_equivalence_new_uses_same_core_as_solver():
    """new 路徑只掛 BSMACore；與 old/BSMA 在相同 seed 下應逐步一致（回歸錨點）。"""
    repo_root = Path(__file__).resolve().parents[1]
    report = verify_equivalence(
        repo_root=repo_root,
        dataset="WEISH",
        problem_id="weish01",
        seed=101,
        max_iterations=30,
    )
    assert report.trace_match is True
    assert report.final_solution_match is True
    assert report.final_objective_old == report.final_objective_new


def test_verify_equivalence_weish01_three_seeds():
    """計畫驗收：WEISH/weish01 + 三個固定 seeds。"""
    repo_root = Path(__file__).resolve().parents[1]
    for seed in (101, 202, 303):
        report = verify_equivalence(
            repo_root=repo_root,
            dataset="WEISH",
            problem_id="weish01",
            seed=seed,
            max_iterations=30,
        )
        assert report.trace_match is True, f"seed={seed}"
        assert report.final_solution_match is True, f"seed={seed}"
        assert report.final_objective_old == report.final_objective_new, f"seed={seed}"


def test_verify_equivalence_include_loop_meta_shape():
    repo_root = Path(__file__).resolve().parents[1]
    report = verify_equivalence(
        repo_root=repo_root,
        dataset="WEISH",
        problem_id="weish01",
        seed=101,
        max_iterations=30,
        include_loop_meta=True,
    )
    assert report.loop_meta_new is not None
    # 若提前達 best_known，外層迭代會少於 max_iterations
    assert 1 <= len(report.loop_meta_new) <= 30
    assert report.loop_meta_new[0]["iter"] == 0
    assert all("W0_digest" in row for row in report.loop_meta_new)
