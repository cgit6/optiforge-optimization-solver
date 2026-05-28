from __future__ import annotations

import json
import math
import shutil
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .config import DatasetSetting, ExperimentConfig, ProblemSetting, load_config
from .evaluation import RoundEvalDecision, RoundEvalInput, RoundEvaluator, VariantSummary
from .seed_bank import build_seed_bank, problem_seed_entry, solver_config_snapshot, variant_key, write_seed_bank
from ..engine.assembly import Engine
from ..engine.models import ExperimentSpec, RunTask
from ..machine import Machine, MachinePool, MachinePoolSession, MachineResult, SimulatorRunRow
from ..rng import DerivedPerProblemSeedStrategy
from ..simulator.core import Simulator, SimulatorResult
from ..tools.show import write_simulator_result
from ..tools.stat import SummaryMeta, machine_result_entries, summarize

EXP_BASE_SEED = 0
COLLECTION_PROGRESS_INTERVAL = 50

_EVALUATORS: dict[str, RoundEvaluator] = {}


@dataclass(frozen=True)
class ProblemCollectionReport:
    dataset_experiment_id: str
    dataset: str
    problem_id: str
    output_dir: str
    status: str
    collected_count: int
    attempted_repeats: int
    collected_repeat_indices: tuple[int, ...]
    collected_run_seeds: tuple[int, ...]


@dataclass(frozen=True)
class ExperimentReport:
    experiment_name: str
    output_dir: str
    problems: tuple[ProblemCollectionReport, ...]


@dataclass
class Experiment:
    cfg: ExperimentConfig
    collected_results: list[ProblemCollectionReport] = field(default_factory=list)
    _seed_bank_problem_entries: list[dict[str, Any]] = field(default_factory=list, init=False, repr=False)
    _seed_bank_variants: dict[str, dict[str, Any]] = field(default_factory=dict, init=False, repr=False)

    def run(self, *, problem_root: Path, solver_root: Path, output_root: Path) -> ExperimentReport:
        """執行優化任務"""
        _assert_configured_evaluators_registered(self.cfg)
        experiment_output_dir = Path(output_root) / self.cfg.experiment_name
        if experiment_output_dir.exists():
            shutil.rmtree(experiment_output_dir)
        experiment_output_dir.mkdir(parents=True, exist_ok=True)
        self.collected_results.clear()
        self._seed_bank_problem_entries.clear()
        self._seed_bank_variants.clear()

        progress = _CollectionProgress(self.cfg)
        print("step1: collect", file=sys.stderr, flush=True)
        progress.emit()

        problem_reports: list[ProblemCollectionReport] = []
        # 對每一個題庫跑模擬
        for dataset_setting in self.cfg.dataset_settings:
            simulators = self._build_dataset_simulators(
                dataset_setting,
                problem_root=problem_root,
                solver_root=solver_root,
            )
            try:
                # 跑模擬
                dataset_reports = self._run_dataset(
                    dataset_setting,
                    simulators=simulators,
                    output_root=Path(output_root),
                    progress=progress,
                )
                problem_reports.extend(dataset_reports)
                self.collected_results.extend(dataset_reports)
            finally:
                if simulators:
                    simulators[0].close()
        print("step2: report")
        report = ExperimentReport(
            experiment_name=self.cfg.experiment_name,
            output_dir=str(experiment_output_dir),
            problems=tuple(problem_reports),
        )
        # 輸出
        print("step: write summary.json file")
        _write_json(experiment_output_dir / "summary.json", asdict(report))
        if self._seed_bank_problem_entries:
            write_seed_bank(
                experiment_output_dir / "seed_bank.json",
                build_seed_bank(
                    experiment_name=self.cfg.experiment_name,
                    base_seed=EXP_BASE_SEED,
                    seed_strategy=DerivedPerProblemSeedStrategy.__name__,
                    variants=self._seed_bank_variants.values(),
                    problems=self._seed_bank_problem_entries,
                ),
            )
        print("step3: finish")
        return report

    def _build_dataset_simulators(
        self,
        dataset_setting: DatasetSetting,
        *,
        problem_root: Path | str,
        solver_root: Path | str,
    ) -> tuple[Simulator, ...]:
        spec = ExperimentSpec(
            experiment_name=f"{self.cfg.experiment_name}_{dataset_setting.experiment_id}",
            dataset=dataset_setting.dataset,
            problem_ids=dataset_setting.problem_ids,
            solver_ids=self.cfg.solver_ids,
            repeat=self.cfg.repeat,
            worker_count=self.cfg.worker_count,
            problem_type=dataset_setting.problem_type,
            base_seed=EXP_BASE_SEED,
        )
        bundle = Engine.build(
            spec=spec,
            problem_root=Path(problem_root),
            solver_root=Path(solver_root),
            seed_strategy=DerivedPerProblemSeedStrategy(),
        )
        return bundle.new_simulators()

    def _run_dataset(
        self,
        dataset_setting: DatasetSetting,
        *,
        simulators: tuple[Simulator, ...],
        output_root: Path,
        progress: _CollectionProgress,
    ) -> list[ProblemCollectionReport]:
        machines = _selected_machines(simulators, self.cfg.solver_variants)
        reports: list[ProblemCollectionReport] = []
        pool = MachinePool(machines, worker_count=self.cfg.worker_count)
        with pool.session() as session:
            for problem_setting in dataset_setting.problem_settings:
                reports.append(
                    self._run_problem(
                        dataset_setting,
                        problem_setting=problem_setting,
                        machines=machines,
                        session=session,
                        output_root=output_root,
                        progress=progress,
                    )
                )
        return reports

    def _run_problem(
        self,
        dataset_setting: DatasetSetting,
        *,
        problem_setting: ProblemSetting,
        machines: tuple[Machine, ...],
        session: MachinePoolSession,
        output_root: Path,
        progress: _CollectionProgress,
    ) -> ProblemCollectionReport:
        rows_by_variant: dict[tuple[str, int], list[SimulatorRunRow]] = {
            (machine.solver_id, machine.param_set_index): []
            for machine in machines
        }
        collected_repeat_indices: list[int] = []
        collected_run_seeds: list[int] = []
        attempted_repeats = 0
        window_size = _repeat_window_size(self.cfg.worker_count, len(machines))
        problem_id = problem_setting.problem_id
        repeat_index = 0

        while repeat_index < self.cfg.repeat and len(collected_repeat_indices) < self.cfg.collects:
            repeat_indices = tuple(
                range(repeat_index, min(self.cfg.repeat, repeat_index + window_size))
            )
            tasks = _window_tasks(machines, problem_id=problem_id, repeat_indices=repeat_indices)
            window_result = SimulatorResult(machine_results=session.run_tasks(tasks))

            for candidate_repeat_index in repeat_indices:
                if len(collected_repeat_indices) >= self.cfg.collects:
                    break
                attempted_repeats = candidate_repeat_index + 1
                round_result = _result_for_repeat(
                    machines,
                    window_result=window_result,
                    problem_id=problem_id,
                    repeat_index=candidate_repeat_index,
                )
                projected_rows_by_variant = _copy_rows_by_variant(rows_by_variant)
                _append_round_rows(projected_rows_by_variant, round_result)
                projected_result = SimulatorResult(
                    machine_results=_machine_results_from_rows(machines, projected_rows_by_variant)
                )
                collected_result = SimulatorResult(
                    machine_results=_machine_results_from_rows(machines, rows_by_variant)
                )

                decisions = _evaluate_candidate_round(
                    dataset_setting=dataset_setting,
                    problem_setting=problem_setting,
                    problem_id=problem_id,
                    repeat_index=candidate_repeat_index,
                    round_result=round_result,
                    collected_result=collected_result,
                    projected_result=projected_result,
                )
                accepted = all(decision.passed for decision in decisions)
                if accepted:
                    _append_round_rows(rows_by_variant, round_result)
                    collected_repeat_indices.append(candidate_repeat_index)
                    collected_run_seeds.append(
                        _shared_round_seed(round_result, problem_id, candidate_repeat_index)
                    )

                progress.set_count(
                    dataset_setting=dataset_setting,
                    problem_id=problem_id,
                    collected_count=len(collected_repeat_indices),
                )
                progress.record_evaluation()

            repeat_index += len(repeat_indices)

        if len(collected_repeat_indices) < self.cfg.collects:
            raise RuntimeError(
                "experiment collection failed: "
                f"dataset={dataset_setting.experiment_id!r} problem_id={problem_id!r} "
                f"collected={len(collected_repeat_indices)} required={self.cfg.collects} "
                f"repeat_limit={self.cfg.repeat}"
            )

        result = SimulatorResult(
            machine_results=_machine_results_from_rows(machines, rows_by_variant)
        )
        experiment_name = f"{self.cfg.experiment_name}/{dataset_setting.experiment_id}/{problem_id}"
        metadata = {
            (machine_result.solver_id, machine_result.param_set_index): {
                "base_seed": EXP_BASE_SEED,
                "dataset_experiment_id": dataset_setting.experiment_id,
                "problem_id": problem_id,
                "collected_count": len(collected_repeat_indices),
                "collected_repeat_indices": tuple(collected_repeat_indices),
                "collected_run_seeds": tuple(collected_run_seeds),
                "evaluations": problem_setting.evaluation_names,
            }
            for machine_result in result.machine_results
        }
        write_simulator_result(
            result,
            experiment_name=experiment_name,
            output_root=output_root,
            variant_metadata=metadata,
        )
        self._record_seed_bank_problem(
            dataset_setting=dataset_setting,
            problem_id=problem_id,
            machines=machines,
            collected_repeat_indices=tuple(collected_repeat_indices),
            collected_run_seeds=tuple(collected_run_seeds),
        )
        return ProblemCollectionReport(
            dataset_experiment_id=dataset_setting.experiment_id,
            dataset=dataset_setting.dataset,
            problem_id=problem_id,
            output_dir=str(Path(output_root) / experiment_name),
            status="completed",
            collected_count=len(collected_repeat_indices),
            attempted_repeats=attempted_repeats,
            collected_repeat_indices=tuple(collected_repeat_indices),
            collected_run_seeds=tuple(collected_run_seeds),
        )

    def _record_seed_bank_problem(
        self,
        *,
        dataset_setting: DatasetSetting,
        problem_id: str,
        machines: tuple[Machine, ...],
        collected_repeat_indices: tuple[int, ...],
        collected_run_seeds: tuple[int, ...],
    ) -> None:
        variant_keys: list[str] = []
        for machine in machines:
            key = variant_key(machine.solver_id, machine.param_set_index)
            config = solver_config_snapshot(
                machine._solver_configs.get(machine.solver_id, machine.param_set_index)
            )
            existing = self._seed_bank_variants.get(key)
            if existing is not None and existing != config:
                raise RuntimeError(f"conflicting seed bank variant snapshot: {key!r}")
            self._seed_bank_variants[key] = config
            variant_keys.append(key)
        self._seed_bank_problem_entries.append(
            problem_seed_entry(
                dataset_experiment_id=dataset_setting.experiment_id,
                dataset=dataset_setting.dataset,
                problem_type=dataset_setting.problem_type,
                problem_id=problem_id,
                collected_repeat_indices=collected_repeat_indices,
                run_seeds=collected_run_seeds,
                variant_keys=variant_keys,
            )
        )


def register(name: str, evaluator: RoundEvaluator) -> None:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("evaluator name cannot be empty.")
    if not callable(evaluator):
        raise TypeError("evaluator must be callable.")
    _EVALUATORS[name.strip()] = evaluator


def _clear_registered_evaluators_for_tests() -> None:
    _EVALUATORS.clear()


def build(
    exp_path: Path,
    *,
    problem_root: Path = Path("configs/problems"),
    solver_root: Path = Path("configs/solvers"),
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
    problem_root: Path | str = Path("configs/problems"),
    solver_root: Path | str = Path("configs/solvers"),
    output_root: Path | str = Path("output"),
) -> ExperimentReport:
    return experiment.run(
        problem_root=problem_root,
        solver_root=solver_root,
        output_root=output_root,
    )


def _assert_configured_evaluators_registered(cfg: ExperimentConfig) -> None:
    missing = sorted(
        {
            evaluation.name
            for dataset_setting in cfg.dataset_settings
            for problem_setting in dataset_setting.problem_settings
            for evaluation in problem_setting.evaluations
            if evaluation.name not in _EVALUATORS
        }
    )
    if missing:
        raise KeyError(f"unknown evaluator: {missing!r}")


def _evaluate_candidate_round(
    *,
    dataset_setting: DatasetSetting,
    problem_setting: ProblemSetting,
    problem_id: str,
    repeat_index: int,
    round_result: SimulatorResult,
    collected_result: SimulatorResult,
    projected_result: SimulatorResult,
) -> tuple[RoundEvalDecision, ...]:
    projected_summaries = _variant_summaries(projected_result)
    decisions: list[RoundEvalDecision] = []
    for evaluation in problem_setting.evaluations:
        evaluator = _EVALUATORS[evaluation.name]
        decisions.append(
            evaluator(
                RoundEvalInput(
                    dataset_setting=dataset_setting,
                    problem_setting=problem_setting,
                    problem_id=problem_id,
                    repeat_index=repeat_index,
                    evaluation=evaluation,
                    evaluation_name=evaluation.name,
                    variant_summaries=projected_summaries,
                    simulator_result=round_result,
                    collected_result=collected_result,
                    candidate_result=round_result,
                    projected_result=projected_result,
                )
            )
        )
    return tuple(decisions)


def _selected_machines(
    simulators: tuple[Simulator, ...],
    solver_variants: tuple[tuple[str, int], ...],
) -> tuple[Machine, ...]:
    by_variant = {
        (machine.solver_id, machine.param_set_index): machine
        for simulator in simulators
        for machine in simulator.machines
    }
    machines: list[Machine] = []
    for variant in solver_variants:
        if variant not in by_variant:
            raise KeyError(f"selected solver variant is not available: {variant!r}")
        machines.append(by_variant[variant])
    return tuple(machines)


def _repeat_window_size(worker_count: int, variant_count: int) -> int:
    if variant_count <= 0:
        raise ValueError("variant_count must be > 0.")
    return max(1, math.ceil(worker_count / variant_count))


def _window_tasks(
    machines: tuple[Machine, ...],
    *,
    problem_id: str,
    repeat_indices: tuple[int, ...],
) -> list[RunTask]:
    return [
        machine.expand_task(
            problem_id=problem_id,
            repeat_index=repeat_index,
            base_seed=EXP_BASE_SEED,
        )
        for repeat_index in repeat_indices
        for machine in machines
    ]


def _result_for_repeat(
    machines: tuple[Machine, ...],
    *,
    window_result: SimulatorResult,
    problem_id: str,
    repeat_index: int,
) -> SimulatorResult:
    window_by_variant = window_result.by_variant
    return SimulatorResult(
        machine_results=tuple(
            MachineResult(
                solver_id=machine.solver_id,
                param_set_index=machine.param_set_index,
                params=machine.params,
                rows=tuple(
                    row
                    for row in window_by_variant[(machine.solver_id, machine.param_set_index)].rows
                    if row.task.problem_id == problem_id
                    and row.task.repeat_index == repeat_index
                ),
            )
            for machine in machines
        )
    )


def _copy_rows_by_variant(
    rows_by_variant: dict[tuple[str, int], list[SimulatorRunRow]],
) -> dict[tuple[str, int], list[SimulatorRunRow]]:
    return {key: list(rows) for key, rows in rows_by_variant.items()}


def _append_round_rows(
    rows_by_variant: dict[tuple[str, int], list[SimulatorRunRow]],
    round_result: SimulatorResult,
) -> None:
    for machine_result in round_result.machine_results:
        rows_by_variant[(machine_result.solver_id, machine_result.param_set_index)].extend(
            machine_result.rows
        )


def _machine_results_from_rows(
    machines: tuple[Machine, ...],
    rows_by_variant: dict[tuple[str, int], list[SimulatorRunRow]],
) -> tuple[MachineResult, ...]:
    return tuple(
        MachineResult(
            solver_id=machine.solver_id,
            param_set_index=machine.param_set_index,
            params=machine.params,
            rows=tuple(rows_by_variant[(machine.solver_id, machine.param_set_index)]),
        )
        for machine in machines
    )


def _shared_round_seed(
    round_result: SimulatorResult,
    problem_id: str,
    repeat_index: int,
) -> int:
    rows = round_result.by_run(problem_id, repeat_index)
    if not rows:
        raise RuntimeError(f"round produced no rows: problem_id={problem_id!r}, repeat_index={repeat_index!r}")
    seeds = {row.task.task_seed for row in rows}
    if len(seeds) != 1:
        raise RuntimeError(
            "round tasks must share one seed: "
            f"problem_id={problem_id!r} repeat_index={repeat_index!r} seeds={sorted(seeds)!r}"
        )
    return next(iter(seeds))


def _variant_summaries(simulator_result: SimulatorResult) -> tuple[VariantSummary, ...]:
    variants: list[VariantSummary] = []
    for machine_result in sorted(
        simulator_result.machine_results,
        key=lambda result: (result.solver_id, result.param_set_index),
    ):
        entries = machine_result_entries(machine_result)
        variants.append(
            VariantSummary(
                solver_id=machine_result.solver_id,
                param_set_index=machine_result.param_set_index,
                params=machine_result.params,
                summary=summarize(
                    entries,
                    meta=SummaryMeta(
                        solver_id=machine_result.solver_id,
                        param_set_index=machine_result.param_set_index,
                        params=machine_result.params,
                    ),
                ),
            )
        )
    return tuple(variants)


@dataclass
class _CollectionProgress:
    cfg: ExperimentConfig

    def __post_init__(self) -> None:
        self._counts = {
            (dataset_setting.experiment_id, problem_setting.problem_id): 0
            for dataset_setting in self.cfg.dataset_settings
            for problem_setting in dataset_setting.problem_settings
        }
        self._evaluated_round_count = 0

    def record_evaluation(self) -> None:
        self._evaluated_round_count += 1
        if self._evaluated_round_count % COLLECTION_PROGRESS_INTERVAL == 0:
            self.emit()

    def set_count(
        self,
        *,
        dataset_setting: DatasetSetting,
        problem_id: str,
        collected_count: int,
    ) -> None:
        self._counts[(dataset_setting.experiment_id, problem_id)] = collected_count

    @property
    def remaining(self) -> int:
        return sum(max(0, self.cfg.collects - count) for count in self._counts.values())

    def emit(self) -> None:
        lines = []
        for index, dataset_setting in enumerate(self.cfg.dataset_settings):
            parts = [
                f"{problem_setting.problem_id}: "
                f"{self._counts[(dataset_setting.experiment_id, problem_setting.problem_id)]}/{self.cfg.collects}"
                for problem_setting in dataset_setting.problem_settings
            ]
            line = f"[{dataset_setting.experiment_id}] " + " ".join(parts)
            if index == len(self.cfg.dataset_settings) - 1:
                line += f" | remaining: {self.remaining}"
            lines.append(line)
        print("\n".join(lines), file=sys.stderr, flush=True)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
