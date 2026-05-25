from __future__ import annotations

import math
from typing import Any

from ...experiment import FAIL, PASS, RoundEvalDecision, RoundEvalInput, VariantSummary

BASELINE_TARGET_SOLVER_IDS = ("bsma_numba", "brlsmasca_rl_numba")
BSCA_SOLVER_ID = "bsca_numba"
BSCA_BASELINE_MARGIN = 2.0


def mkp_base_evaluator(input_data: RoundEvalInput) -> RoundEvalDecision:
    baseline_pdevs = [
        baseline.pdev
        for baseline in input_data.evaluation.base_line
        if baseline.pdev is not None
    ]
    if not baseline_pdevs:
        return RoundEvalDecision(
            passed=False,
            verdict=FAIL,
            message="mkp_base requires at least one baseline Pdev.",
        )

    summary_failures = _summary_failures(input_data.variant_summaries)
    if summary_failures:
        return RoundEvalDecision(
            passed=False,
            verdict=FAIL,
            message="Some projected variant summaries are invalid.",
            details={"failures": summary_failures},
        )

    threshold = min(baseline_pdevs)
    variant_pdevs = _variant_pdevs(input_data.variant_summaries)
    target_pdevs = _target_pdevs(variant_pdevs, BASELINE_TARGET_SOLVER_IDS)
    missing_targets = [
        solver_id
        for solver_id in BASELINE_TARGET_SOLVER_IDS
        if not _has_solver_pdev(target_pdevs, solver_id)
    ]
    if missing_targets:
        return RoundEvalDecision(
            passed=False,
            verdict=FAIL,
            message="mkp_base target solver is not present in projected variant summaries.",
            details={
                "missing_targets": missing_targets,
                "target_solver_ids": BASELINE_TARGET_SOLVER_IDS,
                "variant_pdevs": variant_pdevs,
            },
        )

    worse_variants = [
        {"variant": variant, "pdev": pdev, "threshold": threshold}
        for variant, pdev in target_pdevs.items()
        if not _lte(pdev, threshold)
    ]
    if worse_variants:
        return RoundEvalDecision(
            passed=False,
            verdict=FAIL,
            message="Some target variants are worse than the best baseline Pdev.",
            details={
                "threshold_pdev": threshold,
                "target_solver_ids": BASELINE_TARGET_SOLVER_IDS,
                "target_pdevs": target_pdevs,
                "variant_pdevs": variant_pdevs,
                "worse_variants": worse_variants,
            },
        )

    return RoundEvalDecision(
        passed=True,
        verdict=PASS,
        message="BSMA and BRLSMASCA RL are at least as good as the best baseline Pdev.",
        details={
            "threshold_pdev": threshold,
            "target_solver_ids": BASELINE_TARGET_SOLVER_IDS,
            "target_pdevs": target_pdevs,
            "variant_pdevs": variant_pdevs,
        },
    )


def mkp_bsca_base_margin_2_evaluator(input_data: RoundEvalInput) -> RoundEvalDecision:
    baseline_pdevs = [
        baseline.pdev
        for baseline in input_data.evaluation.base_line
        if baseline.pdev is not None
    ]
    if not baseline_pdevs:
        return RoundEvalDecision(
            passed=False,
            verdict=FAIL,
            message="mkp_bsca_base_margin_2 requires at least one baseline Pdev.",
        )

    summary_failures = _summary_failures(input_data.variant_summaries)
    if summary_failures:
        return RoundEvalDecision(
            passed=False,
            verdict=FAIL,
            message="Some projected variant summaries are invalid.",
            details={"failures": summary_failures},
        )

    baseline_threshold = min(baseline_pdevs)
    threshold = baseline_threshold + BSCA_BASELINE_MARGIN
    variant_pdevs = _variant_pdevs(input_data.variant_summaries)
    bsca_pdevs = _target_pdevs(variant_pdevs, (BSCA_SOLVER_ID,))
    if not bsca_pdevs:
        return RoundEvalDecision(
            passed=False,
            verdict=FAIL,
            message=f"{BSCA_SOLVER_ID} is not present in projected variant summaries.",
            details={"variant_pdevs": variant_pdevs},
        )

    worse_variants = [
        {"variant": variant, "pdev": pdev, "threshold": threshold}
        for variant, pdev in bsca_pdevs.items()
        if not _lte(pdev, threshold)
    ]
    if worse_variants:
        return RoundEvalDecision(
            passed=False,
            verdict=FAIL,
            message=f"{BSCA_SOLVER_ID} is more than {BSCA_BASELINE_MARGIN} Pdev worse than the best baseline.",
            details={
                "baseline_threshold_pdev": baseline_threshold,
                "threshold_pdev": threshold,
                "margin_pdev": BSCA_BASELINE_MARGIN,
                "bsca_pdevs": bsca_pdevs,
                "variant_pdevs": variant_pdevs,
                "worse_variants": worse_variants,
            },
        )

    return RoundEvalDecision(
        passed=True,
        verdict=PASS,
        message=f"{BSCA_SOLVER_ID} is within {BSCA_BASELINE_MARGIN} Pdev of the best baseline.",
        details={
            "baseline_threshold_pdev": baseline_threshold,
            "threshold_pdev": threshold,
            "margin_pdev": BSCA_BASELINE_MARGIN,
            "bsca_pdevs": bsca_pdevs,
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


def _target_pdevs(variant_pdevs: dict[str, float], solver_ids: tuple[str, ...]) -> dict[str, float]:
    return {
        variant: pdev
        for variant, pdev in variant_pdevs.items()
        if any(variant.startswith(f"{solver_id}/") for solver_id in solver_ids)
    }


def _has_solver_pdev(variant_pdevs: dict[str, float], solver_id: str) -> bool:
    return any(variant.startswith(f"{solver_id}/") for variant in variant_pdevs)


def _lte(value: float, threshold: float) -> bool:
    return value <= threshold or math.isclose(value, threshold, rel_tol=1e-12, abs_tol=1e-12)
