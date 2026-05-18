"""CLI 之後的編排：驗證參數、呼叫 `engine.build`、建立 `Simulator` 與執行批次、由 show 模組輸出、釋放 SHM。"""

from __future__ import annotations

import argparse
from pathlib import Path

from ... import engine
from ...engine.models import ExperimentSpec
from ...engine.repository import ProblemRepository
from ...problem import buildProblemRegistry, problemBuilders
from ...simulator import SimulatorResult
from ...tools.show import write_simulator_result
from ...tools.solver_config_loader import SolverConfigLoader

def _splitProblemIds(raw: str) -> tuple[str, ...]:
    """將命令參數 problems 中逗號分隔的題目清單轉換為 tuple 格式"""
    values = tuple(part.strip() for part in raw.split(",") if part.strip())
    if not values:
        raise ValueError("CSV argument cannot be empty.")
    return values


def _splitSolverIds(raw: str) -> tuple[str, ...]:
    """將命令參數 solver 轉換為 tuple"""
    values = tuple(part.strip() for part in raw.split(",") if part.strip())
    if not values:
        raise ValueError("--solver must contain at least one solver id.")
    return values

def validate_execute_args(spec: ExperimentSpec, problem_root: Path, solver_root: Path) -> None:
    """執行模擬前驗證：題目 YAML、solver YAML capability 是否相容。"""
    if len(spec.solver_ids) != 1:
        raise ValueError("cli.run accepts exactly one solver; use cli.exp for multi-solver experiments.")

    problem_registry = buildProblemRegistry(problemBuilders())
    repository = ProblemRepository(config_root=problem_root, registry=problem_registry)
    problem_metas = [
        repository.read_metadata(spec.dataset, problem_id, spec.problem_type)
        for problem_id in spec.problem_ids
    ]
    triples = {(m["problem_type"], m["encoding"], m["direction"]) for m in problem_metas}
    if len(triples) != 1:
        raise ValueError(
            "A single experiment cannot mix problem_type / encoding / direction: "
            f"{sorted(triples)}"
        )
    problem_type, encoding, direction = next(iter(triples))

    loader = SolverConfigLoader(config_root=solver_root)
    for solver_id in spec.solver_ids:
        solver_configs = loader.load_all(solver_id)
        capabilities = solver_configs[0]["capabilities"]
        if problem_type not in {str(v) for v in capabilities["problem_types"]}:
            raise ValueError(
                f"solver={solver_id} is incompatible: "
                f"problem_type={problem_type!r} not in {capabilities['problem_types']!r}"
            )
        if encoding not in {str(v) for v in capabilities["encodings"]}:
            raise ValueError(
                f"solver={solver_id} is incompatible: "
                f"encoding={encoding!r} not in {capabilities['encodings']!r}"
            )
        if direction not in {str(v) for v in capabilities["directions"]}:
            raise ValueError(
                f"solver={solver_id} is incompatible: "
                f"direction={direction!r} not in {capabilities['directions']!r}"
            )

def parser() -> argparse.ArgumentParser:
    """獲取命令行參數，並解析&驗證"""

    # 1. 解析命令行參數
    parser = argparse.ArgumentParser(description="Run simulation batch.")
    parser.add_argument("--experiment-name", required=True)
    parser.add_argument("--type", required=True, dest="problem_type")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--problems", required=True, help="Comma-separated problem ids")
    parser.add_argument("--solver", required=True, help="Single solver id")
    parser.add_argument("--repeat", default=20, type=int)
    parser.add_argument("--seed", default=55688, type=int)
    parser.add_argument("--worker", default=1, type=int, dest="worker_count")
    # 2. 返回 parser 物件
    return parser


build_parser = parser

# 一次模擬只允許執行一種問題類型
def createExperimentSpec(args: argparse.Namespace) -> ExperimentSpec:
    """建立 ExperimentSpec 物件"""

    # 這邊應該先驗證
    problem_ids = _splitProblemIds(args.problems) # 拆解題目清單為 tuple 格式
    solver_ids = _splitSolverIds(args.solver) # 拆解求解器清單為 tuple 格式

    return ExperimentSpec(
        experiment_name=args.experiment_name, # 實驗名稱
        problem_type=str(args.problem_type).strip(), # 問題類型
        dataset=args.dataset, # 資料集
        problem_ids=problem_ids, # 問題ID
        solver_ids=solver_ids, # 求解器ID
        repeat=args.repeat, # 獨立實驗次數
        worker_count=args.worker_count, # worker 數
    )



def executeSimulator(
    spec: ExperimentSpec, # 實驗規格
    *,
    seed: int,
    problem_root: Path,
    solver_root: Path,
    output_root: Path,
) -> SimulatorResult:
    """驗證參數、`engine.build`、建立 `Simulator`，依 worker_count 選串行或併發路徑後輸出結果"""

    # 驗證命令行參數合法性
    validate_execute_args(spec, problem_root, solver_root)

    # 建立 SimulationBundle 物件
    bundle = engine.build(
        spec=spec,
        problem_root=problem_root,
        solver_root=solver_root,
    )
    try:
        sim = bundle.new_simulator()
        # 1. 執行模擬
        if spec.worker_count > 1:
            simulator_result = sim.run_batch(seed=seed) # 併發執行
        else:
            simulator_result = sim.run_sequential(seed=seed) # 單一執行

        # 3. 輸出: 將整批模擬結果與已計算好的統計交給 show 模組寫入文件
        write_simulator_result(
            simulator_result,
            experiment_name=spec.experiment_name,
            output_root=output_root,
        )
        return simulator_result

    finally:
        bundle.problem_bank.close() # 釋放 ProblemBank shared memory
