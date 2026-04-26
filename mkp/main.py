from __future__ import annotations

import argparse
from pathlib import Path

from .contracts import ExperimentSpec
from .engine import Engine


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run MKP simulation batch.")
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--problems", required=True, help="Comma-separated problem ids")
    parser.add_argument("--solvers", required=True, help="Comma-separated solver ids")
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

# 建立實驗規格
def create_experiment_spec(args: argparse.Namespace) -> ExperimentSpec:
    problem_ids = _split_csv_values(args.problems) # 問題ID`
    solver_ids = _split_csv_values(args.solvers) 
    output_base = Path(args.output_dir)
    output_dir = output_base / args.experiment_id
    return ExperimentSpec(
        experiment_id=args.experiment_id, # 實驗ID
        dataset=args.dataset, # 資料集
        problem_ids=problem_ids, # 問題ID
        solver_ids=solver_ids, # 求解器ID
        repeat=args.repeat, # 獨立實驗次數
        base_seed=args.base_seed, # 基礎種子
        output_dir=output_dir, # 輸出目錄
        benchmark_enabled=False, # 是否啟用benchmark
        execution_mode=args.execution_mode, # 任務展開與執行順序
    )

# 前置驗證，如果失敗就不執行後面的事情
def preflight_validate(spec: ExperimentSpec, problem_root: Path, solver_root: Path) -> None:
    # 檢查問題設定檔是否存在
    missing_problem_paths = [
        problem_root / spec.dataset / f"{problem_id}.yaml"
        for problem_id in spec.problem_ids
        if not (problem_root / spec.dataset / f"{problem_id}.yaml").exists()
    ]
    # 如果問題設定檔不存在，則拋出錯誤
    if missing_problem_paths:
        missing = ", ".join(str(path) for path in missing_problem_paths)
        raise FileNotFoundError(f"Missing problem YAML file(s): {missing}")
    # 檢查求解器設定檔是否存在
    missing_solver_paths = [
        solver_root / f"{solver_id}.yaml"
        for solver_id in spec.solver_ids
        if not (solver_root / f"{solver_id}.yaml").exists()
    ]
    # 如果求解器設定檔不存在，則拋出錯誤
    if missing_solver_paths:
        missing = ", ".join(str(path) for path in missing_solver_paths)
        raise FileNotFoundError(f"Missing solver YAML file(s): {missing}")


def main(
    argv: list[str] | None = None,
    *,
    problem_root: Path | str = Path("mkp/configs/problems"),
    solver_root: Path | str = Path("mkp/configs/solvers"),
) -> list[tuple]:
    parser = build_parser() # 解析命令行參數
    args = parser.parse_args(argv) # 轉換為 argparse.Namespace 物件
    spec = create_experiment_spec(args) # 轉換為 ExperimentSpec 物件

    problem_root_path = Path(problem_root)
    solver_root_path = Path(solver_root)
    output_root_path = Path(args.output_dir)
    preflight_validate(spec, problem_root_path, solver_root_path) # 前置驗證(檢查問題和求解器設定檔是否存在)

    # 組裝實驗所需環境
    bundle = Engine.build(
        spec=spec,
        problem_root=problem_root_path,
        solver_root=solver_root_path,
        output_root=output_root_path,
    )
    try:
        return bundle.simulator.run_batch(bundle.spec)
    finally:
        if bundle.problem_bank is not None:
            bundle.problem_bank.close()


if __name__ == "__main__":
    main()
