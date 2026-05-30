from __future__ import annotations

import argparse
import copy
import json
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from ..engine.builders import solverBuilders
from ..engine.repository import ProblemRepository
from ..problem import ProblemModel, buildProblemRegistry, problemBuilders
from ..solver.registry import SolverRegistry
from ..tools.solver_config_loader import SolverConfigLoader


ITEM_EVAL_VARIANTS: dict[str, dict[str, Any]] = {
    "BASE": {},
    "CORE_SCORE_CP": {
        "item_eval_method": "core_score_cp",
        "guided_binary_enabled": False,
    },
    "FREQ_GATED_V2": {
        "item_eval_method": "freq_gated_v2",
        "guided_binary_enabled": False,
    },
    "FREQ_GATED_V2_GBC": {
        "item_eval_method": "freq_gated_v2_gbc",
        "guided_binary_enabled": True,
        "guided_lambda_lp": 0.10,
        "guided_lambda_bucket": 0.05,
        "guided_lambda_slack": 0.05,
    },
}


@dataclass(frozen=True)
class ItemEvalSummary:
    dataset: str
    problem_id: str
    variant: str
    total_runs: int
    feasible_rate: float
    mean_objective: float
    std_objective: float
    best_objective: int
    worst_objective: int
    pdev: float
    mean_runtime: float
    delta_vs_base: float | None
    pdev_delta_vs_base: float | None


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


def _or_datasets(problem_root: Path) -> tuple[str, ...]:
    return tuple(sorted(path.name for path in (problem_root / "mkp").iterdir() if path.is_dir() and path.name.startswith("OR")))


def sample_or_problems(
    *,
    problem_root: Path = Path("configs/problems"),
    sample_per_dataset: int = 2,
    sample_seed: int = 20260530,
    datasets: tuple[str, ...] | None = None,
) -> tuple[tuple[str, str], ...]:
    selected: list[tuple[str, str]] = []
    rng = np.random.default_rng(int(sample_seed))
    dataset_names = datasets or _or_datasets(problem_root)
    for dataset in dataset_names:
        files = sorted((problem_root / "mkp" / dataset).glob("*.yaml"))
        problem_ids = [path.stem for path in files]
        if not problem_ids:
            continue
        count = min(int(sample_per_dataset), len(problem_ids))
        indices = sorted(rng.choice(len(problem_ids), size=count, replace=False).tolist())
        for idx in indices:
            selected.append((dataset, problem_ids[idx]))
    return tuple(selected)


def _base_config(max_iterations: int) -> dict[str, Any]:
    config = SolverConfigLoader().load("brlsmasca_rl_rc_numba", param_set_index=20)
    config = copy.deepcopy(config)
    config["stop_condition"] = dict(config["stop_condition"])
    config["stop_condition"]["max_iterations"] = int(max_iterations)
    config["params"] = dict(config["params"])
    return config


def _row_key(row: dict[str, Any]) -> tuple[str, str, str, int]:
    return (str(row["dataset"]), str(row["problem_id"]), str(row["variant"]), int(row["seed"]))


def _load_existing_rows(path: Path) -> dict[tuple[str, str, str, int], dict[str, Any]]:
    if not path.exists():
        return {}
    rows: dict[tuple[str, str, str, int], dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        rows[_row_key(row)] = row
    return rows


def _run_variant(
    problem: ProblemModel,
    *,
    dataset: str,
    variant: str,
    seed: int,
    max_iterations: int,
    registry: SolverRegistry,
) -> dict[str, Any]:
    config = _base_config(max_iterations)
    config["params"].update(ITEM_EVAL_VARIANTS[variant])
    config["run_seed"] = int(seed)
    solver = registry.create(str(config["solver_id"]))
    t0 = time.perf_counter()
    result = solver.solve(problem, config, np.random.default_rng(int(seed)))
    wall_runtime = time.perf_counter() - t0
    feasible = bool(result.feasible) and bool(np.all(result.best_solution @ problem.weights <= problem.capacities))
    return {
        "dataset": dataset,
        "problem_id": problem.problem_id,
        "variant": variant,
        "seed": int(seed),
        "max_iterations": int(max_iterations),
        "objective": int(result.best_objective),
        "feasible": feasible,
        "runtime": float(result.runtime),
        "wall_runtime": float(wall_runtime),
        "metadata": result.metadata,
    }


def _summaries(rows: list[dict[str, Any]], problems: dict[tuple[str, str], ProblemModel]) -> list[ItemEvalSummary]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault((str(row["dataset"]), str(row["problem_id"]), str(row["variant"])), []).append(row)

    preliminary: dict[tuple[str, str, str], ItemEvalSummary] = {}
    for key, key_rows in sorted(grouped.items()):
        dataset, problem_id, variant = key
        problem = problems[(dataset, problem_id)]
        feasible_rows = [row for row in key_rows if bool(row["feasible"])]
        objectives = [int(row["objective"]) for row in feasible_rows]
        feasible_rate = len(feasible_rows) / len(key_rows) if key_rows else 0.0
        if objectives:
            mean_objective = float(statistics.fmean(objectives))
            std_objective = float(np.std(np.asarray(objectives, dtype=np.float64)))
            best_objective = max(objectives)
            worst_objective = min(objectives)
        else:
            mean_objective = 0.0
            std_objective = 0.0
            best_objective = 0
            worst_objective = 0
        pdev = 100.0 * (float(problem.best_known) - mean_objective) / float(problem.best_known)
        preliminary[key] = ItemEvalSummary(
            dataset=dataset,
            problem_id=problem_id,
            variant=variant,
            total_runs=len(key_rows),
            feasible_rate=feasible_rate,
            mean_objective=mean_objective,
            std_objective=std_objective,
            best_objective=best_objective,
            worst_objective=worst_objective,
            pdev=pdev,
            mean_runtime=float(statistics.fmean(float(row["runtime"]) for row in key_rows)),
            delta_vs_base=None,
            pdev_delta_vs_base=None,
        )

    output: list[ItemEvalSummary] = []
    for summary in preliminary.values():
        base = preliminary.get((summary.dataset, summary.problem_id, "BASE"))
        if base is None or summary.variant == "BASE":
            output.append(summary)
        else:
            output.append(
                ItemEvalSummary(
                    **{
                        **asdict(summary),
                        "delta_vs_base": summary.mean_objective - base.mean_objective,
                        "pdev_delta_vs_base": summary.pdev - base.pdev,
                    }
                )
            )
    return sorted(output, key=lambda item: (item.dataset, item.problem_id, item.variant))


def _ranking(summaries: list[ItemEvalSummary]) -> list[dict[str, Any]]:
    by_variant: dict[str, list[ItemEvalSummary]] = {}
    for summary in summaries:
        by_variant.setdefault(summary.variant, []).append(summary)
    base_variant = by_variant.get("BASE", [])
    expected_problem_count = len(base_variant)
    ranking = []
    for variant, variant_summaries in by_variant.items():
        if variant == "BASE":
            continue
        complete = len(variant_summaries) == expected_problem_count
        not_below_base = sum(1 for item in variant_summaries if (item.delta_vs_base or 0.0) >= 0.0)
        pdev_regressions = sum(1 for item in variant_summaries if (item.pdev_delta_vs_base or 0.0) > 0.01)
        mean_delta = statistics.fmean(float(item.delta_vs_base or 0.0) for item in variant_summaries)
        mean_pdev_delta = statistics.fmean(float(item.pdev_delta_vs_base or 0.0) for item in variant_summaries)
        ranking.append(
            {
                "variant": variant,
                "complete": complete,
                "problems": len(variant_summaries),
                "not_below_base": not_below_base,
                "pdev_regressions_gt_001": pdev_regressions,
                "mean_delta_vs_base": mean_delta,
                "mean_pdev_delta_vs_base": mean_pdev_delta,
            }
        )
    return sorted(
        ranking,
        key=lambda item: (
            -float(item["mean_delta_vs_base"]),
            float(item["mean_pdev_delta_vs_base"]),
            str(item["variant"]),
        ),
    )


def run_experiment(
    *,
    output_root: Path,
    sample_seed: int,
    sample_per_dataset: int,
    max_iterations: int,
    repeat: int,
    seed_start: int,
    variants: tuple[str, ...],
    datasets: tuple[str, ...] | None,
    max_runs: int | None,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    rows_path = output_root / "runs.jsonl"
    existing = _load_existing_rows(rows_path)
    repository = _problem_repository()
    registry = _solver_registry()
    selected = sample_or_problems(
        sample_seed=sample_seed,
        sample_per_dataset=sample_per_dataset,
        datasets=datasets,
    )
    problems = {(dataset, problem_id): repository.load(dataset, problem_id) for dataset, problem_id in selected}
    seeds = tuple(range(int(seed_start), int(seed_start) + int(repeat)))
    run_count = 0
    with rows_path.open("a", encoding="utf-8") as fh:
        for dataset, problem_id in selected:
            problem = problems[(dataset, problem_id)]
            for variant in variants:
                for seed in seeds:
                    key = (dataset, problem_id, variant, int(seed))
                    if key in existing:
                        continue
                    row = _run_variant(
                        problem,
                        dataset=dataset,
                        variant=variant,
                        seed=int(seed),
                        max_iterations=max_iterations,
                        registry=registry,
                    )
                    fh.write(json.dumps(row, sort_keys=True) + "\n")
                    fh.flush()
                    existing[key] = row
                    run_count += 1
                    if max_runs is not None and run_count >= max_runs:
                        break
                if max_runs is not None and run_count >= max_runs:
                    break
            if max_runs is not None and run_count >= max_runs:
                break

    rows = list(existing.values())
    relevant_rows = [
        row
        for row in rows
        if (str(row["dataset"]), str(row["problem_id"])) in problems
        and str(row["variant"]) in variants
        and int(row["seed"]) in seeds
    ]
    summaries = _summaries(relevant_rows, problems)
    payload = {
        "selected_problems": [{"dataset": dataset, "problem_id": problem_id} for dataset, problem_id in selected],
        "sample_seed": int(sample_seed),
        "sample_per_dataset": int(sample_per_dataset),
        "max_iterations": int(max_iterations),
        "seeds": list(seeds),
        "variants": list(variants),
        "completed_runs": len(relevant_rows),
        "expected_runs": len(selected) * len(variants) * len(seeds),
        "summaries": [asdict(summary) for summary in summaries],
        "ranking": _ranking(summaries),
    }
    (output_root / "summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run OR item-evaluation method comparison.")
    parser.add_argument("--output-root", type=Path, default=Path("output/mkp_item_eval_or_sample"))
    parser.add_argument("--sample-seed", type=int, default=20260530)
    parser.add_argument("--sample-per-dataset", type=int, default=2)
    parser.add_argument("--max-iterations", type=int, default=5000)
    parser.add_argument("--repeat", type=int, default=20)
    parser.add_argument("--seed-start", type=int, default=1000)
    parser.add_argument("--variant", action="append", choices=tuple(ITEM_EVAL_VARIANTS))
    parser.add_argument("--dataset", action="append", help="Restrict to an OR dataset, e.g. OR5x500")
    parser.add_argument("--max-runs", type=int, default=None, help="Stop after N newly executed runs; resume later.")
    args = parser.parse_args(argv)
    payload = run_experiment(
        output_root=args.output_root,
        sample_seed=args.sample_seed,
        sample_per_dataset=args.sample_per_dataset,
        max_iterations=args.max_iterations,
        repeat=args.repeat,
        seed_start=args.seed_start,
        variants=tuple(args.variant or ITEM_EVAL_VARIANTS.keys()),
        datasets=tuple(args.dataset) if args.dataset else None,
        max_runs=args.max_runs,
    )
    print(
        json.dumps(
            {
                "output": str(args.output_root / "summary.json"),
                "completed_runs": payload["completed_runs"],
                "expected_runs": payload["expected_runs"],
                "ranking": payload["ranking"][:5],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
