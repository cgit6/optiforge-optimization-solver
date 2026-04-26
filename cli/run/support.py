"""CLI 之後的編排：驗證參數、呼叫 `engine.build`、建立 `Simulator` 與執行批次、釋放 SHM。"""

from __future__ import annotations

import argparse
from pathlib import Path

from ... import engine
from ...engine.contracts import ExperimentSpec

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run MKP simulation batch.")
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--problems", required=True, help="Comma-separated problem ids")
    parser.add_argument("--solver", required=True, help="Single solver id (one algorithm per run)")
    parser.add_argument("--repeat", required=True, type=int)
    parser.add_argument("--base-seed", required=True, type=int)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--execution-mode",
        choices=("grid", "worker_curriculum"),
        default="grid",
        help="Task order: grid = problem×solver×repeat; worker_curriculum = solver×repeat×problem.",
    )
    return parser


def _split_csv_values(raw: str) -> tuple[str, ...]:
    values = tuple(part.strip() for part in raw.split(",") if part.strip())
    if not values:
        raise ValueError("CSV argument cannot be empty.")
    return values


def create_experiment_spec(args: argparse.Namespace) -> ExperimentSpec:
    problem_ids = _split_csv_values(args.problems)
    solver = str(args.solver).strip()
    if not solver:
        raise ValueError("--solver must be a non-empty string.")
    output_base = Path(args.output_dir)
    output_dir = output_base / args.experiment_id
    return ExperimentSpec(
        experiment_id=args.experiment_id,
        dataset=args.dataset,
        problem_ids=problem_ids,
        solver_ids=(solver,),
        repeat=args.repeat,
        seed=args.base_seed,
        output_dir=output_dir,
        benchmark_enabled=False,
        execution_mode=args.execution_mode,
    )


def preflight_validate(spec: ExperimentSpec, problem_root: Path, solver_root: Path) -> None:
    """檢查實驗所引用之題目與 solver 的 yaml 檔案是否存在（由 `main` / `validate_execute_args` 使用）。"""
    missing_problem_paths = [
        problem_root / spec.dataset / f"{problem_id}.yaml"
        for problem_id in spec.problem_ids
        if not (problem_root / spec.dataset / f"{problem_id}.yaml").exists()
    ]
    if missing_problem_paths:
        missing = ", ".join(str(path) for path in missing_problem_paths)
        raise FileNotFoundError(f"Missing problem YAML file(s): {missing}")
    missing_solver_paths = [
        solver_root / f"{solver_id}.yaml"
        for solver_id in spec.solver_ids
        if not (solver_root / f"{solver_id}.yaml").exists()
    ]
    if missing_solver_paths:
        missing = ", ".join(str(path) for path in missing_solver_paths)
        raise FileNotFoundError(f"Missing solver YAML file(s): {missing}")


def validate_execute_args(spec: ExperimentSpec, problem_root: Path, solver_root: Path) -> None:
    """執行模擬前驗證：單一 solver、檔案存在等。"""
    if len(spec.solver_ids) != 1:
        raise ValueError("Exactly one solver is required: pass a single id (see --solver).")
    preflight_validate(spec, problem_root, solver_root)


def executeSimulator(
    spec: ExperimentSpec,
    problem_root: Path | str,
    solver_root: Path | str,
    output_root: Path | str,
) -> list[tuple]:
    """驗證參數、`engine.build`、建立 `Simulator`，再依 repeat／execution_mode 選串行或併發路徑。"""
    problem_root_p = Path(problem_root)
    solver_root_p = Path(solver_root)
    output_root_p = Path(output_root)
    validate_execute_args(spec, problem_root_p, solver_root_p)

    bundle = engine.build(
        spec=spec,
        problem_root=problem_root_p,
        solver_root=solver_root_p,
        output_root=output_root_p,
    )
    try:
        solver_id = spec.solver_ids[0]
        sim = bundle.NewSimulatorWithSeed(solver_id, spec.seed)
        if spec.execution_mode == "worker_curriculum" and spec.repeat > 1:
            return sim.run_batch(spec)
        return sim.run_sequential(spec)

    finally:
        bundle.problem_bank.close() # 釋放 ProblemBank shared memory
