from __future__ import annotations

from itertools import combinations
import math
from typing import Any

from ...experiment.evaluation import (
    DatasetEvalDecision,
    FAIL,
    PASS,
    PaperSetEvalInput,
    VariantSummary,
)


_ALLOWED_CONFIG_KEYS = frozenset()
_EPSILON = 1e-12
_PAIR_SIZE = 2
_EXPECTED_SOLVER_SPECS = {
    "ISMA": {
        "solver_id": "bsma_numba_literature",
        "param_keys": ("z",),
        "expected": ((0.01,), (0.08,), (0.15,)),
        "target": (0.08,),
    },
    "ISCA": {
        "solver_id": "bsca_numba_literature",
        "param_keys": ("a",),
        "expected": ((1.5,), (2.0,), (2.5,)),
        "target": (1.5,),
    },
    "HSMSCA": {
        "solver_id": "brlsmasca_numba_literature",
        "param_keys": ("z", "a"),
        "expected": (
            (0.01, 1.5),
            (0.01, 2.0),
            (0.01, 2.5),
            (0.08, 1.5),
            (0.08, 2.0),
            (0.08, 2.5),
            (0.15, 1.5),
            (0.15, 2.0),
            (0.15, 2.5),
        ),
        "target": (0.08, 2.5),
    },
}
_EXTERNAL_BASELINES = {
    "set1": {"HLMS": 0.569},
    "set2": {"HLMS": 0.154, "BIWOA": 0.472, "BMMVO": 0.861, "BSCA": 0.314, "IBSMA_U1": 0.105},
    "set3_1": {"HLMS": 0.925, "BIWOA": 1.234},
    "set3_2": {"HLMS": 1.349},
    "set4": {"HLMS": 0.922, "BIWOA": 0.857, "BMMVO": 2.438, "BSCA": 1.997, "IBSMA_U1": 0.624},
}


def literature_mkp_support_evaluator(input_data: PaperSetEvalInput) -> DatasetEvalDecision:
    _parse_config(input_data.evaluation_config)
    validity_failures = _validity_failures(input_data.variant_summaries)
    if validity_failures:
        return DatasetEvalDecision(
            passed=False,
            verdict=FAIL,
            message="Some variant summaries are invalid.",
            details={"failures": validity_failures},
        )

    parsed_variants = _parse_expected_variants(input_data.variant_summaries)
    calibration = _find_calibration_pair(parsed_variants)
    if calibration is None:
        return DatasetEvalDecision(
            passed=False,
            verdict=FAIL,
            message="No two-problem calibration subset supports the literature parameter ranking.",
            details={
                "paper_set": input_data.paper_set,
                "problem_count": len(_problem_keys(parsed_variants)),
            },
        )

    final = _final_comparison(input_data.paper_set, parsed_variants)
    if not final["passed"]:
        return DatasetEvalDecision(
            passed=False,
            verdict=FAIL,
            message="HSMSCA does not dominate the literature baselines on the full paper set.",
            details={
                "paper_set": input_data.paper_set,
                "calibration_pair": calibration["pair"],
                "calibration_scores": calibration["scores"],
                "set_pdevs": final["set_pdevs"],
                "external_baselines": final["external_baselines"],
                "comparisons": final["comparisons"],
            },
        )

    return DatasetEvalDecision(
        passed=True,
        verdict=PASS,
        message="Paper set supports the literature calibration and final-ranking conclusions.",
        details={
            "paper_set": input_data.paper_set,
            "calibration_pair": calibration["pair"],
            "calibration_scores": calibration["scores"],
            "set_pdevs": final["set_pdevs"],
            "external_baselines": final["external_baselines"],
            "comparisons": final["comparisons"],
        },
    )


def _parse_config(raw_config: dict[str, Any]) -> None:
    keys = {str(key) for key in raw_config}
    unknown = sorted(keys - _ALLOWED_CONFIG_KEYS)
    if unknown:
        raise ValueError(f"evaluation.config has unknown key(s): {unknown}")


def _validity_failures(variant_summaries: tuple[VariantSummary, ...]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for variant in variant_summaries:
        overall = variant.summary.overall
        excluded = overall.excluded_counts
        excluded_total = excluded.infeasible + excluded.objective_mismatch + excluded.runtime_error
        if (
            overall.total_runs <= 0
            or overall.valid_run_count != overall.total_runs
            or not math.isclose(overall.feasible_rate, 1.0)
            or overall.avg_objective is None
            or overall.best_known is None
            or excluded_total != 0
        ):
            failures.append(
                {
                    "solver_id": variant.solver_id,
                    "param_set_index": variant.param_set_index,
                    "total_runs": overall.total_runs,
                    "valid_run_count": overall.valid_run_count,
                    "feasible_rate": overall.feasible_rate,
                    "avg_objective": overall.avg_objective,
                    "best_known": overall.best_known,
                    "excluded_counts": {
                        "infeasible": excluded.infeasible,
                        "objective_mismatch": excluded.objective_mismatch,
                        "runtime_error": excluded.runtime_error,
                    },
                }
            )
    return failures


def _parse_expected_variants(
    variant_summaries: tuple[VariantSummary, ...],
) -> dict[str, dict[tuple[float, ...], VariantSummary]]:
    parsed: dict[str, dict[tuple[float, ...], VariantSummary]] = {
        family: {} for family in _EXPECTED_SOLVER_SPECS
    }
    expected_solver_ids = {spec["solver_id"] for spec in _EXPECTED_SOLVER_SPECS.values()}
    for variant in variant_summaries:
        if variant.solver_id not in expected_solver_ids:
            raise ValueError(f"Unexpected solver variant in literature support evaluator: {variant.solver_id}")
        family, signature = _variant_signature(variant)
        if signature in parsed[family]:
            raise ValueError(f"Duplicate literature variant detected for {family}: {signature!r}")
        parsed[family][signature] = variant

    for family, spec in _EXPECTED_SOLVER_SPECS.items():
        missing = [signature for signature in spec["expected"] if signature not in parsed[family]]
        if missing:
            raise ValueError(f"Missing literature variants for {family}: {missing}")
    return parsed


def _variant_signature(variant: VariantSummary) -> tuple[str, tuple[float, ...]]:
    for family, spec in _EXPECTED_SOLVER_SPECS.items():
        if variant.solver_id != spec["solver_id"]:
            continue
        signature = tuple(_float_param(variant.params, key) for key in spec["param_keys"])
        if signature not in spec["expected"]:
            raise ValueError(f"Unexpected parameter combination for {variant.solver_id}: {signature!r}")
        return family, signature
    raise ValueError(f"Unsupported literature solver variant: {variant.solver_id}")


def _find_calibration_pair(
    parsed_variants: dict[str, dict[tuple[float, ...], VariantSummary]],
) -> dict[str, Any] | None:
    problems = _problem_keys(parsed_variants)
    if len(problems) < _PAIR_SIZE:
        return None

    problem_pdevs = {
        family: {
            signature: _problem_pdev_map(variant)
            for signature, variant in family_variants.items()
        }
        for family, family_variants in parsed_variants.items()
    }
    for family, variant_maps in problem_pdevs.items():
        for signature, mapping in variant_maps.items():
            missing = [problem for problem in problems if problem not in mapping]
            if missing:
                raise ValueError(f"{family} variant {signature!r} is missing problem summaries: {missing}")

    for pair in combinations(problems, _PAIR_SIZE):
        scores = {
            family: {
                _signature_label(family, signature): _mean_problem_pdev(mapping, pair)
                for signature, mapping in problem_pdevs[family].items()
            }
            for family in problem_pdevs
        }
        if all(
            _target_is_best(family, scores[family])
            for family in _EXPECTED_SOLVER_SPECS
        ):
            return {
                "pair": [
                    {"dataset": dataset, "problem_id": problem_id}
                    for dataset, problem_id in pair
                ],
                "scores": scores,
            }
    return None


def _final_comparison(
    paper_set: str,
    parsed_variants: dict[str, dict[tuple[float, ...], VariantSummary]],
) -> dict[str, Any]:
    external_baselines = _EXTERNAL_BASELINES.get(paper_set)
    if external_baselines is None:
        raise ValueError(f"Unsupported literature paper_set: {paper_set}")

    target_variants = {
        family: family_variants[_EXPECTED_SOLVER_SPECS[family]["target"]]
        for family, family_variants in parsed_variants.items()
    }
    set_pdevs = {
        family: _overall_pdev(target_variants[family])
        for family in ("ISMA", "ISCA", "HSMSCA")
    }
    hsmsca_pdev = set_pdevs["HSMSCA"]
    comparisons = {
        "hsmsca_vs_isma": hsmsca_pdev <= set_pdevs["ISMA"] + _EPSILON,
        "hsmsca_vs_isca": hsmsca_pdev <= set_pdevs["ISCA"] + _EPSILON,
        "hsmsca_vs_external": {
            name: hsmsca_pdev <= value + _EPSILON
            for name, value in external_baselines.items()
        },
    }
    passed = comparisons["hsmsca_vs_isma"] and comparisons["hsmsca_vs_isca"] and all(
        comparisons["hsmsca_vs_external"].values()
    )
    return {
        "passed": passed,
        "set_pdevs": set_pdevs,
        "external_baselines": dict(external_baselines),
        "comparisons": comparisons,
    }


def _problem_keys(
    parsed_variants: dict[str, dict[tuple[float, ...], VariantSummary]],
) -> list[tuple[str, str]]:
    target_variant = parsed_variants["HSMSCA"][_EXPECTED_SOLVER_SPECS["HSMSCA"]["target"]]
    return sorted((entry.dataset, entry.problem_id) for entry in target_variant.summary.by_problem_solver)


def _problem_pdev_map(variant: VariantSummary) -> dict[tuple[str, str], float]:
    mapping: dict[tuple[str, str], float] = {}
    for entry in variant.summary.by_problem_solver:
        if entry.pdev is None:
            raise ValueError(
                f"Problem-level pdev is missing for {variant.solver_id}/param_{variant.param_set_index}"
            )
        mapping[(entry.dataset, entry.problem_id)] = float(entry.pdev)
    return mapping


def _mean_problem_pdev(
    problem_pdevs: dict[tuple[str, str], float],
    pair: tuple[tuple[str, str], tuple[str, str]],
) -> float:
    return sum(problem_pdevs[problem] for problem in pair) / len(pair)


def _target_is_best(family: str, scores: dict[str, float]) -> bool:
    best_score = min(scores.values())
    target_label = _signature_label(family, _EXPECTED_SOLVER_SPECS[family]["target"])
    return scores[target_label] <= best_score + _EPSILON


def _signature_label(family: str, signature: tuple[float, ...]) -> str:
    if family == "ISMA":
        return f"z={signature[0]:.2f}"
    if family == "ISCA":
        return f"a={signature[0]:.1f}"
    return f"z={signature[0]:.2f},a={signature[1]:.1f}"


def _overall_pdev(variant: VariantSummary) -> float:
    pdev = variant.summary.overall.pdev
    if pdev is None:
        raise ValueError(f"Overall pdev is missing for {variant.solver_id}/param_{variant.param_set_index}")
    return float(pdev)


def _float_param(params: dict[str, Any], key: str) -> float:
    value = params.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"params.{key} must be numeric in literature support evaluator.")
    return float(value)
