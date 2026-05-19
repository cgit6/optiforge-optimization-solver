from __future__ import annotations

from itertools import combinations
import math
from typing import Any

import numpy as np
from scipy.stats import wilcoxon

from ...experiment.evaluation import (
    DatasetEvalDecision,
    DatasetRunResult,
    ExperimentEvalInput,
    FAIL,
    PaperSetEvalInput,
    SOFT_PASS,
    STRICT_PASS,
    VariantSummary,
)
from ...tools.stat import ResultEntry, SummaryMeta, summarize, result_entries


_ALLOWED_CONFIG_KEYS = frozenset({"pdev_tolerance"})
_DEFAULT_PDEV_TOLERANCE = 0.005
_EPSILON = 1e-12
_PAIR_SIZE = 2
_TRANSFER_CTFS = ("sigmoid_s0", "abs_pow_17", "tanh_abs")
_TRANSFER_LABELS = {
    "sigmoid_s0": "S",
    "abs_pow_17": "U",
    "tanh_abs": "V",
}
_TRANSFER_SOLVER_SPECS = {
    "ISMA": {"solver_id": "bsma_numba_transfer_literature", "target_ctf": "tanh_abs"},
    "ISCA": {"solver_id": "bsca_numba_transfer_literature", "target_ctf": "tanh_abs"},
    "HSMSCA_RL": {"solver_id": "brlsmasca_numba_transfer_literature", "target_ctf": "tanh_abs"},
    "RANDOM50": {"solver_id": "brlsmasca_numba_random50_transfer_literature", "target_ctf": "tanh_abs"},
}
_CALIBRATION_SOLVER_SPECS = {
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
    "HSMSCA_RL": {
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
_FINAL_SOLVER_SPECS = {
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
    "HSMSCA_RL": {
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
    "RANDOM50": {
        "solver_id": "brlsmasca_numba_random50_literature",
        "param_keys": (),
        "expected": ((),),
        "target": (),
    },
}
_EXTERNAL_BASELINES = {
    "set1": {"HLMS": 0.569},
    "set2": {"HLMS": 0.154, "BIWOA": 0.472, "BMMVO": 0.861, "BSCA": 0.314, "IBSMA_U1": 0.105},
    "set3_1": {"HLMS": 0.925, "BIWOA": 1.234},
    "set3_2": {"HLMS": 1.349},
    "set4": {"HLMS": 0.922, "BIWOA": 0.857, "BMMVO": 2.438, "BSCA": 1.997, "IBSMA_U1": 0.624},
}


def literature_mkp_support_full_paper_set_evaluator(input_data: PaperSetEvalInput) -> DatasetEvalDecision:
    cfg = _parse_config(input_data.evaluation_config)
    validity_failures = _validity_failures(input_data.variant_summaries)
    if validity_failures:
        return DatasetEvalDecision(
            passed=False,
            verdict=FAIL,
            message="Some variant summaries are invalid.",
            details={"failures": validity_failures},
        )

    transfer = _transfer_decision(input_data.variant_summaries, cfg["pdev_tolerance"])
    calibration = _calibration_decision(input_data.variant_summaries, cfg["pdev_tolerance"])
    verdict = _combine_verdicts((transfer["verdict"], calibration["verdict"]))
    passed = verdict != FAIL
    return DatasetEvalDecision(
        passed=passed,
        verdict=verdict,
        message=_paper_set_message(verdict, transfer["verdict"], calibration["verdict"]),
        details={
            "paper_set": input_data.paper_set,
            "transfer": transfer,
            "calibration": calibration,
        },
    )


def literature_mkp_support_full_experiment_evaluator(input_data: ExperimentEvalInput) -> DatasetEvalDecision:
    cfg = _parse_config(input_data.evaluation_config)
    validity_failures = _validity_failures(input_data.variant_summaries)
    if validity_failures:
        return DatasetEvalDecision(
            passed=False,
            verdict=FAIL,
            message="Some variant summaries are invalid.",
            details={"failures": validity_failures},
        )

    final = _final_decision(input_data, cfg["pdev_tolerance"])
    wilcoxon_result = _wilcoxon_decision(input_data.variant_summaries)
    verdict = _combine_verdicts((final["verdict"], wilcoxon_result["verdict"]))
    passed = verdict != FAIL
    return DatasetEvalDecision(
        passed=passed,
        verdict=verdict,
        message=_global_message(verdict, final["verdict"], wilcoxon_result["verdict"]),
        details={
            "final": final,
            "wilcoxon": wilcoxon_result,
            "paper_set_evaluations": [
                {
                    "paper_set": record.paper_set,
                    "verdict": record.decision.verdict,
                    "message": record.decision.message,
                }
                for record in input_data.paper_set_evaluations
            ],
        },
    )


def _parse_config(raw_config: dict[str, Any]) -> dict[str, float]:
    keys = {str(key) for key in raw_config}
    unknown = sorted(keys - _ALLOWED_CONFIG_KEYS)
    if unknown:
        raise ValueError(f"evaluation.config has unknown key(s): {unknown}")
    tolerance = raw_config.get("pdev_tolerance", _DEFAULT_PDEV_TOLERANCE)
    if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)):
        raise ValueError("evaluation.config.pdev_tolerance must be numeric.")
    tolerance = float(tolerance)
    if tolerance < 0.0:
        raise ValueError("evaluation.config.pdev_tolerance must be >= 0.")
    return {"pdev_tolerance": tolerance}


def _paper_set_message(verdict: str, transfer_verdict: str, calibration_verdict: str) -> str:
    if verdict == STRICT_PASS:
        return "Paper set supports both transfer and calibration conclusions."
    if verdict == SOFT_PASS:
        return (
            "Paper set is near the literature conclusions "
            f"(transfer={transfer_verdict}, calibration={calibration_verdict})."
        )
    return f"Paper set does not support the literature conclusions (transfer={transfer_verdict}, calibration={calibration_verdict})."


def _global_message(verdict: str, final_verdict: str, wilcoxon_verdict: str) -> str:
    if verdict == STRICT_PASS:
        return "All-level final comparison and Wilcoxon checks support the literature conclusions."
    if verdict == SOFT_PASS:
        return f"All-level result is near the literature conclusions (final={final_verdict}, wilcoxon={wilcoxon_verdict})."
    return f"All-level result does not support the literature conclusions (final={final_verdict}, wilcoxon={wilcoxon_verdict})."


def _transfer_decision(variant_summaries: tuple[VariantSummary, ...], tolerance: float) -> dict[str, Any]:
    parsed = _parse_transfer_variants(variant_summaries)
    family_results: dict[str, dict[str, Any]] = {}
    family_verdicts: list[str] = []
    for family, family_variants in parsed.items():
        scores = {
            _TRANSFER_LABELS[ctf]: _overall_pdev(variant)
            for ctf, variant in family_variants.items()
        }
        verdict = _target_verdict(scores, "V", tolerance)
        family_results[family] = {
            "scores": scores,
            "target": "V",
            "best_transfer": min(scores, key=scores.get),
            "verdict": verdict,
        }
        family_verdicts.append(verdict)
    return {
        "verdict": _combine_verdicts(tuple(family_verdicts)),
        "families": family_results,
        "pdev_tolerance": tolerance,
    }


def _calibration_decision(variant_summaries: tuple[VariantSummary, ...], tolerance: float) -> dict[str, Any]:
    parsed = _parse_expected_variants(variant_summaries, _CALIBRATION_SOLVER_SPECS)
    problems = _problem_keys(parsed, family="HSMSCA_RL")
    if len(problems) < _PAIR_SIZE:
        return {
            "verdict": FAIL,
            "problem_count": len(problems),
        }

    problem_pdevs = {
        family: {
            signature: _problem_pdev_map(variant)
            for signature, variant in family_variants.items()
        }
        for family, family_variants in parsed.items()
    }
    for family, variant_maps in problem_pdevs.items():
        for signature, mapping in variant_maps.items():
            missing = [problem for problem in problems if problem not in mapping]
            if missing:
                raise ValueError(f"{family} variant {signature!r} is missing problem summaries: {missing}")

    best_soft: dict[str, Any] | None = None
    for pair in combinations(problems, _PAIR_SIZE):
        scores = {
            family: {
                _signature_label(family, signature): _mean_problem_pdev(mapping, pair)
                for signature, mapping in problem_pdevs[family].items()
            }
            for family in problem_pdevs
        }
        family_verdicts = {
            family: _target_verdict(scores[family], _target_label(family, _CALIBRATION_SOLVER_SPECS), tolerance)
            for family in _CALIBRATION_SOLVER_SPECS
        }
        verdict = _combine_verdicts(tuple(family_verdicts.values()))
        candidate = {
            "verdict": verdict,
            "pair": [{"dataset": dataset, "problem_id": problem_id} for dataset, problem_id in pair],
            "scores": scores,
            "family_verdicts": family_verdicts,
            "pdev_tolerance": tolerance,
        }
        if verdict == STRICT_PASS:
            return candidate
        if verdict == SOFT_PASS and best_soft is None:
            best_soft = candidate

    if best_soft is not None:
        return best_soft
    return {
        "verdict": FAIL,
        "problem_count": len(problems),
        "pdev_tolerance": tolerance,
    }


def _final_decision(input_data: ExperimentEvalInput, tolerance: float) -> dict[str, Any]:
    parsed = _parse_expected_variants(input_data.variant_summaries, _FINAL_SOLVER_SPECS)
    target_variants = {
        family: family_variants[_FINAL_SOLVER_SPECS[family]["target"]]
        for family, family_variants in parsed.items()
    }
    all_level_pdevs = {
        family: _overall_pdev(variant)
        for family, variant in target_variants.items()
    }
    hsmsca_pdev = all_level_pdevs["HSMSCA_RL"]
    internal_deltas = {
        "ISMA": hsmsca_pdev - all_level_pdevs["ISMA"],
        "ISCA": hsmsca_pdev - all_level_pdevs["ISCA"],
        "RANDOM50": hsmsca_pdev - all_level_pdevs["RANDOM50"],
    }
    internal_strict = {name: delta <= _EPSILON for name, delta in internal_deltas.items()}
    internal_soft = {name: delta <= tolerance for name, delta in internal_deltas.items()}
    internal_verdict = _verdict_from_checks(internal_strict, internal_soft)

    paper_set_external = _paper_set_external_checks(input_data.dataset_results, tolerance)
    external_verdict = _combine_verdicts(tuple(item["verdict"] for item in paper_set_external.values()))
    return {
        "verdict": _combine_verdicts((internal_verdict, external_verdict)),
        "all_level_pdevs": all_level_pdevs,
        "internal_comparisons": {
            "strict": internal_strict,
            "soft": internal_soft,
        },
        "paper_set_external": paper_set_external,
        "pdev_tolerance": tolerance,
    }


def _wilcoxon_decision(variant_summaries: tuple[VariantSummary, ...]) -> dict[str, Any]:
    parsed = _parse_expected_variants(variant_summaries, _FINAL_SOLVER_SPECS)
    target_variants = {
        family: family_variants[_FINAL_SOLVER_SPECS[family]["target"]]
        for family, family_variants in parsed.items()
    }
    hsmsca_map = _problem_pdev_map(target_variants["HSMSCA_RL"])
    family_results: dict[str, dict[str, Any]] = {}
    verdicts: list[str] = []
    for family in ("ISMA", "ISCA", "RANDOM50"):
        competitor_map = _problem_pdev_map(target_variants[family])
        problems = sorted(hsmsca_map)
        if problems != sorted(competitor_map):
            raise ValueError(f"Problem coverage mismatch in Wilcoxon comparison: HSMSCA_RL vs {family}")
        hsmsca_values = np.array([hsmsca_map[problem] for problem in problems], dtype=np.float64)
        competitor_values = np.array([competitor_map[problem] for problem in problems], dtype=np.float64)
        mean_delta = float(np.mean(hsmsca_values - competitor_values))
        direction_better = mean_delta < -_EPSILON
        try:
            statistic, p_value = wilcoxon(
                hsmsca_values,
                competitor_values,
                alternative="less",
                zero_method="zsplit",
            )
            statistic = float(statistic)
            p_value = float(p_value)
        except ValueError as exc:
            statistic = math.nan
            p_value = math.nan
            direction_better = False
            error = str(exc)
        else:
            error = None

        strict = direction_better and not math.isnan(p_value) and p_value < 0.05
        soft = direction_better and not strict
        verdict = STRICT_PASS if strict else SOFT_PASS if soft else FAIL
        verdicts.append(verdict)
        family_results[family] = {
            "verdict": verdict,
            "mean_delta": mean_delta,
            "direction_better": direction_better,
            "statistic": statistic,
            "p_value": p_value,
            "problem_count": len(problems),
            "error": error,
        }
    return {
        "verdict": _combine_verdicts(tuple(verdicts)),
        "comparisons": family_results,
    }


def _paper_set_external_checks(
    dataset_results: tuple[DatasetRunResult, ...],
    tolerance: float,
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[DatasetRunResult]] = {}
    ordered: list[str] = []
    for result in dataset_results:
        paper_set = result.dataset_setting.paper_set
        if paper_set not in grouped:
            ordered.append(paper_set)
            grouped[paper_set] = []
        grouped[paper_set].append(result)

    checks: dict[str, dict[str, Any]] = {}
    for paper_set in ordered:
        external_baselines = _EXTERNAL_BASELINES.get(paper_set)
        if external_baselines is None:
            raise ValueError(f"Unsupported literature paper_set: {paper_set}")
        variants = _aggregate_variant_summaries(grouped[paper_set], experiment_meta={"paper_set": paper_set})
        parsed = _parse_expected_variants(variants, _FINAL_SOLVER_SPECS)
        hsmsca_variant = parsed["HSMSCA_RL"][_FINAL_SOLVER_SPECS["HSMSCA_RL"]["target"]]
        hsmsca_pdev = _overall_pdev(hsmsca_variant)
        strict = {name: hsmsca_pdev <= value + _EPSILON for name, value in external_baselines.items()}
        soft = {name: hsmsca_pdev <= value + tolerance for name, value in external_baselines.items()}
        checks[paper_set] = {
            "verdict": _verdict_from_checks(strict, soft),
            "hsmsca_pdev": hsmsca_pdev,
            "external_baselines": dict(external_baselines),
            "strict": strict,
            "soft": soft,
        }
    return checks


def _parse_transfer_variants(
    variant_summaries: tuple[VariantSummary, ...],
) -> dict[str, dict[str, VariantSummary]]:
    parsed = {family: {} for family in _TRANSFER_SOLVER_SPECS}
    expected_solver_ids = {spec["solver_id"] for spec in _TRANSFER_SOLVER_SPECS.values()}
    for variant in variant_summaries:
        if variant.solver_id not in expected_solver_ids:
            continue
        family = _family_for_solver(variant.solver_id, _TRANSFER_SOLVER_SPECS)
        ctf = _string_param(variant.params, "ctf")
        if ctf not in _TRANSFER_CTFS:
            raise ValueError(f"Unexpected transfer CTF for {variant.solver_id}: {ctf!r}")
        if ctf in parsed[family]:
            raise ValueError(f"Duplicate transfer variant detected for {family}: {ctf!r}")
        parsed[family][ctf] = variant
    for family, family_variants in parsed.items():
        missing = [ctf for ctf in _TRANSFER_CTFS if ctf not in family_variants]
        if missing:
            raise ValueError(f"Missing transfer variants for {family}: {missing}")
    return parsed


def _parse_expected_variants(
    variant_summaries: tuple[VariantSummary, ...],
    solver_specs: dict[str, dict[str, Any]],
) -> dict[str, dict[tuple[float, ...], VariantSummary]]:
    parsed = {family: {} for family in solver_specs}
    expected_solver_ids = {spec["solver_id"] for spec in solver_specs.values()}
    for variant in variant_summaries:
        if variant.solver_id not in expected_solver_ids:
            continue
        family, signature = _variant_signature(variant, solver_specs)
        if signature in parsed[family]:
            raise ValueError(f"Duplicate literature variant detected for {family}: {signature!r}")
        parsed[family][signature] = variant
    for family, spec in solver_specs.items():
        missing = [signature for signature in spec["expected"] if signature not in parsed[family]]
        if missing:
            raise ValueError(f"Missing literature variants for {family}: {missing}")
    return parsed


def _variant_signature(
    variant: VariantSummary,
    solver_specs: dict[str, dict[str, Any]],
) -> tuple[str, tuple[float, ...]]:
    for family, spec in solver_specs.items():
        if variant.solver_id != spec["solver_id"]:
            continue
        signature = tuple(_float_param(variant.params, key) for key in spec["param_keys"])
        if signature not in spec["expected"]:
            raise ValueError(f"Unexpected parameter combination for {variant.solver_id}: {signature!r}")
        return family, signature
    raise ValueError(f"Unsupported literature solver variant: {variant.solver_id}")


def _combine_verdicts(verdicts: tuple[str, ...] | list[str]) -> str:
    items = tuple(verdicts)
    if any(verdict == FAIL for verdict in items):
        return FAIL
    if items and all(verdict == STRICT_PASS for verdict in items):
        return STRICT_PASS
    return SOFT_PASS


def _verdict_from_checks(strict: dict[str, bool], soft: dict[str, bool]) -> str:
    if strict and all(strict.values()):
        return STRICT_PASS
    if soft and all(soft.values()):
        return SOFT_PASS
    return FAIL


def _target_verdict(scores: dict[str, float], target_label: str, tolerance: float) -> str:
    best_score = min(scores.values())
    target_score = scores[target_label]
    if target_score <= best_score + _EPSILON:
        return STRICT_PASS
    if target_score - best_score <= tolerance:
        return SOFT_PASS
    return FAIL


def _target_label(family: str, solver_specs: dict[str, dict[str, Any]]) -> str:
    return _signature_label(family, solver_specs[family]["target"])


def _family_for_solver(solver_id: str, solver_specs: dict[str, dict[str, Any]]) -> str:
    for family, spec in solver_specs.items():
        if solver_id == spec["solver_id"]:
            return family
    raise ValueError(f"Unsupported literature solver variant: {solver_id}")


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


def _problem_keys(
    parsed_variants: dict[str, dict[tuple[float, ...], VariantSummary]],
    *,
    family: str,
) -> list[tuple[str, str]]:
    target_variant = parsed_variants[family][_FINAL_SOLVER_SPECS[family]["target"] if family in _FINAL_SOLVER_SPECS else _CALIBRATION_SOLVER_SPECS[family]["target"]]
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


def _signature_label(family: str, signature: tuple[float, ...]) -> str:
    if family == "ISMA":
        return f"z={signature[0]:.2f}"
    if family == "ISCA":
        return f"a={signature[0]:.1f}"
    if family == "RANDOM50":
        return "random50"
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


def _string_param(params: dict[str, Any], key: str) -> str:
    value = params.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"params.{key} must be a non-empty string in literature support evaluator.")
    return value.strip()


def _aggregate_variant_summaries(
    dataset_results: list[DatasetRunResult],
    *,
    experiment_meta: dict[str, Any],
) -> tuple[VariantSummary, ...]:
    grouped_entries: dict[tuple[str, int], list[ResultEntry]] = {}
    variant_params: dict[tuple[str, int], dict[str, Any]] = {}
    for dataset_result in dataset_results:
        for entry in result_entries(dataset_result.simulator_result):
            grouped_entries.setdefault((entry.solver_id, entry.param_set_index), []).append(entry)
        for key, params in dataset_result.simulator_result.variant_params.items():
            variant_params.setdefault(key, dict(params))

    variants: list[VariantSummary] = []
    for solver_id, param_set_index in sorted(grouped_entries):
        key = (solver_id, param_set_index)
        variants.append(
            VariantSummary(
                solver_id=solver_id,
                param_set_index=param_set_index,
                params=variant_params[key],
                summary=summarize(
                    grouped_entries[key],
                    meta=SummaryMeta(
                        solver_id=solver_id,
                        param_set_index=param_set_index,
                        params=variant_params[key],
                        experiment=experiment_meta,
                    ),
                ),
            )
        )
    return tuple(variants)
