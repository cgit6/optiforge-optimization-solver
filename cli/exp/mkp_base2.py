from __future__ import annotations

import math
from typing import Any

from ...experiment import FAIL, PASS, RoundEvalDecision, RoundEvalInput, VariantSummary

TARGET_SOLVER_ID = "brlsmasca_rl_numba"
PDEV_MARGIN_005 = 0.05


def mkp_base2_evaluator(input_data: RoundEvalInput) -> RoundEvalDecision:
    summary_failures = _summary_failures(input_data.variant_summaries)
    if summary_failures:
        return RoundEvalDecision(
            passed=False,
            verdict=FAIL,
            message="Some projected variant summaries are invalid.",
            details={"failures": summary_failures},
        )

    variant_pdevs = _variant_pdevs(input_data.variant_summaries)
    target_pdevs = {
        variant_key: pdev
        for variant_key, pdev in variant_pdevs.items()
        if variant_key.startswith(f"{TARGET_SOLVER_ID}/")
    }
    if not target_pdevs:
        return RoundEvalDecision(
            passed=False,
            verdict=FAIL,
            message=f"{TARGET_SOLVER_ID} is not present in projected variant summaries.",
            details={"variant_pdevs": variant_pdevs},
        )

    competitor_pdevs = {
        variant_key: pdev
        for variant_key, pdev in variant_pdevs.items()
        if not variant_key.startswith(f"{TARGET_SOLVER_ID}/")
    }
    worse_targets = [
        {
            "target": target_variant,
            "target_pdev": target_pdev,
            "competitor": competitor_variant,
            "competitor_pdev": competitor_pdev,
        }
        for target_variant, target_pdev in target_pdevs.items()
        for competitor_variant, competitor_pdev in competitor_pdevs.items()
        if not _lte(target_pdev, competitor_pdev)
    ]
    if worse_targets:
        return RoundEvalDecision(
            passed=False,
            verdict=FAIL,
            message=f"{TARGET_SOLVER_ID} is not the best projected variant.",
            details={
                "target_pdevs": target_pdevs,
                "competitor_pdevs": competitor_pdevs,
                "worse_targets": worse_targets,
            },
        )

    return RoundEvalDecision(
        passed=True,
        verdict=PASS,
        message=f"{TARGET_SOLVER_ID} is at least tied for best projected Pdev.",
        details={
            "target_pdevs": target_pdevs,
            "competitor_pdevs": competitor_pdevs,
        },
    )


def mkp_base2_margin_005_evaluator(input_data: RoundEvalInput) -> RoundEvalDecision:
    summary_failures = _summary_failures(input_data.variant_summaries)
    if summary_failures:
        return RoundEvalDecision(
            passed=False,
            verdict=FAIL,
            message="Some projected variant summaries are invalid.",
            details={"failures": summary_failures},
        )

    variant_pdevs = _variant_pdevs(input_data.variant_summaries)
    target_pdevs = {
        variant_key: pdev
        for variant_key, pdev in variant_pdevs.items()
        if variant_key.startswith(f"{TARGET_SOLVER_ID}/")
    }
    if not target_pdevs:
        return RoundEvalDecision(
            passed=False,
            verdict=FAIL,
            message=f"{TARGET_SOLVER_ID} is not present in projected variant summaries.",
            details={"variant_pdevs": variant_pdevs},
        )

    best_pdev = min(variant_pdevs.values())
    threshold_pdev = best_pdev + PDEV_MARGIN_005
    worse_targets = [
        {
            "target": target_variant,
            "target_pdev": target_pdev,
            "best_pdev": best_pdev,
            "threshold_pdev": threshold_pdev,
            "margin_pdev": PDEV_MARGIN_005,
        }
        for target_variant, target_pdev in target_pdevs.items()
        if not _lte(target_pdev, threshold_pdev)
    ]
    if worse_targets:
        return RoundEvalDecision(
            passed=False,
            verdict=FAIL,
            message=f"{TARGET_SOLVER_ID} is more than {PDEV_MARGIN_005} Pdev from the best projected variant.",
            details={
                "best_pdev": best_pdev,
                "threshold_pdev": threshold_pdev,
                "margin_pdev": PDEV_MARGIN_005,
                "target_pdevs": target_pdevs,
                "variant_pdevs": variant_pdevs,
                "worse_targets": worse_targets,
            },
        )

    return RoundEvalDecision(
        passed=True,
        verdict=PASS,
        message=f"{TARGET_SOLVER_ID} is within {PDEV_MARGIN_005} Pdev of the best projected variant.",
        details={
            "best_pdev": best_pdev,
            "threshold_pdev": threshold_pdev,
            "margin_pdev": PDEV_MARGIN_005,
            "target_pdevs": target_pdevs,
            "variant_pdevs": variant_pdevs,
        },
    )


def _summary_failures(variant_summaries: tuple[VariantSummary, ...]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for variant in variant_summaries:
        overall = variant.summary.overall
        excluded = overall.excluded_counts
        excluded_total = excluded.infeasible + excluded.objective_mismatch + excluded.runtime_error
        if (
            overall.total_runs <= 0
            or overall.valid_run_count != overall.total_runs
            or not math.isclose(overall.feasible_rate, 1.0)
            or overall.pdev is None
            or excluded_total != 0
        ):
            failures.append(
                {
                    "solver_id": variant.solver_id,
                    "param_set_index": variant.param_set_index,
                    "total_runs": overall.total_runs,
                    "valid_run_count": overall.valid_run_count,
                    "feasible_rate": overall.feasible_rate,
                    "pdev": overall.pdev,
                    "excluded_counts": {
                        "infeasible": excluded.infeasible,
                        "objective_mismatch": excluded.objective_mismatch,
                        "runtime_error": excluded.runtime_error,
                    },
                }
            )
    return failures


def _variant_pdevs(variant_summaries: tuple[VariantSummary, ...]) -> dict[str, float]:
    return {
        _variant_key(variant): float(variant.summary.overall.pdev)
        for variant in variant_summaries
        if variant.summary.overall.pdev is not None
    }


def _variant_key(variant: VariantSummary) -> str:
    return f"{variant.solver_id}/param_{variant.param_set_index}"


def _lte(value: float, threshold: float) -> bool:
    return value <= threshold or math.isclose(value, threshold, rel_tol=1e-12, abs_tol=1e-12)
