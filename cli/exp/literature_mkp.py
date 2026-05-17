from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from ...experiment.evaluation import (
    DatasetEvalDecision,
    DatasetEvalInput,
    FAIL,
    PASS,
    VariantSummary,
)


_ALLOWED_CONFIG_KEYS = frozenset({"pdev_tolerance", "required_variants", "target_variant"})


@dataclass(frozen=True)
class _VariantRef:
    solver_id: str
    param_set_index: int


@dataclass(frozen=True)
class _LiteratureMkpConfig:
    pdev_tolerance: float = 0.0
    required_variants: tuple[_VariantRef, ...] = ()
    target_variant: _VariantRef | None = None


# 註冊的評估函數
def literature_mkp_evaluator(input_data: DatasetEvalInput) -> DatasetEvalDecision:
    cfg = _parse_config(input_data.evaluation_config)
    variants = {
        (variant.solver_id, variant.param_set_index): variant
        for variant in input_data.variant_summaries
    }

    missing = [
        {"solver_id": ref.solver_id, "param_set_index": ref.param_set_index}
        for ref in cfg.required_variants
        if (ref.solver_id, ref.param_set_index) not in variants
    ]
    if missing:
        return DatasetEvalDecision(
            passed=False,
            verdict=FAIL,
            message="Required variants are missing from the dataset result.",
            details={"missing_variants": missing},
        )

    validity_failures = _validity_failures(input_data.variant_summaries)
    if validity_failures:
        return DatasetEvalDecision(
            passed=False,
            verdict=FAIL,
            message="Some variant summaries are invalid.",
            details={"failures": validity_failures},
        )

    variant_pdevs = {
        f"{variant.solver_id}/param_{variant.param_set_index}": variant.summary.overall.pdev
        for variant in input_data.variant_summaries
    }
    if cfg.target_variant is None:
        return DatasetEvalDecision(
            passed=True,
            verdict=PASS,
            message="All variant summaries are valid.",
            details={"variant_pdevs": variant_pdevs},
        )

    target_key = (cfg.target_variant.solver_id, cfg.target_variant.param_set_index)
    target_variant = variants.get(target_key)
    if target_variant is None:
        return DatasetEvalDecision(
            passed=False,
            verdict=FAIL,
            message="Target variant is missing from the dataset result.",
            details={
                "target_variant": {
                    "solver_id": cfg.target_variant.solver_id,
                    "param_set_index": cfg.target_variant.param_set_index,
                }
            },
        )

    comparable = [
        variant
        for variant in input_data.variant_summaries
        if variant.summary.overall.pdev is not None
    ]
    if not comparable:
        return DatasetEvalDecision(
            passed=False,
            verdict=FAIL,
            message="No comparable variant contains pdev.",
        )
    best_variant = min(comparable, key=lambda variant: float(variant.summary.overall.pdev))
    target_pdev = float(target_variant.summary.overall.pdev)
    best_pdev = float(best_variant.summary.overall.pdev)
    passed = target_pdev - best_pdev <= cfg.pdev_tolerance
    return DatasetEvalDecision(
        passed=passed,
        verdict=PASS if passed else FAIL,
        message="Target variant is within tolerance of the best pdev." if passed else "Target variant is not near-best.",
        details={
            "target_variant": {
                "solver_id": target_variant.solver_id,
                "param_set_index": target_variant.param_set_index,
                "pdev": target_pdev,
            },
            "best_variant": {
                "solver_id": best_variant.solver_id,
                "param_set_index": best_variant.param_set_index,
                "pdev": best_pdev,
            },
            "pdev_tolerance": cfg.pdev_tolerance,
            "variant_pdevs": variant_pdevs,
        },
    )


def _parse_config(raw_config: dict[str, Any]) -> _LiteratureMkpConfig:
    keys = {str(key) for key in raw_config}
    unknown = sorted(keys - _ALLOWED_CONFIG_KEYS)
    if unknown:
        raise ValueError(f"evaluation.config has unknown key(s): {unknown}")
    pdev_tolerance = raw_config.get("pdev_tolerance", 0.0)
    if isinstance(pdev_tolerance, bool) or not isinstance(pdev_tolerance, (int, float)):
        raise ValueError("evaluation.config.pdev_tolerance must be numeric.")
    if float(pdev_tolerance) < 0:
        raise ValueError("evaluation.config.pdev_tolerance must be >= 0.")
    required_variants = _parse_variant_refs(
        raw_config.get("required_variants", []),
        field_name="evaluation.config.required_variants",
    )
    target_variant = None
    if "target_variant" in raw_config:
        target_variant = _parse_variant_ref(
            raw_config["target_variant"],
            field_name="evaluation.config.target_variant",
        )
    return _LiteratureMkpConfig(
        pdev_tolerance=float(pdev_tolerance),
        required_variants=required_variants,
        target_variant=target_variant,
    )


def _parse_variant_refs(value: Any, *, field_name: str) -> tuple[_VariantRef, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list.")
    refs = tuple(_parse_variant_ref(item, field_name=f"{field_name}[{index}]") for index, item in enumerate(value))
    if len({(ref.solver_id, ref.param_set_index) for ref in refs}) != len(refs):
        raise ValueError(f"{field_name} cannot contain duplicate value.")
    return refs


def _parse_variant_ref(value: Any, *, field_name: str) -> _VariantRef:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a mapping.")
    keys = {str(key) for key in value}
    required = {"solver", "param_set_index"}
    missing = sorted(required - keys)
    unknown = sorted(keys - required)
    if missing:
        raise ValueError(f"{field_name} missing required key(s): {missing}")
    if unknown:
        raise ValueError(f"{field_name} has unknown key(s): {unknown}")
    solver_id = value["solver"]
    param_set_index = value["param_set_index"]
    if not isinstance(solver_id, str) or not solver_id.strip():
        raise ValueError(f"{field_name}.solver must be a non-empty string.")
    if isinstance(param_set_index, bool) or not isinstance(param_set_index, int) or param_set_index < 0:
        raise ValueError(f"{field_name}.param_set_index must be a non-negative integer.")
    return _VariantRef(solver_id=solver_id.strip(), param_set_index=param_set_index)


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
