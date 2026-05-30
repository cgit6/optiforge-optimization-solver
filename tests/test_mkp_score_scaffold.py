from __future__ import annotations

from pathlib import Path

import numpy as np

from mkp.engine.repository import ProblemRepository
from mkp.problem import buildProblemRegistry, problemBuilders
from mkp.tools.mkp_score_scaffold import (
    _batch_repair_rank_objectives,
    _batch_repair_weight_objectives,
    build_score_variants,
    lagrangian_multipliers,
    run_problem,
)


def _problem():
    repo_root = Path(__file__).resolve().parents[1]
    repository = ProblemRepository(
        config_root=repo_root / "configs/problems",
        registry=buildProblemRegistry(problemBuilders()),
    )
    return repository.load("WEISH", "weish01")


def test_score_scaffold_variants_are_finite_and_complete_orders():
    problem = _problem()

    variants = build_score_variants(problem)

    assert "CURRENT-RANK" in variants
    assert {"CND-rank", "DUAL-weight", "RC-rank", "HYB-weight", "LAG-rank"} <= set(variants)
    for score, order in variants.values():
        assert score.shape == (problem.items,)
        assert np.all(np.isfinite(score))
        assert np.array_equal(np.sort(order), np.arange(problem.items))


def test_score_scaffold_rank_and_weight_repair_return_objectives():
    problem = _problem()
    variants = build_score_variants(problem)
    raw = np.ones((3, problem.items), dtype=np.int8)
    score, order = variants["CURRENT-RANK"]

    rank_objectives = _batch_repair_rank_objectives(
        raw,
        np.asarray(problem.values, dtype=np.int64),
        np.asarray(problem.weights, dtype=np.int64),
        np.asarray(problem.capacities, dtype=np.int64),
        np.asarray(order, dtype=np.int64),
    )
    weight_objectives = _batch_repair_weight_objectives(
        raw,
        np.asarray(problem.values, dtype=np.int64),
        np.asarray(problem.weights, dtype=np.int64),
        np.asarray(problem.capacities, dtype=np.int64),
        np.asarray(score, dtype=np.float64),
    )

    assert rank_objectives.shape == (3,)
    assert weight_objectives.shape == (3,)
    assert np.all(rank_objectives > 0)
    assert np.all(weight_objectives > 0)


def test_score_scaffold_run_problem_is_reproducible():
    problem = _problem()

    rows_a, summaries_a = run_problem(problem, seeds=(20260529,), budget=8, qpso_mean=problem.best_known)
    rows_b, summaries_b = run_problem(problem, seeds=(20260529,), budget=8, qpso_mean=problem.best_known)

    comparable_rows_a = [{k: v for k, v in row.items() if k != "runtime"} for row in rows_a]
    comparable_rows_b = [{k: v for k, v in row.items() if k != "runtime"} for row in rows_b]
    assert comparable_rows_a == comparable_rows_b
    comparable_summaries_a = [
        {k: v for k, v in summary.__dict__.items() if k != "avg_runtime"} for summary in summaries_a
    ]
    comparable_summaries_b = [
        {k: v for k, v in summary.__dict__.items() if k != "avg_runtime"} for summary in summaries_b
    ]
    assert comparable_summaries_a == comparable_summaries_b


def test_lagrangian_multipliers_are_finite():
    problem = _problem()

    multipliers = lagrangian_multipliers(problem.values, problem.weights, problem.capacities, iterations=5)

    assert multipliers.shape == (problem.dim,)
    assert np.all(np.isfinite(multipliers))
    assert np.all(multipliers >= 0.0)
