from __future__ import annotations

from pathlib import Path

from mkp.valid.bsma_equivalence import max_outer_iterations_for_budget, verify_equivalence_streaming
from mkp.engine.repository import ProblemRepository
from mkp.problem import buildProblemRegistry, problemBuilders


def test_weish_streaming_equivalence_smoke_matches_memory_final_result(tmp_path: Path):
    """小 budget：串流與記憶體路徑都能產生一致的 weish01 最終結果。"""
    from mkp.valid.bsma_equivalence import verify_equivalence

    repo_root = Path(__file__).resolve().parents[1]
    budget = 2000
    max_iter = max_outer_iterations_for_budget(budget=budget)
    seed = 101
    trace_dir = tmp_path / "stream_traces"
    repository = ProblemRepository(
        config_root=repo_root / "configs/problems",
        registry=buildProblemRegistry(problemBuilders()),
    )
    problem = repository.load("WEISH", "weish01")

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
    assert stream.final_solution_match is True
    assert mem.final_solution_match is True
    assert stream.trace_length_old == mem.trace_length_old
    assert stream.final_objective_old == mem.final_objective_old
    assert stream.new_stop_reason is not None
    assert stream.new_reported_eval_count is not None
