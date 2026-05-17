
from __future__ import annotations

from pathlib import Path

from ...experiment import ExperimentReport, build
from .literature_mkp import literature_mkp_evaluator


# 這種東西應該放在專案設定中
DEFAULT_CONFIG_PATH = Path("cli/exp/exp_cfg.yaml") # 實驗設定
DEFAULT_PROBLEM_ROOT = Path("configs/problems") # 題庫路徑
DEFAULT_SOLVER_ROOT = Path("configs/solvers") # 求解器路徑
DEFAULT_OUTPUT_ROOT = Path("output") # 輸出路徑


# 註冊評估函數這邊可以再調整，

def main() -> ExperimentReport:
    # 1. 創建實驗模組
    experiment = build(
        DEFAULT_CONFIG_PATH,
        problem_root=DEFAULT_PROBLEM_ROOT,
        solver_root=DEFAULT_SOLVER_ROOT,
    )
    # 2. 註冊評估函數
    # 這邊或許不用迴護註冊這件事
    experiment.register("literature_mkp", literature_mkp_evaluator) 

    # 3. 執行實驗
    return experiment.run(
        problem_root=DEFAULT_PROBLEM_ROOT, # 題庫根路徑
        solver_root=DEFAULT_SOLVER_ROOT, # 算法資料夾根路徑
        output_root=DEFAULT_OUTPUT_ROOT, # 輸出位至
    )


if __name__ == "__main__":
    main()
