from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from numba import njit

from ..engine.repository import ProblemRepository
from ..problem import ProblemModel, buildProblemRegistry, problemBuilders
from ..solver.BSCASMA_rl_rc_numba import _build_lp_rc_item_eval_payload


DEFAULT_PROBLEMS = (
    ("OR5x250", "OR5x250-0.25_2", 61470.0),
    ("OR5x500", "OR5x500-0.25_4", 120740.3),
    ("OR10x500", "OR10x500-0.25_2", 119148.5),
)


@dataclass(frozen=True)
class ScaffoldSummary:
    variant: str
    problem_id: str
    mean_objective: float
    std_objective: float
    best_objective: int
    worst_objective: int
    pdev: float
    positive_qpso_gap: float
    avg_runtime: float


def _normalize(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64).ravel()
    finite = np.isfinite(arr)
    if not np.any(finite):
        return np.zeros(arr.size, dtype=np.float64)
    safe = arr.copy()
    min_value = float(np.min(safe[finite]))
    max_value = float(np.max(safe[finite]))
    safe[~finite & (safe > 0.0)] = max_value
    safe[~finite & (safe <= 0.0)] = min_value
    if math.isclose(max_value, min_value):
        return np.zeros(arr.size, dtype=np.float64)
    return (safe - min_value) / (max_value - min_value)


def _safe_ratio(values: np.ndarray, denom: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.asarray(values, dtype=np.float64) / np.asarray(denom, dtype=np.float64)
    positive = np.asarray(values, dtype=np.float64) > 0.0
    ratio = np.where((denom <= 0.0) & positive, np.inf, ratio)
    return np.nan_to_num(ratio, nan=0.0, posinf=np.finfo(np.float64).max, neginf=0.0)


def lagrangian_multipliers(
    values: np.ndarray,
    weights: np.ndarray,
    capacities: np.ndarray,
    *,
    iterations: int = 200,
    step0: float = 2.0,
) -> np.ndarray:
    dim = int(capacities.size)
    lam = np.zeros(dim, dtype=np.float64)
    best_lam = lam.copy()
    best_dual = np.inf
    capacities_f = np.asarray(capacities, dtype=np.float64)
    weights_f = np.asarray(weights, dtype=np.float64)
    values_f = np.asarray(values, dtype=np.float64)
    for t in range(int(iterations)):
        net = values_f - weights_f @ lam
        x = (net > 0.0).astype(np.float64)
        usage = weights_f.T @ x
        dual_val = float(capacities_f @ lam + np.maximum(net, 0.0).sum())
        if dual_val < best_dual:
            best_dual = dual_val
            best_lam = lam.copy()
        subgrad = usage - capacities_f
        scaled = subgrad / (capacities_f + 1.0e-12)
        norm = float(np.linalg.norm(scaled))
        if norm < 1.0e-12:
            break
        step = step0 / math.sqrt(float(t + 1))
        lam = np.maximum(0.0, lam + step * scaled)
    return best_lam


def build_score_variants(problem: ProblemModel) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    payload = _build_lp_rc_item_eval_payload(
        problem.values,
        problem.weights,
        problem.capacities,
        eval_group_decimals=1,
        eval_rc_eps=1.0e-9,
        eval_x_eps=1.0e-9,
    )
    values = np.asarray(problem.values, dtype=np.float64)
    weights = np.asarray(problem.weights, dtype=np.float64)
    capacities = np.asarray(problem.capacities, dtype=np.float64)
    density_cost = weights @ (1.0 / (capacities + 1.0e-12))
    cnd = _safe_ratio(values, density_cost)
    dual_price = np.asarray(payload["dual_price"], dtype=np.float64)
    dual_cost = weights @ dual_price
    dual = _safe_ratio(values, dual_cost)
    reduced_pos = np.maximum(np.asarray(payload["reduced_cost"], dtype=np.float64), 0.0)
    x_lp = np.asarray(payload["x_lp"], dtype=np.float64)
    bucket = np.asarray(payload["bucket"], dtype=np.int64)
    core_flag = (bucket == 1).astype(np.float64)
    rc = 0.5 * _normalize(reduced_pos) + 0.5 * x_lp
    hyb = (
        0.35 * _normalize(dual)
        + 0.25 * _normalize(reduced_pos)
        + 0.25 * x_lp
        + 0.15 * core_flag
    )
    lag = _safe_ratio(values, weights @ lagrangian_multipliers(problem.values, problem.weights, problem.capacities))
    scores = {
        "CURRENT": np.asarray(payload["efficiency"], dtype=np.float64),
        "CND": cnd,
        "DUAL": dual,
        "RC": rc,
        "HYB": hyb,
        "LAG": lag,
    }
    variants: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    current_order = np.asarray(payload["base_order"], dtype=np.int64)
    variants["CURRENT-RANK"] = (scores["CURRENT"], current_order)
    item_ids = np.arange(problem.items, dtype=np.int64)
    for name in ("CND", "DUAL", "RC", "HYB", "LAG"):
        order = np.ascontiguousarray(np.lexsort((item_ids, -scores[name])).astype(np.int64))
        variants[f"{name}-rank"] = (scores[name], order)
        variants[f"{name}-weight"] = (scores[name], order)
    return variants


@njit(cache=True)
def _batch_repair_rank_objectives(
    raw_candidates: np.ndarray,
    values: np.ndarray,
    weights: np.ndarray,
    capacities: np.ndarray,
    order: np.ndarray,
) -> np.ndarray:
    runs, items = raw_candidates.shape
    dim = capacities.size
    objectives = np.zeros(runs, dtype=np.int64)
    sol = np.zeros(items, dtype=np.float64)
    resource = np.zeros(dim, dtype=np.float64)
    for r in range(runs):
        for d in range(dim):
            resource[d] = 0.0
        fit = 0
        for j in range(items):
            bit = 1.0 if raw_candidates[r, j] != 0 else 0.0
            sol[j] = bit
            if bit == 1.0:
                fit += int(values[j])
                for d in range(dim):
                    resource[d] += weights[j, d]
        for pos in range(items - 1, -1, -1):
            over = False
            for d in range(dim):
                if resource[d] > capacities[d]:
                    over = True
                    break
            if not over:
                break
            j = int(order[pos])
            if sol[j] == 1.0:
                sol[j] = 0.0
                fit -= int(values[j])
                for d in range(dim):
                    resource[d] -= weights[j, d]
        for pos in range(items):
            j = int(order[pos])
            if sol[j] == 0.0:
                ok = True
                for d in range(dim):
                    if resource[d] + weights[j, d] > capacities[d]:
                        ok = False
                        break
                if ok:
                    sol[j] = 1.0
                    fit += int(values[j])
                    for d in range(dim):
                        resource[d] += weights[j, d]
        objectives[r] = fit
    return objectives


@njit(cache=True)
def _batch_repair_weight_objectives(
    raw_candidates: np.ndarray,
    values: np.ndarray,
    weights: np.ndarray,
    capacities: np.ndarray,
    score: np.ndarray,
) -> np.ndarray:
    runs, items = raw_candidates.shape
    dim = capacities.size
    objectives = np.zeros(runs, dtype=np.int64)
    sol = np.zeros(items, dtype=np.float64)
    resource = np.zeros(dim, dtype=np.float64)
    for r in range(runs):
        for d in range(dim):
            resource[d] = 0.0
        fit = 0
        for j in range(items):
            bit = 1.0 if raw_candidates[r, j] != 0 else 0.0
            sol[j] = bit
            if bit == 1.0:
                fit += int(values[j])
                for d in range(dim):
                    resource[d] += weights[j, d]
        while True:
            over = False
            for d in range(dim):
                if resource[d] > capacities[d]:
                    over = True
                    break
            if not over:
                break
            best_j = -1
            best_merit = 1.0e300
            for j in range(items):
                if sol[j] != 1.0:
                    continue
                stress = 0.0
                for d in range(dim):
                    violation = resource[d] - capacities[d]
                    if violation < 0.0:
                        violation = 0.0
                    stress += (1.0 + violation / (float(capacities[d]) + 1.0e-12)) * (
                        float(weights[j, d]) / (float(capacities[d]) + 1.0e-12)
                    )
                merit = (score[j] + 1.0e-12) / (stress + 1.0e-12)
                if merit < best_merit or (merit == best_merit and j > best_j):
                    best_merit = merit
                    best_j = j
            if best_j < 0:
                break
            sol[best_j] = 0.0
            fit -= int(values[best_j])
            for d in range(dim):
                resource[d] -= weights[best_j, d]
        while True:
            best_j = -1
            best_merit = -1.0e300
            for j in range(items):
                if sol[j] != 0.0:
                    continue
                feasible = True
                tight_penalty = 0.0
                for d in range(dim):
                    remaining = capacities[d] - resource[d]
                    if weights[j, d] > remaining:
                        feasible = False
                        break
                    tight_penalty += float(weights[j, d]) / (remaining + 1.0e-12)
                if not feasible:
                    continue
                merit = (score[j] + 1.0e-12) / (1.0 + tight_penalty)
                if merit > best_merit or (merit == best_merit and j < best_j):
                    best_merit = merit
                    best_j = j
            if best_j < 0:
                break
            sol[best_j] = 1.0
            fit += int(values[best_j])
            for d in range(dim):
                resource[d] += weights[best_j, d]
        objectives[r] = fit
    return objectives


def run_problem(
    problem: ProblemModel,
    *,
    seeds: Iterable[int],
    budget: int,
    qpso_mean: float,
) -> tuple[list[dict[str, object]], list[ScaffoldSummary]]:
    variants = build_score_variants(problem)
    rows: list[dict[str, object]] = []
    summaries: list[ScaffoldSummary] = []
    for variant, (score, order) in variants.items():
        objectives: list[int] = []
        runtimes: list[float] = []
        mode = "weight" if variant.endswith("-weight") else "rank"
        for seed in seeds:
            rng = np.random.default_rng(int(seed))
            raw = rng.integers(0, 2, size=(int(budget), problem.items), dtype=np.int8)
            t0 = time.perf_counter()
            if mode == "weight":
                repaired = _batch_repair_weight_objectives(
                    raw,
                    np.asarray(problem.values, dtype=np.int64),
                    np.asarray(problem.weights, dtype=np.int64),
                    np.asarray(problem.capacities, dtype=np.int64),
                    np.asarray(score, dtype=np.float64),
                )
            else:
                repaired = _batch_repair_rank_objectives(
                    raw,
                    np.asarray(problem.values, dtype=np.int64),
                    np.asarray(problem.weights, dtype=np.int64),
                    np.asarray(problem.capacities, dtype=np.int64),
                    np.asarray(order, dtype=np.int64),
                )
            runtime = time.perf_counter() - t0
            objective = int(np.max(repaired))
            objectives.append(objective)
            runtimes.append(runtime)
            rows.append(
                {
                    "problem_id": problem.problem_id,
                    "variant": variant,
                    "seed": int(seed),
                    "budget": int(budget),
                    "objective": objective,
                    "runtime": runtime,
                }
            )
        arr = np.asarray(objectives, dtype=np.float64)
        mean = float(np.mean(arr))
        pdev = 100.0 * (float(problem.best_known) - mean) / float(problem.best_known)
        summaries.append(
            ScaffoldSummary(
                variant=variant,
                problem_id=problem.problem_id,
                mean_objective=mean,
                std_objective=float(np.std(arr)),
                best_objective=int(np.max(arr)),
                worst_objective=int(np.min(arr)),
                pdev=pdev,
                positive_qpso_gap=max(0.0, float(qpso_mean) - mean),
                avg_runtime=float(np.mean(np.asarray(runtimes, dtype=np.float64))),
            )
        )
    return rows, summaries


def _problem_repository() -> ProblemRepository:
    repo_root = Path(__file__).resolve().parents[1]
    return ProblemRepository(
        config_root=repo_root / "configs/problems",
        registry=buildProblemRegistry(problemBuilders()),
    )


def _parse_problem_specs(values: list[str] | None) -> tuple[tuple[str, str, float], ...]:
    if not values:
        return DEFAULT_PROBLEMS
    specs = []
    for value in values:
        dataset, problem_id, qpso_mean = value.split(":")
        specs.append((dataset, problem_id, float(qpso_mean)))
    return tuple(specs)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run MKP score-layer random+repair scaffold.")
    parser.add_argument("--problem", action="append", help="dataset:problem_id:qpso_mean")
    parser.add_argument("--seed-start", type=int, default=20260529)
    parser.add_argument("--seed-count", type=int, default=10)
    parser.add_argument("--budget", type=int, default=1000)
    parser.add_argument("--output-root", type=Path, default=Path("output/mkp_score_scaffold"))
    args = parser.parse_args(argv)

    repository = _problem_repository()
    seeds = tuple(range(args.seed_start, args.seed_start + args.seed_count))
    all_rows: list[dict[str, object]] = []
    all_summaries: list[ScaffoldSummary] = []
    for dataset, problem_id, qpso_mean in _parse_problem_specs(args.problem):
        problem = repository.load(dataset, problem_id)
        rows, summaries = run_problem(problem, seeds=seeds, budget=args.budget, qpso_mean=qpso_mean)
        all_rows.extend(rows)
        all_summaries.extend(summaries)

    by_variant: dict[str, float] = {}
    for summary in all_summaries:
        by_variant.setdefault(summary.variant, 0.0)
        by_variant[summary.variant] += summary.positive_qpso_gap
    ranking = sorted(
        ({"variant": variant, "combined_positive_qpso_gap": gap} for variant, gap in by_variant.items()),
        key=lambda item: (float(item["combined_positive_qpso_gap"]), str(item["variant"])),
    )

    args.output_root.mkdir(parents=True, exist_ok=True)
    payload = {
        "seeds": list(seeds),
        "budget": int(args.budget),
        "rows": all_rows,
        "summaries": [asdict(summary) for summary in all_summaries],
        "ranking": ranking,
    }
    (args.output_root / "summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output_root / "summary.json"), "ranking": ranking[:5]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
