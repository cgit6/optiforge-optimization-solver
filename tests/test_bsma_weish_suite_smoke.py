from __future__ import annotations

from pathlib import Path

from mkp.bsma_equivalence import max_outer_iterations_for_budget, verify_equivalence_streaming
from mkp.problem_dat_converter import load_problem_model_from_repo_dat


def test_weish_streaming_equivalence_smoke_matches_memory_path():
    """小 budget：串流驗證與記憶體 trace 驗證結果一致（weish01）。"""
    from mkp.bsma_equivalence import verify_equivalence

    repo_root = Path(__file__).resolve().parents[1]
    budget = 2000
    max_iter = max_outer_iterations_for_budget(budget=budget)
    seed = 101
    trace_dir = repo_root / "mkp/output/bsma_weish_suite_test_smoke/stream_traces"
    problem = load_problem_model_from_repo_dat(repo_root=repo_root, dataset="WEISH", problem_id="weish01")

    mem = verify_equivalence(
        repo_root=repo_root,
        dataset="WEISH",
        problem_id="weish01",
        seed=seed,
        max_iterations=max_iter,
        problem=problem,
    )
    stream = verify_equivalence_streaming(
        repo_root=repo_root,
        dataset="WEISH",
        problem_id="weish01",
        seed=seed,
        max_iterations=max_iter,
        trace_dir=trace_dir,
        problem=problem,
    )
    assert stream.trace_match is True
    assert stream.final_solution_match is True
    assert mem.trace_match is True
    assert stream.trace_length_old == mem.trace_length_old
    assert stream.final_objective_old == mem.final_objective_old


def test_weish_streaming_smoke_two_problems_small_budget():
    repo_root = Path(__file__).resolve().parents[1]
    budget = 2000
    max_iter = max_outer_iterations_for_budget(budget=budget)
    trace_dir = repo_root / "mkp/output/bsma_weish_suite_test_smoke/batch_traces"
    for problem_id in ("weish01", "weish30"):
        problem = load_problem_model_from_repo_dat(
            repo_root=repo_root, dataset="WEISH", problem_id=problem_id
        )
        report = verify_equivalence_streaming(
            repo_root=repo_root,
            dataset="WEISH",
            problem_id=problem_id,
            seed=101,
            max_iterations=max_iter,
            trace_dir=trace_dir,
            problem=problem,
        )
        assert report.trace_match is True, problem_id
        assert report.final_solution_match is True, problem_id
        assert report.final_objective_old == report.final_objective_new, problem_id
        assert report.new_stop_reason is not None
        assert report.new_reported_eval_count is not None
