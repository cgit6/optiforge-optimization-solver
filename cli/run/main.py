from __future__ import annotations

from pathlib import Path

from ...rng import DerivedPerProblemSeedStrategy
from .support import buildSimulationBundle, parser, createExperimentSpec, executeSimulator


def main(
    argv: list[str] | None = None,
    *,
    problem_root: Path | str = Path("configs/problems"),
    solver_root: Path | str = Path("configs/solvers"),
    output_root: Path | str = Path("output"),
):
    """CLI 入口；可由程式呼叫並注入 `argv` / `problem_root` / `solver_root`（測試用）"""

    arg_parser = parser() # 獲取命令行參數，並解析&驗證
    args = arg_parser.parse_args(argv) # 獲取命令行參數
    spec = createExperimentSpec(args) # 實驗規格物件
    bundle = buildSimulationBundle(
        spec,
        seed_strategy=DerivedPerProblemSeedStrategy(),
        problem_root=Path(problem_root),
        solver_root=Path(solver_root),
    )

    # 執行模擬
    return executeSimulator(
        bundle=bundle,
        base_seed=args.seed, # 自定義 seed
        output_root=Path(output_root),
    )
