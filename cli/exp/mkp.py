from __future__ import annotations

import math
from typing import Any

from ...experiment.evaluation import (
    DatasetEvalDecision,
    DatasetEvalInput,
    FAIL,
    PASS,
    VariantSummary,
)


# 註冊的評估函數
def literature_mkp_evaluator(input_data: DatasetEvalInput) -> DatasetEvalDecision:
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
    return DatasetEvalDecision(
        passed=True,
        verdict=PASS,
        message="All variant summaries are valid.",
        details={"variant_pdevs": variant_pdevs},
    )


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
