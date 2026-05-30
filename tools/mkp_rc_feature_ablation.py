from __future__ import annotations

import argparse
import copy
import json
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from ruamel.yaml import YAML

from ..engine.builders import solverBuilders
from ..engine.repository import ProblemRepository
from ..problem import ProblemModel, buildProblemRegistry, problemBuilders
from ..solver.registry import SolverRegistry
from ..tools.solver_config_loader import SolverConfigLoader


DEFAULT_GUARD_PROBLEMS = (
    ("OR5x250", "OR5x250-0.25_2"),
    ("OR5x500", "OR5x500-0.25_4"),
    ("OR10x500", "OR10x500-0.25_2"),
)


VARIANT_OVERRIDES: dict[str, dict[str, Any]] = {
    "BASE": {},
    "GBC": {"guided_binary_enabled": True},
    "LS": {"local_search_enabled": True},
    "PR": {"archive_pr_enabled": True},
    "GBC+LS": {"guided_binary_enabled": True, "local_search_enabled": True},
    "GBC+PR": {"guided_binary_enabled": True, "archive_pr_enabled": True},
    "LS+PR": {"local_search_enabled": True, "archive_pr_enabled": True},
    "FULL": {
        "guided_binary_enabled": True,
        "local_search_enabled": True,
        "archive_pr_enabled": True,
    },
}


@dataclass(frozen=True)
class AblationSummary:
    variant: str
    problem_id: str
    mean_objective: float
    std_objective: float
    best_objective: int
    worst_objective: int
    pdev: float
    positive_qpso_gap: float
    feasible_rate: float
    avg_runtime: float


def _problem_repository() -> ProblemRepository:
    repo_root = Path(__file__).resolve().parents[1]
    return ProblemRepository(
        config_root=repo_root / "configs/problems",
        registry=buildProblemRegistry(problemBuilders()),
    )


def _solver_registry() -> SolverRegistry:
    registry = SolverRegistry()
    for solver_id, builder in solverBuilders().items():
        registry.register(solver_id, builder)
    return registry


def _load_qpso_means(path: Path = Path("cli/exp/exp_cfg.yaml")) -> dict[str, float]:
    yaml = YAML(typ="safe")
    data = yaml.load(path.read_text(encoding="utf-8"))
    means: dict[str, float] = {}
    for dataset in data.get("dataset_settings", []):
        for problem in dataset.get("problems", []):
            problem_id = str(problem["problem"])
            for baseline in problem.get("base_line", []):
                if str(baseline.get("name", "")).strip().lower() == "qpso":
                    means[problem_id] = float(baseline["Mean"])
    return means


def _load_base_config(max_iterations: int) -> dict[str, Any]:
    config = SolverConfigLoader().load("brlsmasca_rl_rc_numba", param_set_index=20)
    config = copy.deepcopy(config)
    config["stop_condition"] = dict(config["stop_condition"])
    config["stop_condition"]["max_iterations"] = int(max_iterations)
    config["params"] = dict(config["params"])
    return config


def _run_one(
    problem: ProblemModel,
    *,
    seed: int,
    variant: str,
    max_iterations: int,
    registry: SolverRegistry,
) -> dict[str, Any]:
    config = _load_base_config(max_iterations)
    config["params"].update(VARIANT_OVERRIDES[variant])
    config["run_seed"] = int(seed)
    solver = registry.create(str(config["solver_id"]))
    t0 = time.perf_counter()
    result = solver.solve(problem, config, np.random.default_rng(int(seed)))
    wall = time.perf_counter() - t0
    return {
        "variant": variant,
        "problem_id": problem.problem_id,
        "seed": int(seed),
        "objective": int(result.best_objective),
        "feasible": bool(result.feasible),
        "runtime": float(result.runtime),
        "wall_runtime": wall,
        "metadata": result.metadata,
    }


def summarize_rows(
    rows: Iterable[dict[str, Any]],
    *,
    problem: ProblemModel,
    qpso_mean: float,
) -> list[AblationSummary]:
    by_variant: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_variant.setdefault(str(row["variant"]), []).append(row)
    summaries = []
    for variant, variant_rows in sorted(by_variant.items()):
        objectives = [int(row["objective"]) for row in variant_rows if bool(row["feasible"])]
        feasible_rate = len(objectives) / len(variant_rows) if variant_rows else 0.0
        if objectives:
            mean = float(statistics.fmean(objectives))
            std = float(np.std(np.asarray(objectives, dtype=np.float64)))
            best = max(objectives)
            worst = min(objectives)
        else:
            mean = 0.0
            std = 0.0
            best = 0
            worst = 0
        pdev = 100.0 * (float(problem.best_known) - mean) / float(problem.best_known)
        summaries.append(
            AblationSummary(
                variant=variant,
                problem_id=problem.problem_id,
                mean_objective=mean,
                std_objective=std,
                best_objective=best,
                worst_objective=worst,
                pdev=pdev,
                positive_qpso_gap=max(0.0, float(qpso_mean) - mean),
                feasible_rate=feasible_rate,
                avg_runtime=float(statistics.fmean(float(row["runtime"]) for row in variant_rows)),
            )
        )
    return summaries


def run_ablation(
    *,
    problems: tuple[tuple[str, str], ...] = DEFAULT_GUARD_PROBLEMS,
    seeds: tuple[int, ...] = tuple(range(1000, 1010)),
    max_iterations: int = 1000,
    variants: tuple[str, ...] = tuple(VARIANT_OVERRIDES),
) -> dict[str, Any]:
    repository = _problem_repository()
    registry = _solver_registry()
    qpso_means = _load_qpso_means()
    all_rows: list[dict[str, Any]] = []
    all_summaries: list[AblationSummary] = []
    for dataset, problem_id in problems:
        problem = repository.load(dataset, problem_id)
        problem_rows = []
        for variant in variants:
            for seed in seeds:
                row = _run_one(
                    problem,
                    seed=seed,
                    variant=variant,
                    max_iterations=max_iterations,
                    registry=registry,
                )
                all_rows.append(row)
                problem_rows.append(row)
        all_summaries.extend(
            summarize_rows(problem_rows, problem=problem, qpso_mean=qpso_means[problem_id])
        )

    combined_gap: dict[str, float] = {}
    baseline_by_problem = {
        summary.problem_id: summary
        for summary in all_summaries
        if summary.variant == "BASE"
    }
    guard: dict[str, dict[str, float | int]] = {}
    for summary in all_summaries:
        combined_gap.setdefault(summary.variant, 0.0)
        combined_gap[summary.variant] += summary.positive_qpso_gap
        base = baseline_by_problem.get(summary.problem_id)
        if summary.variant != "BASE" and base is not None:
            entry = guard.setdefault(summary.variant, {"not_below_base": 0, "pdev_regressions": 0})
            if summary.mean_objective >= base.mean_objective:
                entry["not_below_base"] = int(entry["not_below_base"]) + 1
            if summary.pdev - base.pdev > 0.02:
                entry["pdev_regressions"] = int(entry["pdev_regressions"]) + 1

    ranking = sorted(
        (
            {
                "variant": variant,
                "combined_positive_qpso_gap": gap,
                **guard.get(variant, {}),
            }
            for variant, gap in combined_gap.items()
        ),
        key=lambda item: (float(item["combined_positive_qpso_gap"]), str(item["variant"])),
    )
    return {
        "seeds": list(seeds),
        "max_iterations": int(max_iterations),
        "variants": list(variants),
        "rows": all_rows,
        "summaries": [asdict(summary) for summary in all_summaries],
        "ranking": ranking,
    }


def _parse_problems(values: list[str] | None) -> tuple[tuple[str, str], ...]:
    if not values:
        return DEFAULT_GUARD_PROBLEMS
    parsed = []
    for value in values:
        dataset, problem_id = value.split(":")
        parsed.append((dataset, problem_id))
    return tuple(parsed)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run BRLSMASCARLRC feature ablation.")
    parser.add_argument("--problem", action="append", help="dataset:problem_id")
    parser.add_argument("--seed-start", type=int, default=1000)
    parser.add_argument("--seed-count", type=int, default=10)
    parser.add_argument("--max-iterations", type=int, default=1000)
    parser.add_argument("--variant", action="append", choices=tuple(VARIANT_OVERRIDES))
    parser.add_argument("--output-root", type=Path, default=Path("output/mkp_rc_feature_ablation"))
    args = parser.parse_args(argv)

    payload = run_ablation(
        problems=_parse_problems(args.problem),
        seeds=tuple(range(args.seed_start, args.seed_start + args.seed_count)),
        max_iterations=args.max_iterations,
        variants=tuple(args.variant or VARIANT_OVERRIDES.keys()),
    )
    args.output_root.mkdir(parents=True, exist_ok=True)
    output_path = args.output_root / "summary.json"
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output_path), "ranking": payload["ranking"][:5]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
