"""CLI 之後的編排：驗證參數、呼叫 `engine.build`、建立 `Simulator` 與執行批次、由 show 模組輸出、釋放 SHM。"""

from __future__ import annotations

import argparse
from pathlib import Path

from ... import engine
from ...engine.models import ExperimentSpec
from ...engine.repository import ProblemRepository
from ...simulator import SimulatorResult
from ...tools.show import write_simulator_result
from ...tools.solver_config_loader import SolverConfigLoader
from ...tools.stat import result_entries, summarize

def _splitProblemIds(raw: str) -> tuple[str, ...]:
    """將命令參數 problems 中逗號分隔的題目清單轉換為 tuple 格式"""
    values = tuple(part.strip() for part in raw.split(",") if part.strip())
    if not values:
        raise ValueError("CSV argument cannot be empty.")
    return values

def validate_execute_args(spec: ExperimentSpec, problem_root: Path, solver_root: Path) -> None:
    """執行模擬前驗證：單一 solver、題目 YAML、solver YAML capability 是否相容。"""
    if len(spec.solver_ids) != 1:
        raise ValueError("Exactly one solver is required: pass a single id (see --solver).")

    repository = ProblemRepository(config_root=problem_root)
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

    solver_config = SolverConfigLoader(config_root=solver_root).load(spec.solver_ids[0])
    capabilities = solver_config["capabilities"]
    if problem_type not in {str(v) for v in capabilities["problem_types"]}:
        raise ValueError(
            f"solver={spec.solver_ids[0]} is incompatible: "
            f"problem_type={problem_type!r} not in {capabilities['problem_types']!r}"
        )
    if encoding not in {str(v) for v in capabilities["encodings"]}:
        raise ValueError(
            f"solver={spec.solver_ids[0]} is incompatible: "
            f"encoding={encoding!r} not in {capabilities['encodings']!r}"
        )
    if direction not in {str(v) for v in capabilities["directions"]}:
        raise ValueError(
            f"solver={spec.solver_ids[0]} is incompatible: "
            f"direction={direction!r} not in {capabilities['directions']!r}"
        )

def parser() -> argparse.ArgumentParser:
    """獲取命令行參數，並解析&驗證"""

    # 1. 解析命令行參數
    parser = argparse.ArgumentParser(description="Run MKP simulation batch.")
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--problem-type", default="mkp")
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
    # 2. 返回 parser 物件
    return parser


build_parser = parser


def createExperimentSpec(args: argparse.Namespace) -> ExperimentSpec:
    """建立 ExperimentSpec 物件"""

    # 這邊應該先驗證
    problem_ids = _splitProblemIds(args.problems) # 拆解題目清單為 tuple 格式
    solver = str(args.solver).strip() # 移除求解器ID前後的空白字元
    
    if not solver:
        raise ValueError("--solver must be a non-empty string.")
    
    output_base = Path(args.output_dir)
    output_dir = output_base / args.experiment_id
    return ExperimentSpec(
        experiment_id=args.experiment_id, # 實驗ID
        problem_type=str(args.problem_type).strip() or "mkp",
        dataset=args.dataset, # 資料集
        problem_ids=problem_ids, # 問題ID
        solver_ids=(solver,), # 求解器ID，為了保持可以支持多個求解器ID的tuple格式的擴容條件
        repeat=args.repeat, # 獨立實驗次數
        seed=args.base_seed, # 基礎種子，這邊應該可以彈性選擇要不要填如果填了就固定如果不填就隨機生成
        output_dir=output_dir, # 輸出目錄
        benchmark_enabled=False, # 是否啟用 benchmark
        execution_mode=args.execution_mode, # 任務展開與執行順序
        # 這邊應該要添加一個這個物件的狀態是否被創建過了如果被創建過之後就都不能改了
    )



def executeSimulator(
    spec: ExperimentSpec,
    output_root: Path | str,
    *,
    problem_root: Path | str = Path("configs/problems"),
    solver_root: Path | str = Path("configs/solvers"),
) -> SimulatorResult:
    """驗證參數、`engine.build`、建立 `Simulator`，依 repeat / execution_mode 選串行或併發路徑；批次跑完後交給 show 模組輸出檔案。"""
    problem_root_p = Path(problem_root)
    solver_root_p = Path(solver_root)
    output_root_p = Path(output_root) # 由命令參數決定的輸出目錄

    # 驗證命令行參數合法性
    validate_execute_args(spec, problem_root_p, solver_root_p)

    # 建立 SimulationBundle 物件
    bundle = engine.build(
        spec=spec,
        problem_root=problem_root_p,
        solver_root=solver_root_p,
        output_root=output_root_p,
    )
    try:
        solver_id = spec.solver_ids[0]
        sim = bundle.NewSimulatorWithSeed(solver_id, spec.seed)
        # 這邊判斷是否觸發的邏輯要再注意一下
        if spec.execution_mode == "worker_curriculum":
            simulator_result = sim.run_batch(spec) # 執行併發
        else:
            simulator_result = sim.run_sequential(spec) # 單一

        # 結果與統計
        entries = result_entries(simulator_result)
        summary = summarize(entries)

        # 將整批模擬結果與已計算好的統計交給 show 模組寫入文件
        write_simulator_result(
            simulator_result,
            entries,
            summary,
            experiment_id=spec.experiment_id,
            output_root=output_root_p,
        )
        return simulator_result

    finally:
        bundle.problem_bank.close() # 釋放 ProblemBank shared memory
