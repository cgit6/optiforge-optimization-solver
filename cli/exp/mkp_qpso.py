from __future__ import annotations

import math
from typing import Any

from ...experiment import FAIL, PASS, RoundEvalDecision, RoundEvalInput, VariantSummary

TARGET_SOLVER_ID = "brlsmasca_rl_rc_numba"
TARGET_PARAM_SET_INDEX = 20
FLOAT_TOLERANCE = 1e-12


def mkp_qpso_mean_gte_evaluator(input_data: RoundEvalInput) -> RoundEvalDecision:
    qpso_mean = _qpso_mean(input_data)
    if qpso_mean is None:
        return RoundEvalDecision(
            passed=False,
            verdict=FAIL,
            message="mkp_qpso_mean_gte requires a QPSO baseline with eval=mean.",
        )

    target = _target_variant(input_data.variant_summaries)
    if target is None:
        return RoundEvalDecision(
            passed=False,
            verdict=FAIL,
            message=f"{TARGET_SOLVER_ID}/param_{TARGET_PARAM_SET_INDEX} is not present.",
            details={"target_solver_id": TARGET_SOLVER_ID, "target_param_set_index": TARGET_PARAM_SET_INDEX},
        )

    invalid = _summary_failure(target)
    if invalid is not None:
        return RoundEvalDecision(
            passed=False,
            verdict=FAIL,
            message="Target projected summary is invalid.",
            details={"failure": invalid},
        )

    target_mean = float(target.summary.overall.avg_objective)
    passed = _gte(target_mean, qpso_mean)
    return RoundEvalDecision(
        passed=passed,
        verdict=PASS if passed else FAIL,
        message=(
            f"{TARGET_SOLVER_ID}/param_{TARGET_PARAM_SET_INDEX} projected mean is at least QPSO Mean."
            if passed
            else f"{TARGET_SOLVER_ID}/param_{TARGET_PARAM_SET_INDEX} projected mean is below QPSO Mean."
        ),
        details={
            "target": f"{TARGET_SOLVER_ID}/param_{TARGET_PARAM_SET_INDEX}",
            "target_mean": target_mean,
            "qpso_mean": qpso_mean,
            "gap_to_qpso_mean": target_mean - qpso_mean,
        },
    )


def _qpso_mean(input_data: RoundEvalInput) -> float | None:
    for baseline in input_data.evaluation.base_line:
        if baseline.name.strip().lower() == "qpso" and baseline.metric == "mean":
            return float(baseline.value)
    return None


def _target_variant(variant_summaries: tuple[VariantSummary, ...]) -> VariantSummary | None:
    for variant in variant_summaries:
        if variant.solver_id == TARGET_SOLVER_ID and variant.param_set_index == TARGET_PARAM_SET_INDEX:
            return variant
    return None


def _summary_failure(variant: VariantSummary) -> dict[str, Any] | None:
    overall = variant.summary.overall
    excluded = overall.excluded_counts
    excluded_total = excluded.infeasible + excluded.objective_mismatch + excluded.runtime_error
    if (
        overall.total_runs <= 0
        or overall.valid_run_count != overall.total_runs
        or not math.isclose(overall.feasible_rate, 1.0)
        or overall.avg_objective is None
        or excluded_total != 0
    ):
        return {
            "solver_id": variant.solver_id,
            "param_set_index": variant.param_set_index,
            "total_runs": overall.total_runs,
            "valid_run_count": overall.valid_run_count,
            "feasible_rate": overall.feasible_rate,
            "avg_objective": overall.avg_objective,
            "excluded_counts": {
                "infeasible": excluded.infeasible,
                "objective_mismatch": excluded.objective_mismatch,
                "runtime_error": excluded.runtime_error,
            },
        }
    return None


def _gte(value: float, threshold: float) -> bool:
    return value > threshold or math.isclose(value, threshold, rel_tol=FLOAT_TOLERANCE, abs_tol=FLOAT_TOLERANCE)
