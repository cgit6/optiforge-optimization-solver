from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from statistics import mean
from typing import Any, Callable, Literal

from scipy.stats import wilcoxon

from .config import ExperimentConfig, StaticBaseline
from ..tools.stat import SummaryReport


Verdict = Literal["STRICT_PASS", "SOFT_PASS", "FAIL"]
STRICT_PASS: Verdict = "STRICT_PASS"
SOFT_PASS: Verdict = "SOFT_PASS"
FAIL: Verdict = "FAIL"
PASSING_VERDICTS = frozenset({STRICT_PASS, SOFT_PASS})


@dataclass(frozen=True)
class CheckResult:
    name: str
    verdict: Verdict
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProblemMetric:
    stage: str
    dataset_experiment_id: str
    dataset: str
    problem_id: str
    problem_type: str
    combo_id: str
    algorithm: str
    pdev: float
    rank: float | None
    avg_objective: float | None
    best_objective: float | None
    best_known: float | None
    direction: str
    source: str


@dataclass(frozen=True)
class ComboMetric:
    stage: str
    combo_id: str
    algorithm: str
    avg_pdev: float
    avg_rank: float
    problem_count: int
    params: dict[str, Any] = field(default_factory=dict)
    transfer_type: str | None = None
    source: str = "simulated"


@dataclass(frozen=True)
class StageSummary:
    stage: str
    dataset_experiment_id: str
    dataset: str
    combo_id: str
    algorithm: str
    solver_id: str
    param_set_index: int
    params: dict[str, Any]
    transfer_type: str | None
    summary: SummaryReport
    source: str = "simulated"


@dataclass(frozen=True)
class EvaluationReport:
    seed: int
    verdict: Verdict
    checks: tuple[CheckResult, ...]
    problem_metrics: tuple[ProblemMetric, ...]
    combo_metrics: tuple[ComboMetric, ...]
    wilcoxon: dict[str, Any] = field(default_factory=dict)
    best_transfer: dict[str, Any] = field(default_factory=dict)
    best_params: dict[str, Any] = field(default_factory=dict)
    final_all_level_metrics: dict[str, Any] = field(default_factory=dict)


Evaluator = Callable[[ExperimentConfig, int, tuple[StageSummary, ...]], EvaluationReport]


def literature_mkp_evaluator(
    cfg: ExperimentConfig,
    seed: int,
    summaries: tuple[StageSummary, ...],
) -> EvaluationReport:
    checks: list[CheckResult] = []
    checks.extend(_validity_checks(cfg, summaries))

    simulated_metrics = _simulated_problem_metrics(summaries)
    static_metrics = _static_problem_metrics(cfg.static_baselines)
    problem_metrics = simulated_metrics + static_metrics
    _assign_average_ranks(problem_metrics)
    combo_metrics = _combo_metrics(problem_metrics, summaries)

    checks.append(_stage_data_check(problem_metrics))
    transfer_check, best_transfer = _transfer_check(cfg, combo_metrics)
    checks.append(transfer_check)
    param_check, best_params = _param_check(cfg, combo_metrics)
    checks.append(param_check)
    final_check, final_all_level = _final_check(cfg, combo_metrics)
    checks.append(final_check)
    wilcoxon_check, wilcoxon_details = _wilcoxon_check(cfg, problem_metrics, combo_metrics)
    checks.append(wilcoxon_check)

    verdict = _overall_verdict(checks)
    return EvaluationReport(
        seed=seed,
        verdict=verdict,
        checks=tuple(checks),
        problem_metrics=tuple(problem_metrics),
        combo_metrics=tuple(combo_metrics),
        wilcoxon=wilcoxon_details,
        best_transfer=best_transfer,
        best_params=best_params,
        final_all_level_metrics=final_all_level,
    )


def _validity_checks(cfg: ExperimentConfig, summaries: tuple[StageSummary, ...]) -> list[CheckResult]:
    failures: list[dict[str, Any]] = []
    for stage_summary in summaries:
        for group in stage_summary.summary.by_problem_solver:
            excluded = group.excluded_counts
            excluded_total = excluded.infeasible + excluded.objective_mismatch + excluded.runtime_error
            if (
                group.run_count != cfg.repeat
                or group.valid_run_count != cfg.repeat
                or not math.isclose(group.feasible_rate, 1.0)
                or group.avg_objective is None
                or group.best_known is None
                or excluded_total != 0
            ):
                failures.append(
                    {
                        "stage": stage_summary.stage,
                        "combo_id": stage_summary.combo_id,
                        "dataset": group.dataset,
                        "problem_id": group.problem_id,
                        "run_count": group.run_count,
                        "valid_run_count": group.valid_run_count,
                        "feasible_rate": group.feasible_rate,
                        "avg_objective": group.avg_objective,
                        "best_known": group.best_known,
                        "excluded_counts": {
                            "infeasible": excluded.infeasible,
                            "objective_mismatch": excluded.objective_mismatch,
                            "runtime_error": excluded.runtime_error,
                        },
                    }
                )
    if failures:
        return [
            CheckResult(
                name="validity",
                verdict=FAIL,
                message="Some simulated summaries are invalid for literature comparison.",
                details={"failures": failures},
            )
        ]
    return [
        CheckResult(
            name="validity",
            verdict=STRICT_PASS,
            message="All simulated summaries are feasible and complete.",
        )
    ]


def _simulated_problem_metrics(summaries: tuple[StageSummary, ...]) -> list[ProblemMetric]:
    metrics: list[ProblemMetric] = []
    for stage_summary in summaries:
        for group in stage_summary.summary.by_problem_solver:
            pdev = _pdev(
                avg_objective=group.avg_objective,
                best_known=group.best_known,
                direction=group.direction,
            )
            if pdev is None:
                continue
            metrics.append(
                ProblemMetric(
                    stage=stage_summary.stage,
                    dataset_experiment_id=stage_summary.dataset_experiment_id,
                    dataset=group.dataset,
                    problem_id=group.problem_id,
                    problem_type=group.problem_type,
                    combo_id=stage_summary.combo_id,
                    algorithm=stage_summary.algorithm,
                    pdev=pdev,
                    rank=None,
                    avg_objective=float(group.avg_objective) if group.avg_objective is not None else None,
                    best_objective=float(group.best_objective) if group.best_objective is not None else None,
                    best_known=float(group.best_known) if group.best_known is not None else None,
                    direction=group.direction,
                    source=stage_summary.source,
                )
            )
    return metrics


def _static_problem_metrics(static_baselines: tuple[StaticBaseline, ...]) -> list[ProblemMetric]:
    metrics: list[ProblemMetric] = []
    for baseline in static_baselines:
        for result in baseline.results:
            metrics.append(
                ProblemMetric(
                    stage="final",
                    dataset_experiment_id="static_baseline",
                    dataset=result.dataset,
                    problem_id=result.problem,
                    problem_type=result.problem_type,
                    combo_id=baseline.combo_id,
                    algorithm=baseline.algorithm,
                    pdev=result.pdev,
                    rank=None,
                    avg_objective=result.avg,
                    best_objective=result.best,
                    best_known=None,
                    direction=result.direction,
                    source="static",
                )
            )
    return metrics


def _pdev(
    *,
    avg_objective: int | float | None,
    best_known: int | float | None,
    direction: str,
) -> float | None:
    if avg_objective is None or best_known in (None, 0):
        return None
    if direction == "max":
        return (float(best_known) - float(avg_objective)) / float(best_known) * 100.0
    if direction == "min":
        return (float(avg_objective) - float(best_known)) / float(best_known) * 100.0
    return None


def _assign_average_ranks(metrics: list[ProblemMetric]) -> None:
    grouped: dict[tuple[str, str, str], list[ProblemMetric]] = defaultdict(list)
    for metric in metrics:
        grouped[(metric.stage, metric.dataset, metric.problem_id)].append(metric)

    for bucket in grouped.values():
        ordered = sorted(bucket, key=lambda item: item.pdev)
        index = 0
        while index < len(ordered):
            end = index + 1
            while end < len(ordered) and math.isclose(ordered[end].pdev, ordered[index].pdev, abs_tol=1e-12):
                end += 1
            rank = (index + 1 + end) / 2.0
            for item in ordered[index:end]:
                item.rank = rank
            index = end


def _combo_metrics(
    problem_metrics: list[ProblemMetric],
    summaries: tuple[StageSummary, ...],
) -> tuple[ComboMetric, ...]:
    metadata_by_combo = {
        (summary.stage, summary.combo_id): summary
        for summary in summaries
    }
    grouped: dict[tuple[str, str], list[ProblemMetric]] = defaultdict(list)
    for metric in problem_metrics:
        grouped[(metric.stage, metric.combo_id)].append(metric)

    combo_metrics: list[ComboMetric] = []
    for (stage, combo_id), bucket in sorted(grouped.items()):
        first = bucket[0]
        summary = metadata_by_combo.get((stage, combo_id))
        combo_metrics.append(
            ComboMetric(
                stage=stage,
                combo_id=combo_id,
                algorithm=first.algorithm,
                avg_pdev=mean(item.pdev for item in bucket),
                avg_rank=mean(float(item.rank or 0.0) for item in bucket),
                problem_count=len(bucket),
                params=dict(summary.params) if summary else {},
                transfer_type=summary.transfer_type if summary else None,
                source=first.source,
            )
        )
    return tuple(combo_metrics)


def _stage_data_check(problem_metrics: list[ProblemMetric]) -> CheckResult:
    present = {metric.stage for metric in problem_metrics}
    missing = sorted(set(("transfer", "param", "final")) - present)
    if missing:
        return CheckResult(
            name="stage_data",
            verdict=FAIL,
            message="Evaluation input is missing required stage data.",
            details={"missing": missing},
        )
    return CheckResult(name="stage_data", verdict=STRICT_PASS)


def _transfer_check(
    cfg: ExperimentConfig,
    combo_metrics: tuple[ComboMetric, ...],
) -> tuple[CheckResult, dict[str, Any]]:
    transfer_metrics = [metric for metric in combo_metrics if metric.stage == "transfer" and metric.transfer_type]
    if not transfer_metrics:
        return (
            CheckResult(name="transfer", verdict=FAIL, message="No transfer variants were evaluated."),
            {},
        )

    best_by_type: dict[str, ComboMetric] = {}
    for metric in transfer_metrics:
        key = str(metric.transfer_type)
        if key not in best_by_type or metric.avg_pdev < best_by_type[key].avg_pdev:
            best_by_type[key] = metric

    best = min(best_by_type.values(), key=lambda item: item.avg_pdev)
    v_metric = best_by_type.get("V")
    details = {
        transfer_type: {
            "combo_id": metric.combo_id,
            "avg_pdev": metric.avg_pdev,
            "avg_rank": metric.avg_rank,
        }
        for transfer_type, metric in sorted(best_by_type.items())
    }
    if v_metric is None:
        return (
            CheckResult(
                name="transfer",
                verdict=FAIL,
                message="V-type transfer variant is required for the literature transfer check.",
                details=details,
            ),
            details,
        )
    if v_metric.combo_id == best.combo_id:
        verdict = STRICT_PASS
    elif v_metric.avg_pdev - best.avg_pdev <= cfg.evaluation.pdev_tolerance:
        verdict = SOFT_PASS
    else:
        verdict = FAIL
    return (
        CheckResult(
            name="transfer",
            verdict=verdict,
            message="V-type transfer is best or near-best." if verdict != FAIL else "V-type transfer is not near-best.",
            details=details,
        ),
        details,
    )


def _param_check(
    cfg: ExperimentConfig,
    combo_metrics: tuple[ComboMetric, ...],
) -> tuple[CheckResult, dict[str, Any]]:
    targets = {
        "ISMA": {"z": 0.08},
        "ISCA": {"a": 1.5},
        "HSMSCA": {"z": 0.08, "a": 2.5},
    }
    param_metrics = [metric for metric in combo_metrics if metric.stage == "param"]
    details: dict[str, Any] = {}
    verdicts: list[Verdict] = []

    for algorithm, expected_params in targets.items():
        algorithm_metrics = [metric for metric in param_metrics if metric.algorithm == algorithm]
        if not algorithm_metrics:
            details[algorithm] = {"status": "missing_algorithm"}
            verdicts.append(FAIL)
            continue
        target = _find_metric_by_params(algorithm_metrics, expected_params)
        if target is None:
            details[algorithm] = {"status": "missing_target_params", "expected_params": expected_params}
            verdicts.append(FAIL)
            continue
        best = min(algorithm_metrics, key=lambda item: item.avg_pdev)
        gap = target.avg_pdev - best.avg_pdev
        if target.combo_id == best.combo_id:
            verdict: Verdict = STRICT_PASS
        elif gap <= cfg.evaluation.pdev_tolerance:
            verdict = SOFT_PASS
        else:
            verdict = FAIL
        verdicts.append(verdict)
        details[algorithm] = {
            "verdict": verdict,
            "target_combo_id": target.combo_id,
            "best_combo_id": best.combo_id,
            "target_avg_pdev": target.avg_pdev,
            "best_avg_pdev": best.avg_pdev,
            "gap": gap,
            "expected_params": expected_params,
        }

    return (
        CheckResult(
            name="param",
            verdict=_merge_verdicts(verdicts),
            message="Target parameter settings are best or near-best.",
            details=details,
        ),
        details,
    )


def _find_metric_by_params(metrics: list[ComboMetric], expected: dict[str, float]) -> ComboMetric | None:
    for metric in metrics:
        if all(_numbers_close(metric.params.get(key), value) for key, value in expected.items()):
            return metric
    return None


def _numbers_close(actual: Any, expected: float) -> bool:
    if isinstance(actual, bool) or not isinstance(actual, (int, float)):
        return False
    return math.isclose(float(actual), float(expected), abs_tol=1e-12)


def _final_check(
    cfg: ExperimentConfig,
    combo_metrics: tuple[ComboMetric, ...],
) -> tuple[CheckResult, dict[str, Any]]:
    final_metrics = [metric for metric in combo_metrics if metric.stage == "final"]
    if not final_metrics:
        return (
            CheckResult(name="final", verdict=FAIL, message="No final variants were evaluated."),
            {},
        )
    target_metrics = [metric for metric in final_metrics if metric.algorithm == cfg.evaluation.target_algorithm]
    if not target_metrics:
        return (
            CheckResult(
                name="final",
                verdict=FAIL,
                message=f"Target algorithm {cfg.evaluation.target_algorithm!r} is missing in final stage.",
            ),
            {},
        )
    best_target = min(target_metrics, key=lambda item: item.avg_pdev)
    best_pdev = min(final_metrics, key=lambda item: item.avg_pdev)
    best_rank = min(final_metrics, key=lambda item: item.avg_rank)
    pdev_gap = best_target.avg_pdev - best_pdev.avg_pdev
    rank_gap = best_target.avg_rank - best_rank.avg_rank
    if best_target.combo_id == best_pdev.combo_id and best_target.combo_id == best_rank.combo_id:
        verdict: Verdict = STRICT_PASS
    elif pdev_gap <= cfg.evaluation.pdev_tolerance and rank_gap <= cfg.evaluation.pdev_tolerance:
        verdict = SOFT_PASS
    else:
        verdict = FAIL

    details = {
        "target_combo_id": best_target.combo_id,
        "best_pdev_combo_id": best_pdev.combo_id,
        "best_rank_combo_id": best_rank.combo_id,
        "target_avg_pdev": best_target.avg_pdev,
        "best_avg_pdev": best_pdev.avg_pdev,
        "target_avg_rank": best_target.avg_rank,
        "best_avg_rank": best_rank.avg_rank,
        "pdev_gap": pdev_gap,
        "rank_gap": rank_gap,
    }
    return (
        CheckResult(
            name="final",
            verdict=verdict,
            message="Final target algorithm is best or near-best on Avg.PDev and Avg.Rank.",
            details=details,
        ),
        details,
    )


def _wilcoxon_check(
    cfg: ExperimentConfig,
    problem_metrics: list[ProblemMetric],
    combo_metrics: tuple[ComboMetric, ...],
) -> tuple[CheckResult, dict[str, Any]]:
    final_combo_metrics = [metric for metric in combo_metrics if metric.stage == "final"]
    target_candidates = [metric for metric in final_combo_metrics if metric.algorithm == cfg.evaluation.target_algorithm]
    if not target_candidates:
        return (
            CheckResult(name="wilcoxon", verdict=FAIL, message="Target algorithm is missing in final stage."),
            {},
        )
    target_combo = min(target_candidates, key=lambda item: item.avg_pdev)
    final_problem_metrics = [metric for metric in problem_metrics if metric.stage == "final"]
    by_combo: dict[str, dict[tuple[str, str], float]] = defaultdict(dict)
    algorithm_by_combo: dict[str, str] = {}
    for metric in final_problem_metrics:
        by_combo[metric.combo_id][(metric.dataset, metric.problem_id)] = metric.pdev
        algorithm_by_combo[metric.combo_id] = metric.algorithm

    target_values_by_problem = by_combo.get(target_combo.combo_id, {})
    competitor_details: dict[str, Any] = {}
    all_pass = True
    for competitor in final_combo_metrics:
        if competitor.combo_id == target_combo.combo_id:
            continue
        common_keys = sorted(set(target_values_by_problem) & set(by_combo[competitor.combo_id]))
        target_values = [target_values_by_problem[key] for key in common_keys]
        competitor_values = [by_combo[competitor.combo_id][key] for key in common_keys]
        p_value = _wilcoxon_p_value(target_values, competitor_values)
        mean_target = mean(target_values) if target_values else None
        mean_competitor = mean(competitor_values) if competitor_values else None
        passed = (
            len(common_keys) >= 2
            and p_value is not None
            and p_value < cfg.evaluation.alpha
            and mean_target is not None
            and mean_competitor is not None
            and mean_target < mean_competitor
        )
        all_pass = all_pass and passed
        competitor_details[competitor.combo_id] = {
            "algorithm": algorithm_by_combo.get(competitor.combo_id, competitor.algorithm),
            "paired_problem_count": len(common_keys),
            "target_mean_pdev": mean_target,
            "competitor_mean_pdev": mean_competitor,
            "p_value": p_value,
            "passed": passed,
        }

    if not competitor_details:
        return (
            CheckResult(name="wilcoxon", verdict=FAIL, message="No final competitor exists for Wilcoxon."),
            {"target_combo_id": target_combo.combo_id, "competitors": {}},
        )
    verdict: Verdict = STRICT_PASS if all_pass else FAIL
    return (
        CheckResult(
            name="wilcoxon",
            verdict=verdict,
            message="Target algorithm is significantly better than final competitors.",
            details={"target_combo_id": target_combo.combo_id, "competitors": competitor_details},
        ),
        {"target_combo_id": target_combo.combo_id, "competitors": competitor_details},
    )


def _wilcoxon_p_value(target_values: list[float], competitor_values: list[float]) -> float | None:
    if len(target_values) != len(competitor_values) or len(target_values) < 2:
        return None
    try:
        result = wilcoxon(target_values, competitor_values, alternative="less")
    except ValueError:
        return 1.0
    p_value = float(result.pvalue)
    if math.isnan(p_value):
        return 1.0
    return p_value


def _overall_verdict(checks: list[CheckResult]) -> Verdict:
    verdicts = [check.verdict for check in checks]
    return _merge_verdicts(verdicts)


def _merge_verdicts(verdicts: list[Verdict]) -> Verdict:
    if any(verdict == FAIL for verdict in verdicts):
        return FAIL
    if any(verdict == SOFT_PASS for verdict in verdicts):
        return SOFT_PASS
    return STRICT_PASS
