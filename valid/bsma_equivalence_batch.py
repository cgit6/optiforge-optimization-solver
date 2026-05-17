"""WEISH 全題庫批次：舊版 BSMA vs BSMACore 串流等價驗證。"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from .bsma_equivalence import (
    BSMA_DEFAULT_POP_SIZE,
    max_outer_iterations_for_budget,
    verify_equivalence_streaming,
)
from ..cli.convert import getConverter
from ..converter import transformToYaml
from ..engine.repository import ProblemRepository
from ..problem import buildProblemRegistry, problemBuilders


def default_weish_problem_ids() -> list[str]:
    return [f"weish{i:02d}" for i in range(1, 31)]


def run_weish_equivalence_suite(
    *,
    repo_root: Path,
    seed: int = 101,
    budget: int = 100_000,
    problem_ids: list[str] | None = None,
    output_dir: Path | None = None,
    ensure_yaml: bool = True,
    dataset: str = "WEISH",
) -> dict[str, Any]:
    """逐題串流驗證；預設 budget=100_000 → max_iter=4999（pop_size=20）。"""
    if problem_ids is None:
        problem_ids = default_weish_problem_ids()
    if output_dir is None:
        output_dir = repo_root / "output/bsma_weish_suite"
    trace_dir = output_dir / "traces"
    output_dir.mkdir(parents=True, exist_ok=True)
    trace_dir.mkdir(parents=True, exist_ok=True)

    max_iter = max_outer_iterations_for_budget(budget=budget, pop_size=BSMA_DEFAULT_POP_SIZE)
    eval_upper_bound = BSMA_DEFAULT_POP_SIZE * (max_iter + 1)
    repository = ProblemRepository(
        config_root=repo_root / "configs/problems",
        registry=buildProblemRegistry(problemBuilders()),
    )

    rows: list[dict[str, Any]] = []
    t_suite = time.perf_counter()
    for problem_id in problem_ids:
        if ensure_yaml:
            transformToYaml(
                repo_root=repo_root,
                dataset=dataset,
                problem_id=problem_id,
                parser=getConverter(dataset.lower()),
            )
        problem = repository.load(dataset, problem_id)
        t0 = time.perf_counter()
        report = verify_equivalence_streaming(
            repo_root=repo_root,
            dataset=dataset,
            problem_id=problem_id,
            seed=seed,
            max_iterations=max_iter,
            trace_dir=trace_dir,
            problem=problem,
        )
        elapsed = time.perf_counter() - t0
        rows.append(
            {
                "problem_id": problem_id,
                "trace_match": report.trace_match,
                "final_solution_match": report.final_solution_match,
                "final_objective_old": report.final_objective_old,
                "final_objective_new": report.final_objective_new,
                "trace_length_old": report.trace_length_old,
                "trace_length_new": report.trace_length_new,
                "new_stop_reason": report.new_stop_reason,
                "new_reported_eval_count": report.new_reported_eval_count,
                "budget_requested": budget,
                "max_iterations": max_iter,
                "pop_size": BSMA_DEFAULT_POP_SIZE,
                "fitness_eval_upper_bound_formula": eval_upper_bound,
                "seconds": round(elapsed, 3),
                "first_mismatch_index": report.first_mismatch_index,
            }
        )

    summary: dict[str, Any] = {
        "dataset": dataset,
        "seed": seed,
        "budget": budget,
        "max_iterations": max_iter,
        "pop_size": BSMA_DEFAULT_POP_SIZE,
        "eval_upper_bound_pop_times_iter_plus_one": eval_upper_bound,
        "problem_ids": list(problem_ids),
        "all_pass": all(r["trace_match"] and r["final_solution_match"] for r in rows),
        "total_seconds": round(time.perf_counter() - t_suite, 3),
        "results": rows,
    }

    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        f"WEISH BSMA equivalence suite",
        f"seed={seed} budget={budget} max_iter={max_iter} pop={BSMA_DEFAULT_POP_SIZE}",
        f"all_pass={summary['all_pass']} total_seconds={summary['total_seconds']}",
        "",
    ]
    for r in rows:
        status = "PASS" if r["trace_match"] and r["final_solution_match"] else "FAIL"
        lines.append(
            f"{r['problem_id']}: {status} obj_old={r['final_objective_old']} obj_new={r['final_objective_new']} "
            f"trace_len={r['trace_length_old']} stop={r['new_stop_reason']} reported_eval={r['new_reported_eval_count']} "
            f"t={r['seconds']}s"
        )
    (output_dir / "summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def _parse_problem_list(raw: str | None) -> list[str] | None:
    if raw is None or not raw.strip():
        return None
    return [p.strip() for p in raw.split(",") if p.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="WEISH weish01..30 BSMA strict equivalence (streaming trace).")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="專案根目錄（含 data/、configs/；預設：此檔所在目錄＝專案根）",
    )
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--budget", type=int, default=100_000)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--problems", type=str, default=None, help="逗號分隔，例如 weish01,weish02；預設 weish01..30")
    parser.add_argument("--no-ensure-yaml", action="store_true", help="不寫入/更新 YAML（仍從 .dat 載入 ProblemModel）")
    args = parser.parse_args(argv)
    # 此檔在專案根目錄時，repo root = 本檔所在目錄
    repo_root = args.repo_root if args.repo_root is not None else Path(__file__).resolve().parent
    summary = run_weish_equivalence_suite(
        repo_root=repo_root,
        seed=args.seed,
        budget=args.budget,
        problem_ids=_parse_problem_list(args.problems),
        output_dir=args.output_dir,
        ensure_yaml=not args.no_ensure_yaml,
    )
    print(json.dumps({k: summary[k] for k in ("all_pass", "total_seconds", "seed", "budget", "max_iterations")}, ensure_ascii=False))
    return 0 if summary["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
