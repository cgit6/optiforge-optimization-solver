from __future__ import annotations

from pathlib import Path
from .support import parser, createExperimentSpec, executeSimulator


def main():

    """CLI 入口；可由程式呼叫並注入 `argv` / `problem_root` / `solver_root`（測試用）""" 
    
    arg_parser = parser() # 獲取命令行參數，並解析&驗證
    args = arg_parser.parse_args() # 獲取命令行參數
    spec = createExperimentSpec(args) # 實驗規格物件

    # 執行模擬
    return executeSimulator(
        spec=spec, # 實驗規格
        seed=args.seed, # 自定義 seed
        problem_root=Path("configs/problems"),
        solver_root=Path("configs/solvers"),
        output_root=Path("output"),
    )
