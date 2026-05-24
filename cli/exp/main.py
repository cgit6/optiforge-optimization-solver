from __future__ import annotations

from pathlib import Path

from ...experiment import ExperimentReport, build, register
from .mkp_base import mkp_base_evaluator
from .mkp_base2 import mkp_base2_evaluator


# 這種東西應該放在專案設定中
DEFAULT_CONFIG_PATH = Path("cli/exp/exp_cfg.yaml") # 實驗設定
DEFAULT_PROBLEM_ROOT = Path("configs/problems") # 題庫路徑
DEFAULT_SOLVER_ROOT = Path("configs/solvers") # 求解器路徑
DEFAULT_OUTPUT_ROOT = Path("output") # 輸出路徑


def main() -> ExperimentReport:
    register("mkp_base", mkp_base_evaluator)
    register("mkp_base2", mkp_base2_evaluator)

    # 1. 創建實驗模組
    experiment = build(
        DEFAULT_CONFIG_PATH, # 設定檔路徑
        problem_root=DEFAULT_PROBLEM_ROOT, # 題庫路徑
        solver_root=DEFAULT_SOLVER_ROOT, # 求解器路徑
    )

    # 3. 執行實驗
    return experiment.run(
        problem_root=DEFAULT_PROBLEM_ROOT, # 題庫根路徑
        solver_root=DEFAULT_SOLVER_ROOT, # 算法資料夾根路徑
        output_root=DEFAULT_OUTPUT_ROOT, # 輸出位至
    )


if __name__ == "__main__":
    main()
