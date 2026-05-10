from __future__ import annotations

import json
import shutil
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .config import DatasetSetting, ExperimentConfig, ExperimentVariant, load_config
from .evaluation import (
    FAIL,
    PASSING_VERDICTS,
    CheckResult,
    EvaluationReport,
    Evaluator,
    StageSummary,
    literature_mkp_evaluator,
)
from ..engine.assembly import Engine
from ..engine.models import ExperimentSpec
from ..simulator.core import SimulatorResult
from ..tools.show import write_simulator_result
from ..tools.stat import ResultEntry, SummaryMeta, SummaryReport, result_entries, summarize


@dataclass(frozen=True)
class SeedAttempt:
    seed: int
    verdict: str
    collected: bool
    checks: tuple[CheckResult, ...]
    message: str = ""


@dataclass(frozen=True)
class CollectedSeed:
    collect_index: int
    seed: int
    output_dir: str
    evaluation: EvaluationReport


@dataclass(frozen=True)
class ExperimentReport:
    experiment_name: str
    output_dir: str
    collected_seeds: tuple[int, ...]
    attempts: tuple[SeedAttempt, ...]
    collected: tuple[CollectedSeed, ...] = ()


@dataclass
class _VariantRun:
    dataset_setting: DatasetSetting
    variant: ExperimentVariant
    summary: SummaryReport
    simulator_result: SimulatorResult


@dataclass
class Experiment:
    cfg: ExperimentConfig
    evaluators: dict[str, Evaluator] = field(default_factory=dict)
    collected_results: list[CollectedSeed] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.evaluators.setdefault("literature_mkp", literature_mkp_evaluator)

    def register(self, name: str, evaluator: Evaluator) -> None:
        if not name.strip():
            raise ValueError("evaluator name cannot be empty.")
        self.evaluators[name] = evaluator

    def run(
        self,
        *,
        eval_name: str = "literature_mkp",
        problem_root: Path | str = Path("configs/problems"),
        solver_root: Path | str = Path("configs/solvers"),
        output_root: Path | str = Path("output"),
    ) -> ExperimentReport:
        if eval_name not in self.evaluators:
            raise KeyError(f"unknown evaluator: {eval_name}")

        evaluator = self.evaluators[eval_name]
        experiment_output_dir = Path(output_root) / self.cfg.experiment_name
        if experiment_output_dir.exists():
            shutil.rmtree(experiment_output_dir)
        experiment_output_dir.mkdir(parents=True, exist_ok=True)

        attempts: list[SeedAttempt] = []
        collected: list[CollectedSeed] = []
        start, end = self.cfg.seed_range

        for seed in range(start, end + 1):
            if len(collected) >= self.cfg.collects:
                break

            variant_runs: list[_VariantRun] = []
            stage_summaries: list[StageSummary] = []
            partial_evaluation: EvaluationReport | None = None

            for dataset_setting in self.cfg.dataset_settings:
                dataset_runs, dataset_summaries = self._run_dataset_seed(
                    dataset_setting,
                    seed=seed,
                    problem_root=problem_root,
                    solver_root=solver_root,
                )
                variant_runs.extend(dataset_runs)
                stage_summaries.extend(dataset_summaries)
                if not _stage_summaries_are_valid(self.cfg, dataset_summaries):
                    partial_evaluation = literature_mkp_evaluator(self.cfg, seed, tuple(stage_summaries))
                    break

            evaluation = partial_evaluation or evaluator(self.cfg, seed, tuple(stage_summaries))
            is_collected = evaluation.verdict in PASSING_VERDICTS
            message = _attempt_message(evaluation)
            attempts.append(
                SeedAttempt(
                    seed=seed,
                    verdict=evaluation.verdict,
                    collected=is_collected,
                    checks=evaluation.checks,
                    message=message,
                )
            )

            if not is_collected:
                continue

            collect_index = len(collected) + 1
            collect_dir = experiment_output_dir / f"collect_{collect_index:04d}"
            self._write_collect(
                collect_dir=collect_dir,
                collect_index=collect_index,
                seed=seed,
                evaluation=evaluation,
                variant_runs=variant_runs,
                output_root=Path(output_root),
            )
            collected_seed = CollectedSeed(
                collect_index=collect_index,
                seed=seed,
                output_dir=str(collect_dir),
                evaluation=evaluation,
            )
            collected.append(collected_seed)
            self.collected_results.append(collected_seed)

        report = ExperimentReport(
            experiment_name=self.cfg.experiment_name,
            output_dir=str(experiment_output_dir),
            collected_seeds=tuple(item.seed for item in collected),
            attempts=tuple(attempts),
            collected=tuple(collected),
        )
        _write_json(experiment_output_dir / "summary.json", asdict(report))
        return report

    def _run_dataset_seed(
        self,
        dataset_setting: DatasetSetting,
        *,
        seed: int,
        problem_root: Path | str,
        solver_root: Path | str,
    ) -> tuple[list[_VariantRun], list[StageSummary]]:
        spec = ExperimentSpec(
            experiment_name=f"{self.cfg.experiment_name}_{dataset_setting.experiment_id}_seed_{seed}",
            dataset=dataset_setting.dataset,
            problem_ids=dataset_setting.problem_ids,
            solver_ids=self.cfg.solver_ids,
            repeat=self.cfg.repeat,
            seed=seed,
            worker_count=self.cfg.worker_count,
            problem_type=dataset_setting.problem_type,
        )
        bundle = Engine.build(spec=spec, problem_root=Path(problem_root), solver_root=Path(solver_root))
        simulator = bundle.new_simulator()
        try:
            simulator_result = simulator.run_sequential() if self.cfg.worker_count == 1 else simulator.run_batch()
        finally:
            simulator.close()

        summaries_by_variant = _summaries_by_variant(simulator_result)
        variant_runs: list[_VariantRun] = []
        stage_summaries: list[StageSummary] = []
        for variant in self._stage_variants():
            key = (variant.solver_id, variant.param_set_index)
            if key not in summaries_by_variant:
                raise KeyError(f"simulator did not produce variant: solver={key[0]!r}, param={key[1]}")
            summary = summaries_by_variant[key]
            filtered_result = _filter_simulator_result(simulator_result, solver_id=key[0], param_set_index=key[1])
            variant_runs.append(
                _VariantRun(
                    dataset_setting=dataset_setting,
                    variant=variant,
                    summary=summary,
                    simulator_result=filtered_result,
                )
            )
            stage_summaries.append(
                StageSummary(
                    stage=variant.stage,
                    dataset_experiment_id=dataset_setting.experiment_id,
                    dataset=dataset_setting.dataset,
                    combo_id=variant.combo_id,
                    algorithm=variant.algorithm,
                    solver_id=variant.solver_id,
                    param_set_index=variant.param_set_index,
                    params=dict(simulator_result.variant_params[key]),
                    transfer_type=variant.transfer_type,
                    summary=summary,
                )
            )
        return variant_runs, stage_summaries

    def _stage_variants(self) -> tuple[ExperimentVariant, ...]:
        return tuple(variant for stage in self.cfg.stages for variant in stage.variants)

    def _write_collect(
        self,
        *,
        collect_dir: Path,
        collect_index: int,
        seed: int,
        evaluation: EvaluationReport,
        variant_runs: list[_VariantRun],
        output_root: Path,
    ) -> None:
        collect_dir.mkdir(parents=True, exist_ok=True)
        for run in variant_runs:
            metadata = {
                "stage": run.variant.stage,
                "algorithm": run.variant.algorithm,
                "transfer_type": run.variant.transfer_type,
                "combo_id": run.variant.combo_id,
                "seed": seed,
                "collect_index": collect_index,
                "dataset_experiment_id": run.dataset_setting.experiment_id,
            }
            write_simulator_result(
                run.simulator_result,
                experiment_name=(
                    f"{self.cfg.experiment_name}/collect_{collect_index:04d}/"
                    f"{run.dataset_setting.experiment_id}/{run.variant.stage}"
                ),
                output_root=output_root,
                variant_metadata={(run.variant.solver_id, run.variant.param_set_index): metadata},
            )
        _write_json(
            collect_dir / "collect_summary.json",
            {
                "collect_index": collect_index,
                "seed": seed,
                "evaluation": asdict(evaluation),
            },
        )


def build(
    exp_path: Path | str = Path("cli/exp/exp_cfg.yaml"),
    *,
    problem_root: Path | str = Path("configs/problems"),
    solver_root: Path | str = Path("configs/solvers"),
) -> Experiment:
    cfg = load_config(
        exp_path,
        problem_root=problem_root,
        solver_root=solver_root,
    )
    return Experiment(cfg=cfg)


def executeExperiment(
    experiment: Experiment,
    *,
    eval_name: str = "literature_mkp",
    problem_root: Path | str = Path("configs/problems"),
    solver_root: Path | str = Path("configs/solvers"),
    output_root: Path | str = Path("output"),
) -> ExperimentReport:
    return experiment.run(
        eval_name=eval_name,
        problem_root=problem_root,
        solver_root=solver_root,
        output_root=output_root,
    )


def _summaries_by_variant(simulator_result: SimulatorResult) -> dict[tuple[str, int], SummaryReport]:
    entries = result_entries(simulator_result)
    grouped: dict[tuple[str, int], list[ResultEntry]] = defaultdict(list)
    for entry in entries:
        grouped[(entry.solver_id, entry.param_set_index)].append(entry)
    summaries: dict[tuple[str, int], SummaryReport] = {}
    for (solver_id, param_set_index), bucket in grouped.items():
        summaries[(solver_id, param_set_index)] = summarize(
            bucket,
            meta=SummaryMeta(
                solver_id=solver_id,
                param_set_index=param_set_index,
                params=simulator_result.variant_params[(solver_id, param_set_index)],
            ),
        )
    return summaries


def _filter_simulator_result(
    simulator_result: SimulatorResult,
    *,
    solver_id: str,
    param_set_index: int,
) -> SimulatorResult:
    key = (solver_id, param_set_index)
    return SimulatorResult(
        rows=tuple(
            row
            for row in simulator_result.rows
            if row.task.solver_id == solver_id and row.task.param_set_index == param_set_index
        ),
        variant_params={key: dict(simulator_result.variant_params[key])},
    )


def _stage_summaries_are_valid(cfg: ExperimentConfig, summaries: list[StageSummary]) -> bool:
    for stage_summary in summaries:
        for group in stage_summary.summary.by_problem_solver:
            excluded = group.excluded_counts
            if (
                group.run_count != cfg.repeat
                or group.valid_run_count != cfg.repeat
                or group.feasible_rate != 1.0
                or group.avg_objective is None
                or group.best_known is None
                or excluded.infeasible
                or excluded.objective_mismatch
                or excluded.runtime_error
            ):
                return False
    return True


def _attempt_message(evaluation: EvaluationReport) -> str:
    if evaluation.verdict != FAIL:
        return "seed collected"
    failed = [check for check in evaluation.checks if check.verdict == FAIL]
    if not failed:
        return "seed failed"
    return "; ".join(f"{check.name}: {check.message}" for check in failed[:3])


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
