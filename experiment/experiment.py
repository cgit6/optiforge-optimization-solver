from __future__ import annotations

import json
import shutil
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .config import DatasetSetting, ExperimentConfig, load_config
from .evaluation import (
    DatasetEvalDecision,
    DatasetEvalInput,
    DatasetEvaluator,
    DatasetRunResult,
    FAIL,
    PASS,
    VariantSummary,
)
from ..engine.assembly import Engine
from ..engine.models import ExperimentSpec
from ..simulator.core import Simulator
from ..tools.show import write_simulator_result
from ..tools.stat import ResultEntry, SummaryMeta, SummaryReport, result_entries, summarize


@dataclass(frozen=True)
class DatasetEvaluationRecord:
    dataset_setting: DatasetSetting
    decision: DatasetEvalDecision


@dataclass(frozen=True)
class SeedAttempt:
    seed: int
    verdict: str
    collected: bool
    dataset_evaluations: tuple[DatasetEvaluationRecord, ...]
    message: str = ""


@dataclass(frozen=True)
class CollectedSeed:
    collect_index: int
    seed: int
    output_dir: str
    dataset_evaluations: tuple[DatasetEvaluationRecord, ...]


@dataclass(frozen=True)
class ExperimentReport:
    experiment_name: str
    output_dir: str
    collected_seeds: tuple[int, ...]
    attempts: tuple[SeedAttempt, ...]
    collected: tuple[CollectedSeed, ...] = ()


@dataclass
class Experiment:
    cfg: ExperimentConfig # 實驗設定
    evaluators: dict[str, DatasetEvaluator] = field(default_factory=dict) # 評估函數的註冊清單
    collected_results: list[CollectedSeed] = field(default_factory=list) # 符合條件的實驗 seed

    def register(self, name: str, evaluator: DatasetEvaluator) -> None:
        if not name.strip():
            raise ValueError("evaluator name cannot be empty.")
        self.evaluators[name] = evaluator

    def run(self, *, problem_root: Path, solver_root: Path, output_root: Path) -> ExperimentReport:
        dataset_evaluators = self._dataset_evaluators()
        # 輸出位置
        experiment_output_dir = Path(output_root) / self.cfg.experiment_name
        if experiment_output_dir.exists():
            shutil.rmtree(experiment_output_dir)
        experiment_output_dir.mkdir(parents=True, exist_ok=True)
        self.collected_results.clear()

        # 緩存，但是不應該再這，應該是實驗模組的屬性值然後共用
        attempts: list[SeedAttempt] = []
        collected: list[CollectedSeed] = []
        start, end = self.cfg.seed_range
        simulators: dict[str, Simulator] = {}
        dataset_total = len(self.cfg.dataset_settings)
        dataset_name_width = max(len(setting.dataset) for setting in self.cfg.dataset_settings)

        try:
            for dataset_setting in self.cfg.dataset_settings:
                simulators[dataset_setting.experiment_id] = self._build_dataset_simulator(
                    dataset_setting,
                    problem_root=problem_root,
                    solver_root=solver_root,
                )

            # 執行實驗
            for seed in range(start, end + 1):
                if len(collected) >= self.cfg.collects:
                    break

                dataset_results: list[DatasetRunResult] = []
                dataset_evaluations: list[DatasetEvaluationRecord] = []
                seed_failed = False

                for dataset_index, dataset_setting in enumerate(self.cfg.dataset_settings, start=1):
                    _emit_dataset_status(
                        seed=seed,
                        dataset_index=dataset_index,
                        dataset_total=dataset_total,
                        dataset_name_width=dataset_name_width,
                        dataset_setting=dataset_setting,
                        status="進行中",
                    )
                    dataset_result = self._run_dataset_seed(
                        dataset_setting,
                        seed=seed,
                        simulator=simulators[dataset_setting.experiment_id],
                    )
                    decision = dataset_evaluators[dataset_setting.experiment_id](
                        DatasetEvalInput(
                            seed=seed,
                            dataset_setting=dataset_setting,
                            evaluation_name=dataset_setting.evaluation.name,
                            evaluation_config=dataset_setting.evaluation.config,
                            variant_summaries=dataset_result.variant_summaries,
                            simulator_result=dataset_result.simulator_result,
                        )
                    )
                    dataset_evaluations.append(
                        DatasetEvaluationRecord(
                            dataset_setting=dataset_setting,
                            decision=decision,
                        )
                    )
                    _emit_dataset_status(
                        seed=seed,
                        dataset_index=dataset_index,
                        dataset_total=dataset_total,
                        dataset_name_width=dataset_name_width,
                        dataset_setting=dataset_setting,
                        status="通過" if decision.passed else "未通過",
                    )
                    if not decision.passed:
                        seed_failed = True
                        break
                    dataset_results.append(dataset_result)

                attempt_verdict = FAIL if seed_failed else PASS
                attempts.append(
                    SeedAttempt(
                        seed=seed,
                        verdict=attempt_verdict,
                        collected=not seed_failed,
                        dataset_evaluations=tuple(dataset_evaluations),
                        message=_attempt_message(dataset_evaluations, collected=not seed_failed),
                    )
                )

                if seed_failed:
                    continue

                collect_index = len(collected) + 1
                collect_dir = experiment_output_dir / f"collect_{collect_index:04d}"
                self._write_collect(
                    collect_dir=collect_dir,
                    collect_index=collect_index,
                    seed=seed,
                    dataset_results=dataset_results,
                    dataset_evaluations=dataset_evaluations,
                    output_root=Path(output_root),
                )
                collected_seed = CollectedSeed(
                    collect_index=collect_index,
                    seed=seed,
                    output_dir=str(collect_dir),
                    dataset_evaluations=tuple(dataset_evaluations),
                )
                collected.append(collected_seed)
                self.collected_results.append(collected_seed)
        finally:
            for simulator in simulators.values():
                simulator.close()

        report = ExperimentReport(
            experiment_name=self.cfg.experiment_name,
            output_dir=str(experiment_output_dir),
            collected_seeds=tuple(item.seed for item in collected),
            attempts=tuple(attempts),
            collected=tuple(collected),
        )
        _write_json(experiment_output_dir / "summary.json", asdict(report))
        return report

    def _build_dataset_simulator(
        self,
        dataset_setting: DatasetSetting,
        *,
        problem_root: Path | str,
        solver_root: Path | str,
    ) -> Simulator:
        spec = ExperimentSpec(
            experiment_name=f"{self.cfg.experiment_name}_{dataset_setting.experiment_id}",
            dataset=dataset_setting.dataset,
            problem_ids=dataset_setting.problem_ids,
            solver_ids=self.cfg.solver_ids,
            repeat=self.cfg.repeat,
            worker_count=self.cfg.worker_count,
            problem_type=dataset_setting.problem_type,
        )
        bundle = Engine.build(spec=spec, problem_root=Path(problem_root), solver_root=Path(solver_root))
        return bundle.new_simulator()

    def _run_dataset_seed(
        self,
        dataset_setting: DatasetSetting,
        *,
        seed: int,
        simulator: Simulator,
    ) -> DatasetRunResult:
        simulator_result = (
            simulator.run_sequential(seed=seed, show_progress=False)
            if self.cfg.worker_count == 1
            else simulator.run_batch(seed=seed, show_progress=False)
        )
        return DatasetRunResult(
            seed=seed,
            dataset_setting=dataset_setting,
            simulator_result=simulator_result,
            variant_summaries=_variant_summaries(simulator_result),
        )

    def _write_collect(
        self,
        *,
        collect_dir: Path,
        collect_index: int,
        seed: int,
        dataset_results: list[DatasetRunResult],
        dataset_evaluations: list[DatasetEvaluationRecord],
        output_root: Path,
    ) -> None:
        collect_dir.mkdir(parents=True, exist_ok=True)
        for dataset_result in dataset_results:
            metadata = {
                key: {
                    "seed": seed,
                    "collect_index": collect_index,
                    "dataset_experiment_id": dataset_result.dataset_setting.experiment_id,
                }
                for key in dataset_result.simulator_result.variant_params
            }
            write_simulator_result(
                dataset_result.simulator_result,
                experiment_name=(
                    f"{self.cfg.experiment_name}/collect_{collect_index:04d}/"
                    f"{dataset_result.dataset_setting.experiment_id}"
                ),
                output_root=output_root,
                variant_metadata=metadata,
            )
        _write_json(
            collect_dir / "collect_summary.json",
            {
                "collect_index": collect_index,
                "seed": seed,
                "dataset_evaluations": [asdict(record) for record in dataset_evaluations],
            },
        )

    def _dataset_evaluators(self) -> dict[str, DatasetEvaluator]:
        evaluators: dict[str, DatasetEvaluator] = {}
        for dataset_setting in self.cfg.dataset_settings:
            evaluation_name = dataset_setting.evaluation.name
            if evaluation_name not in self.evaluators:
                raise KeyError(f"unknown evaluator: {evaluation_name}")
            evaluators[dataset_setting.experiment_id] = self.evaluators[evaluation_name]
        return evaluators


def build(
    exp_path: Path,
    *,
    problem_root: Path = Path("configs/problems"),
    solver_root: Path = Path("configs/solvers"),
) -> Experiment:
    
    # 這邊應該先檢查路徑中的資料是否存在
    
    # 讀實驗設定
    cfg = load_config(
        exp_path, 
        problem_root=problem_root,
        solver_root=solver_root,
    )
    # 返回實驗實例
    return Experiment(cfg=cfg)


def executeExperiment(
    experiment: Experiment,
    *,
    problem_root: Path | str = Path("configs/problems"),
    solver_root: Path | str = Path("configs/solvers"),
    output_root: Path | str = Path("output"),
) -> ExperimentReport:
    return experiment.run(
        problem_root=problem_root,
        solver_root=solver_root,
        output_root=output_root,
    )


def _variant_summaries(simulator_result: Any) -> tuple[VariantSummary, ...]:
    entries = result_entries(simulator_result)
    grouped: dict[tuple[str, int], list[ResultEntry]] = defaultdict(list)
    for entry in entries:
        grouped[(entry.solver_id, entry.param_set_index)].append(entry)

    variants: list[VariantSummary] = []
    for solver_id, param_set_index in sorted(grouped):
        key = (solver_id, param_set_index)
        variants.append(
            VariantSummary(
                solver_id=solver_id,
                param_set_index=param_set_index,
                params=simulator_result.variant_params[key],
                summary=summarize(
                    grouped[key],
                    meta=SummaryMeta(
                        solver_id=solver_id,
                        param_set_index=param_set_index,
                        params=simulator_result.variant_params[key],
                    ),
                ),
            )
        )
    return tuple(variants)


def _attempt_message(
    dataset_evaluations: list[DatasetEvaluationRecord],
    *,
    collected: bool,
) -> str:
    if collected:
        return "seed collected"
    if not dataset_evaluations:
        return "seed failed"
    failed = dataset_evaluations[-1]
    return (
        f"{failed.dataset_setting.experiment_id}: {failed.decision.message}"
        if failed.decision.message
        else f"{failed.dataset_setting.experiment_id}: dataset failed"
    )


def _emit_dataset_status(
    *,
    seed: int,
    dataset_index: int,
    dataset_total: int,
    dataset_name_width: int,
    dataset_setting: DatasetSetting,
    status: str,
) -> None:
    print(
        f"[seed {seed}] ({dataset_index}/{dataset_total}) "
        f"{dataset_setting.dataset:<{dataset_name_width}}   {status}",
        file=sys.stderr,
        flush=True,
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
