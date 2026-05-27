from __future__ import annotations

import math
from itertools import product
from typing import Any

from ...experiment import FAIL, PASS, RoundEvalDecision, RoundEvalInput, VariantSummary

EXPECTED_COMBO_COUNT = 45
PDEV_TOLERANCE = 0.0
BSCA_MARGIN_PDEV = 0.05
BRLSMASCA_MARGIN_PDEV = 0.04
BSCA_TRANSFER_MAX_AVG_RANK = 2.0
EXPECTED_CTFS = ("tanh_abs", "sigmoid_s0", "abs_pow_16")
EXPECTED_TRANSFER_CTF = "abs_pow_16"

ALGORITHM_BY_SOLVER_ID = {
    "bsma_numba": "bsma",
    "bsca_numba": "bsca",
    "brlsmasca_rl_numba": "bscasma",
}
EXPECTED_ALGORITHM_COUNTS = {
    "bsma": 9,
    "bsca": 9,
    "bscasma": 27,
}
CORE_ALGORITHMS = ("bsma", "bscasma")
PAIR_KEYS = {
    "bsma": ("z",),
    "bsca": ("a",),
    "bscasma": ("z", "a"),
}
EXPECTED_PAIRS = {
    "bsma": ({"z": 0.01}, {"z": 0.08}, {"z": 0.15}),
    "bsca": ({"a": 1.5}, {"a": 2.0}, {"a": 2.5}),
    "bscasma": tuple(
        {"z": z, "a": a}
        for z, a in product((0.01, 0.08, 0.15), (1.5, 2.0, 2.5))
    ),
}
TARGET_COMBOS = {
    "bsma": {"z": 0.08},
    "bsca": {"a": 1.5},
    "bscasma": {"z": 0.08, "a": 2.5},
}


def mkp_transfer_paired_strict_evaluator(input_data: RoundEvalInput) -> RoundEvalDecision:
    combos, integrity_checks, integrity_failures = _combo_context(input_data.variant_summaries)
    pair_checks = _check_pair_completeness(combos)
    pair_failures = [check for check in pair_checks if not check["passed"]]
    if integrity_failures or pair_failures:
        return RoundEvalDecision(
            passed=False,
            verdict=FAIL,
            message="Calibration combo set is incomplete.",
            details={
                "pdev_tolerance": PDEV_TOLERANCE,
                "integrity_checks": integrity_checks,
                "pair_checks": pair_checks,
                "failures": integrity_failures + pair_failures,
            },
        )

    transfer_checks = _check_transfer_paired(combos)
    failures = [check for check in transfer_checks if not check["passed"]]
    if failures:
        return RoundEvalDecision(
            passed=False,
            verdict=FAIL,
            message=f"{EXPECTED_TRANSFER_CTF} is not the strict paired-average best transfer function.",
            details={
                "pdev_tolerance": PDEV_TOLERANCE,
                "expected_transfer_ctf": EXPECTED_TRANSFER_CTF,
                "integrity_checks": integrity_checks,
                "pair_checks": pair_checks,
                "transfer_checks": transfer_checks,
                "failures": failures,
            },
        )

    return RoundEvalDecision(
        passed=True,
        verdict=PASS,
        message=f"{EXPECTED_TRANSFER_CTF} is the strict paired-average best transfer function.",
        details={
            "pdev_tolerance": PDEV_TOLERANCE,
            "expected_transfer_ctf": EXPECTED_TRANSFER_CTF,
            "integrity_checks": integrity_checks,
            "pair_checks": pair_checks,
            "transfer_checks": transfer_checks,
        },
    )


def mkp_target_combo_best_evaluator(input_data: RoundEvalInput) -> RoundEvalDecision:
    combos, integrity_checks, integrity_failures = _combo_context(input_data.variant_summaries)
    if integrity_failures:
        return RoundEvalDecision(
            passed=False,
            verdict=FAIL,
            message="Calibration combo set is incomplete.",
            details={
                "pdev_tolerance": PDEV_TOLERANCE,
                "integrity_checks": integrity_checks,
                "failures": integrity_failures,
            },
        )

    target_checks = _check_target_combos(combos)
    failures = [check for check in target_checks if not check["passed"]]
    if failures:
        return RoundEvalDecision(
            passed=False,
            verdict=FAIL,
            message="Target parameter combos are not strict best within their algorithms.",
            details={
                "pdev_tolerance": PDEV_TOLERANCE,
                "integrity_checks": integrity_checks,
                "target_checks": target_checks,
                "failures": failures,
            },
        )

    return RoundEvalDecision(
        passed=True,
        verdict=PASS,
        message="Target parameter combos are strict best within their algorithms.",
        details={
            "pdev_tolerance": PDEV_TOLERANCE,
            "integrity_checks": integrity_checks,
            "target_checks": target_checks,
        },
    )


def mkp_transfer_core_strict_evaluator(input_data: RoundEvalInput) -> RoundEvalDecision:
    combos, integrity_checks, integrity_failures = _combo_context(input_data.variant_summaries)
    pair_checks = _check_pair_completeness(combos)
    pair_failures = [check for check in pair_checks if not check["passed"]]
    if integrity_failures or pair_failures:
        return RoundEvalDecision(
            passed=False,
            verdict=FAIL,
            message="Calibration combo set is incomplete.",
            details={
                "pdev_tolerance": PDEV_TOLERANCE,
                "core_algorithms": CORE_ALGORITHMS,
                "integrity_checks": integrity_checks,
                "pair_checks": pair_checks,
                "failures": integrity_failures + pair_failures,
            },
        )

    transfer_checks = _check_transfer_paired(combos)
    core_transfer_checks = [
        check for check in transfer_checks if check["algorithm"] in CORE_ALGORITHMS
    ]
    failures = [check for check in core_transfer_checks if not check["passed"]]
    if failures:
        return RoundEvalDecision(
            passed=False,
            verdict=FAIL,
            message="Core transfer checks failed.",
            details={
                "pdev_tolerance": PDEV_TOLERANCE,
                "core_algorithms": CORE_ALGORITHMS,
                "integrity_checks": integrity_checks,
                "pair_checks": pair_checks,
                "transfer_checks": transfer_checks,
                "core_transfer_checks": core_transfer_checks,
                "failures": failures,
            },
        )

    return RoundEvalDecision(
        passed=True,
        verdict=PASS,
        message="Core transfer checks passed.",
        details={
            "pdev_tolerance": PDEV_TOLERANCE,
            "core_algorithms": CORE_ALGORITHMS,
            "integrity_checks": integrity_checks,
            "pair_checks": pair_checks,
            "transfer_checks": transfer_checks,
            "core_transfer_checks": core_transfer_checks,
        },
    )


def mkp_transfer_bsca_margin_005_evaluator(input_data: RoundEvalInput) -> RoundEvalDecision:
    combos, integrity_checks, integrity_failures = _combo_context(input_data.variant_summaries)
    pair_checks = _check_pair_completeness(combos)
    pair_failures = [check for check in pair_checks if not check["passed"]]
    if integrity_failures or pair_failures:
        return RoundEvalDecision(
            passed=False,
            verdict=FAIL,
            message="Calibration combo set is incomplete.",
            details={
                "pdev_tolerance": PDEV_TOLERANCE,
                "bsca_margin_pdev": BSCA_MARGIN_PDEV,
                "bsca_transfer_max_avg_rank": BSCA_TRANSFER_MAX_AVG_RANK,
                "integrity_checks": integrity_checks,
                "pair_checks": pair_checks,
                "failures": integrity_failures + pair_failures,
            },
        )

    transfer_checks = _check_transfer_paired(combos)
    bsca_margin_check = _bsca_transfer_margin_check(transfer_checks)
    if not bsca_margin_check["passed"]:
        return RoundEvalDecision(
            passed=False,
            verdict=FAIL,
            message="BSCA transfer check exceeded allowed margin.",
            details={
                "pdev_tolerance": PDEV_TOLERANCE,
                "bsca_margin_pdev": BSCA_MARGIN_PDEV,
                "bsca_transfer_max_avg_rank": BSCA_TRANSFER_MAX_AVG_RANK,
                "integrity_checks": integrity_checks,
                "pair_checks": pair_checks,
                "transfer_checks": transfer_checks,
                "bsca_margin_check": bsca_margin_check,
                "failures": [bsca_margin_check],
            },
        )

    return RoundEvalDecision(
        passed=True,
        verdict=PASS,
        message="BSCA transfer check is strict best or within margin.",
        details={
            "pdev_tolerance": PDEV_TOLERANCE,
            "bsca_margin_pdev": BSCA_MARGIN_PDEV,
            "bsca_transfer_max_avg_rank": BSCA_TRANSFER_MAX_AVG_RANK,
            "integrity_checks": integrity_checks,
            "pair_checks": pair_checks,
            "transfer_checks": transfer_checks,
            "bsca_margin_check": bsca_margin_check,
        },
    )


def mkp_target_combo_core_strict_evaluator(input_data: RoundEvalInput) -> RoundEvalDecision:
    combos, integrity_checks, integrity_failures = _combo_context(input_data.variant_summaries)
    if integrity_failures:
        return RoundEvalDecision(
            passed=False,
            verdict=FAIL,
            message="Calibration combo set is incomplete.",
            details={
                "pdev_tolerance": PDEV_TOLERANCE,
                "core_algorithms": CORE_ALGORITHMS,
                "integrity_checks": integrity_checks,
                "failures": integrity_failures,
            },
        )

    target_checks = _check_target_combos(combos)
    core_target_checks = [
        check for check in target_checks if check["algorithm"] in CORE_ALGORITHMS
    ]
    failures = [check for check in core_target_checks if not check["passed"]]
    if failures:
        return RoundEvalDecision(
            passed=False,
            verdict=FAIL,
            message="Core target combo checks failed.",
            details={
                "pdev_tolerance": PDEV_TOLERANCE,
                "core_algorithms": CORE_ALGORITHMS,
                "integrity_checks": integrity_checks,
                "target_checks": target_checks,
                "core_target_checks": core_target_checks,
                "failures": failures,
            },
        )

    return RoundEvalDecision(
        passed=True,
        verdict=PASS,
        message="Core target combo checks passed.",
        details={
            "pdev_tolerance": PDEV_TOLERANCE,
            "core_algorithms": CORE_ALGORITHMS,
            "integrity_checks": integrity_checks,
            "target_checks": target_checks,
            "core_target_checks": core_target_checks,
        },
    )


def mkp_target_combo_bsma_strict_evaluator(input_data: RoundEvalInput) -> RoundEvalDecision:
    combos, integrity_checks, integrity_failures = _combo_context(input_data.variant_summaries)
    if integrity_failures:
        return RoundEvalDecision(
            passed=False,
            verdict=FAIL,
            message="Calibration combo set is incomplete.",
            details={
                "pdev_tolerance": PDEV_TOLERANCE,
                "algorithm": "bsma",
                "integrity_checks": integrity_checks,
                "failures": integrity_failures,
            },
        )

    target_check = _single_target_combo_check(combos, "bsma")
    if not target_check["passed"]:
        return RoundEvalDecision(
            passed=False,
            verdict=FAIL,
            message="BSMA target combo is not strict best.",
            details={
                "pdev_tolerance": PDEV_TOLERANCE,
                "algorithm": "bsma",
                "integrity_checks": integrity_checks,
                "target_check": target_check,
                "failures": [target_check],
            },
        )

    return RoundEvalDecision(
        passed=True,
        verdict=PASS,
        message="BSMA target combo is strict best.",
        details={
            "pdev_tolerance": PDEV_TOLERANCE,
            "algorithm": "bsma",
            "integrity_checks": integrity_checks,
            "target_check": target_check,
        },
    )


def mkp_target_combo_bsca_margin_005_evaluator(input_data: RoundEvalInput) -> RoundEvalDecision:
    combos, integrity_checks, integrity_failures = _combo_context(input_data.variant_summaries)
    if integrity_failures:
        return RoundEvalDecision(
            passed=False,
            verdict=FAIL,
            message="Calibration combo set is incomplete.",
            details={
                "pdev_tolerance": PDEV_TOLERANCE,
                "bsca_margin_pdev": BSCA_MARGIN_PDEV,
                "integrity_checks": integrity_checks,
                "failures": integrity_failures,
            },
        )

    target_check = _single_target_combo_check(combos, "bsca")
    bsca_margin_check = _target_margin_check(target_check, BSCA_MARGIN_PDEV)
    if not bsca_margin_check["passed"]:
        return RoundEvalDecision(
            passed=False,
            verdict=FAIL,
            message="BSCA target combo check exceeded allowed margin.",
            details={
                "pdev_tolerance": PDEV_TOLERANCE,
                "bsca_margin_pdev": BSCA_MARGIN_PDEV,
                "integrity_checks": integrity_checks,
                "target_check": target_check,
                "bsca_margin_check": bsca_margin_check,
                "failures": [bsca_margin_check],
            },
        )

    return RoundEvalDecision(
        passed=True,
        verdict=PASS,
        message="BSCA target combo check is strict best or within margin.",
        details={
            "pdev_tolerance": PDEV_TOLERANCE,
            "bsca_margin_pdev": BSCA_MARGIN_PDEV,
            "integrity_checks": integrity_checks,
            "target_check": target_check,
            "bsca_margin_check": bsca_margin_check,
        },
    )


def mkp_target_combo_brlsmasca_margin_004_evaluator(
    input_data: RoundEvalInput,
) -> RoundEvalDecision:
    combos, integrity_checks, integrity_failures = _combo_context(input_data.variant_summaries)
    if integrity_failures:
        return RoundEvalDecision(
            passed=False,
            verdict=FAIL,
            message="Calibration combo set is incomplete.",
            details={
                "pdev_tolerance": PDEV_TOLERANCE,
                "brlsmasca_margin_pdev": BRLSMASCA_MARGIN_PDEV,
                "integrity_checks": integrity_checks,
                "failures": integrity_failures,
            },
        )

    target_check = _single_target_combo_check(combos, "bscasma")
    brlsmasca_margin_check = _target_margin_check(target_check, BRLSMASCA_MARGIN_PDEV)
    if not brlsmasca_margin_check["passed"]:
        return RoundEvalDecision(
            passed=False,
            verdict=FAIL,
            message="BRLSMASCA target combo check exceeded allowed margin.",
            details={
                "pdev_tolerance": PDEV_TOLERANCE,
                "brlsmasca_margin_pdev": BRLSMASCA_MARGIN_PDEV,
                "integrity_checks": integrity_checks,
                "target_check": target_check,
                "brlsmasca_margin_check": brlsmasca_margin_check,
                "failures": [brlsmasca_margin_check],
            },
        )

    return RoundEvalDecision(
        passed=True,
        verdict=PASS,
        message="BRLSMASCA target combo check is strict best or within margin.",
        details={
            "pdev_tolerance": PDEV_TOLERANCE,
            "brlsmasca_margin_pdev": BRLSMASCA_MARGIN_PDEV,
            "integrity_checks": integrity_checks,
            "target_check": target_check,
            "brlsmasca_margin_check": brlsmasca_margin_check,
        },
    )


def mkp_calibration_evaluator(input_data: RoundEvalInput) -> RoundEvalDecision:
    transfer = mkp_transfer_paired_strict_evaluator(input_data)
    target = mkp_target_combo_best_evaluator(input_data)
    passed = transfer.passed and target.passed
    return RoundEvalDecision(
        passed=passed,
        verdict=PASS if passed else FAIL,
        message=(
            "Calibration transfer and target-combo checks passed."
            if passed
            else "Calibration transfer or target-combo checks failed."
        ),
        details={
            "pdev_tolerance": PDEV_TOLERANCE,
            "transfer": transfer.details,
            "target": target.details,
        },
    )


def _combo_context(
    variant_summaries: tuple[VariantSummary, ...],
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    summary_failures = _summary_failures(variant_summaries)
    combos = [_combo_from_variant(variant) for variant in variant_summaries]
    integrity_checks = {
        "summary_failures": summary_failures,
        "combo_count": _check_combo_count(combos),
        "algorithm_counts": _check_algorithm_counts(combos),
        "unknown_algorithms": _check_unknown_algorithms(combos),
    }
    failures: list[dict[str, Any]] = []
    if summary_failures:
        failures.append({"check": "summary_failures", "passed": False, "failures": summary_failures})
    if not integrity_checks["combo_count"]["passed"]:
        failures.append({"check": "combo_count", **integrity_checks["combo_count"]})
    failures.extend(
        {"check": "algorithm_counts", **check}
        for check in integrity_checks["algorithm_counts"]
        if not check["passed"]
    )
    if not integrity_checks["unknown_algorithms"]["passed"]:
        failures.append({"check": "unknown_algorithms", **integrity_checks["unknown_algorithms"]})
    return combos, integrity_checks, failures


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


def _combo_from_variant(variant: VariantSummary) -> dict[str, Any]:
    algorithm = ALGORITHM_BY_SOLVER_ID.get(variant.solver_id, "unknown")
    params = variant.params
    return {
        "variant": f"{variant.solver_id}/param_{variant.param_set_index}",
        "algorithm": algorithm,
        "solver_id": variant.solver_id,
        "param_set_index": variant.param_set_index,
        "ctf": params.get("ctf", "tanh_abs"),
        "z": params.get("z"),
        "a": params.get("a"),
        "pdev": float(variant.summary.overall.pdev),
    }


def _check_combo_count(combos: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "passed": len(combos) == EXPECTED_COMBO_COUNT,
        "actual": len(combos),
        "expected": EXPECTED_COMBO_COUNT,
    }


def _check_algorithm_counts(combos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "passed": _algorithm_count(combos, algorithm) == expected_count,
            "algorithm": algorithm,
            "actual": _algorithm_count(combos, algorithm),
            "expected": expected_count,
        }
        for algorithm, expected_count in EXPECTED_ALGORITHM_COUNTS.items()
    ]


def _check_unknown_algorithms(combos: list[dict[str, Any]]) -> dict[str, Any]:
    unknown = sorted({combo["variant"] for combo in combos if combo["algorithm"] == "unknown"})
    return {
        "passed": not unknown,
        "unknown_variants": unknown,
    }


def _check_pair_completeness(combos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for algorithm, expected_pairs in EXPECTED_PAIRS.items():
        algorithm_combos = [combo for combo in combos if combo["algorithm"] == algorithm]
        for expected_pair in expected_pairs:
            pair_combos = [
                combo for combo in algorithm_combos if _matches_target(combo, expected_pair)
            ]
            counts_by_ctf = {
                ctf: sum(1 for combo in pair_combos if combo["ctf"] == ctf)
                for ctf in EXPECTED_CTFS
            }
            checks.append(
                {
                    "passed": all(count == 1 for count in counts_by_ctf.values()),
                    "algorithm": algorithm,
                    "pair": expected_pair,
                    "counts_by_ctf": counts_by_ctf,
                    "variants": [combo["variant"] for combo in pair_combos],
                }
            )
    return checks


def _check_transfer_paired(combos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for algorithm, expected_pairs in EXPECTED_PAIRS.items():
        pair_metrics: list[dict[str, Any]] = []
        for expected_pair in expected_pairs:
            pair_combos = [
                combo
                for combo in combos
                if combo["algorithm"] == algorithm and _matches_target(combo, expected_pair)
            ]
            by_ctf = {combo["ctf"]: combo for combo in pair_combos}
            pdevs = {ctf: by_ctf[ctf]["pdev"] for ctf in EXPECTED_CTFS}
            ranks = _dense_ranks(pdevs)
            pair_metrics.append(
                {
                    "pair": expected_pair,
                    "pdevs": pdevs,
                    "ranks": ranks,
                }
            )

        transfer_metrics = {
            ctf: {
                "avg_pdev": _avg([pair["pdevs"][ctf] for pair in pair_metrics]),
                "avg_rank": _avg([pair["ranks"][ctf] for pair in pair_metrics]),
            }
            for ctf in EXPECTED_CTFS
        }
        best_avg_pdev = min(metric["avg_pdev"] for metric in transfer_metrics.values())
        best_avg_rank = min(metric["avg_rank"] for metric in transfer_metrics.values())
        expected_metrics = transfer_metrics[EXPECTED_TRANSFER_CTF]
        checks.append(
            {
                "passed": (
                    expected_metrics["avg_pdev"] <= best_avg_pdev
                    and expected_metrics["avg_rank"] <= best_avg_rank
                ),
                "algorithm": algorithm,
                "expected_ctf": EXPECTED_TRANSFER_CTF,
                "best_avg_pdev": best_avg_pdev,
                "best_avg_rank": best_avg_rank,
                "transfer_metrics": transfer_metrics,
                "pairs": pair_metrics,
            }
        )
    return checks


def _check_target_combos(combos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        _single_target_combo_check(combos, algorithm)
        for algorithm in TARGET_COMBOS
    ]


def _single_target_combo_check(
    combos: list[dict[str, Any]],
    algorithm: str,
) -> dict[str, Any]:
    target = TARGET_COMBOS[algorithm]
    target_label = _target_label(target)
    algorithm_combos = [combo for combo in combos if combo["algorithm"] == algorithm]
    expected_options = EXPECTED_PAIRS[algorithm]
    if not algorithm_combos:
        return {
            "passed": False,
            "algorithm": algorithm,
            "reason": "algorithm_combos_missing",
            "target": target,
            "target_label": target_label,
        }

    ctf_checks: list[dict[str, Any]] = []
    for ctf in EXPECTED_CTFS:
        ctf_combos = [combo for combo in algorithm_combos if combo["ctf"] == ctf]
        pdevs: dict[str, float] = {}
        variants: dict[str, str] = {}
        option_matches: dict[str, list[str]] = {}
        for option in expected_options:
            option_label = _target_label(option)
            matches = [combo for combo in ctf_combos if _matches_target(combo, option)]
            option_matches[option_label] = [combo["variant"] for combo in matches]
            if len(matches) == 1:
                pdevs[option_label] = matches[0]["pdev"]
                variants[option_label] = matches[0]["variant"]

        missing_or_ambiguous = {
            option_label: matches
            for option_label, matches in option_matches.items()
            if len(matches) != 1
        }
        if missing_or_ambiguous:
            return {
                "passed": False,
                "algorithm": algorithm,
                "reason": "target_option_missing_or_ambiguous",
                "target": target,
                "target_label": target_label,
                "ctf": ctf,
                "matches": missing_or_ambiguous,
            }

        ranks = _dense_ranks(pdevs)
        ctf_checks.append(
            {
                "ctf": ctf,
                "pdevs": pdevs,
                "ranks": ranks,
                "variants": variants,
            }
        )

    option_metrics = {
        _target_label(option): {
            "option": option,
            "avg_pdev": _avg([check["pdevs"][_target_label(option)] for check in ctf_checks]),
            "avg_rank": _avg([check["ranks"][_target_label(option)] for check in ctf_checks]),
        }
        for option in expected_options
    }
    best_avg_pdev = min(metric["avg_pdev"] for metric in option_metrics.values())
    best_avg_rank = min(metric["avg_rank"] for metric in option_metrics.values())
    target_metrics = option_metrics[target_label]
    best_options = [
        label
        for label, metric in option_metrics.items()
        if math.isclose(metric["avg_pdev"], best_avg_pdev, rel_tol=1e-12, abs_tol=1e-12)
    ]
    return {
        "passed": (
            target_metrics["avg_pdev"] <= best_avg_pdev
            and target_metrics["avg_rank"] <= best_avg_rank
        ),
        "algorithm": algorithm,
        "target": target,
        "target_label": target_label,
        "target_pdev": target_metrics["avg_pdev"],
        "target_avg_pdev": target_metrics["avg_pdev"],
        "target_avg_rank": target_metrics["avg_rank"],
        "best_pdev": best_avg_pdev,
        "best_avg_pdev": best_avg_pdev,
        "best_avg_rank": best_avg_rank,
        "best_options": best_options,
        "best_variants": best_options,
        "option_metrics": option_metrics,
        "ctf_checks": ctf_checks,
    }


def _bsca_transfer_margin_check(transfer_checks: list[dict[str, Any]]) -> dict[str, Any]:
    bsca_check = next(
        (check for check in transfer_checks if check["algorithm"] == "bsca"),
        None,
    )
    if bsca_check is None:
        return {
            "passed": False,
            "algorithm": "bsca",
            "reason": "bsca_transfer_check_missing",
        }

    expected_metrics = bsca_check["transfer_metrics"][EXPECTED_TRANSFER_CTF]
    gap_to_best = expected_metrics["avg_pdev"] - bsca_check["best_avg_pdev"]
    margin_passed = (
        gap_to_best <= BSCA_MARGIN_PDEV
        and expected_metrics["avg_rank"] <= BSCA_TRANSFER_MAX_AVG_RANK
    )
    passed = bool(bsca_check["passed"] or margin_passed)
    return {
        **bsca_check,
        "passed": passed,
        "strict_passed": bsca_check["passed"],
        "margin_passed": margin_passed,
        "gap_to_best": gap_to_best,
        "margin": BSCA_MARGIN_PDEV,
        "max_allowed_avg_rank": BSCA_TRANSFER_MAX_AVG_RANK,
        "expected_ctf": EXPECTED_TRANSFER_CTF,
        "expected_ctf_avg_pdev": expected_metrics["avg_pdev"],
        "expected_ctf_avg_rank": expected_metrics["avg_rank"],
    }


def _bsca_target_margin_check(target_checks: list[dict[str, Any]]) -> dict[str, Any]:
    bsca_check = next(
        (check for check in target_checks if check["algorithm"] == "bsca"),
        None,
    )
    if bsca_check is None:
        return {
            "passed": False,
            "algorithm": "bsca",
            "reason": "bsca_target_check_missing",
        }
    return _target_margin_check(bsca_check, BSCA_MARGIN_PDEV)


def _target_margin_check(target_check: dict[str, Any], margin: float) -> dict[str, Any]:
    if "target_pdev" not in target_check or "best_pdev" not in target_check:
        return {
            **target_check,
            "passed": False,
            "strict_passed": False,
            "margin_passed": False,
            "margin": margin,
        }

    gap_to_best = target_check["target_pdev"] - target_check["best_pdev"]
    margin_passed = gap_to_best <= margin
    passed = bool(target_check["passed"] or margin_passed)
    return {
        **target_check,
        "passed": passed,
        "strict_passed": target_check["passed"],
        "margin_passed": margin_passed,
        "gap_to_best": gap_to_best,
        "margin": margin,
    }


def _dense_ranks(pdevs: dict[str, float]) -> dict[str, int]:
    ordered_values = sorted(set(pdevs.values()))
    return {
        ctf: 1 + ordered_values.index(pdev)
        for ctf, pdev in pdevs.items()
    }


def _avg(values: list[int | float]) -> float:
    return sum(float(value) for value in values) / len(values)


def _algorithm_count(combos: list[dict[str, Any]], algorithm: str) -> int:
    return sum(1 for combo in combos if combo["algorithm"] == algorithm)


def _matches_target(combo: dict[str, Any], target: dict[str, Any]) -> bool:
    return all(_same_value(combo.get(key), value) for key, value in target.items())


def _target_label(target: dict[str, Any]) -> str:
    return ",".join(f"{key}={target[key]}" for key in PAIR_KEYS[_target_algorithm(target)])


def _target_algorithm(target: dict[str, Any]) -> str:
    for algorithm, keys in PAIR_KEYS.items():
        if set(target) == set(keys):
            return algorithm
    # Preserve deterministic output for malformed targets used only in failure details.
    return next(iter(PAIR_KEYS))


def _same_value(left: Any, right: Any) -> bool:
    if isinstance(left, (float, int)) and isinstance(right, (float, int)):
        return math.isclose(float(left), float(right), rel_tol=1e-12, abs_tol=1e-12)
    return left == right
