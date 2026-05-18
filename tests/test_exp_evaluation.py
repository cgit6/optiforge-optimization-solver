from __future__ import annotations

from mkp.cli.exp.literature_mkp import literature_mkp_evaluator
from mkp.experiment import DatasetEvalInput, DatasetSetting, EvaluationSpec, FAIL, PASS, VariantSummary
from mkp.simulator import SimulatorResult
from mkp.tools.stat import ExcludedCounts, OverallSummary, ProblemSolverSummary, SummaryMeta, SummaryReport


def _variant_summary(
    *,
    solver_id: str,
    param_set_index: int,
    params: dict,
    pdev: float = 1.0,
    valid_run_count: int = 2,
) -> VariantSummary:
    return VariantSummary(
        solver_id=solver_id,
        param_set_index=param_set_index,
        params=params,
        summary=SummaryReport(
            overall=OverallSummary(
                total_runs=2,
                valid_run_count=valid_run_count,
                feasible_rate=1.0,
                avg_runtime=0.1,
                avg_evaluation_count=10.0,
                meta=SummaryMeta(solver_id=solver_id, param_set_index=param_set_index, params=params),
                best_known=100,
                avg_objective=100 - pdev,
                std_objective=0.0,
                best_objective=100 - pdev,
                worst_objective=100 - pdev,
                pdev=pdev,
                direction="max",
                excluded_counts=ExcludedCounts(infeasible=0, objective_mismatch=0, runtime_error=0),
            ),
            by_problem_solver=[
                ProblemSolverSummary(
                    problem_type="mkp",
                    dataset="DATA",
                    encoding="binary",
                    direction="max",
                    problem_id="p1",
                    run_count=2,
                    valid_run_count=valid_run_count,
                    feasible_rate=1.0,
                    avg_runtime=0.1,
                    avg_evaluation_count=10.0,
                    best_known=100,
                    avg_objective=100 - pdev,
                    std_objective=0.0,
                    best_objective=100 - pdev,
                    worst_objective=100 - pdev,
                    pdev=pdev,
                    excluded_counts=ExcludedCounts(infeasible=0, objective_mismatch=0, runtime_error=0),
                    best_known_reached_count=0,
                    best_known_gap_min=pdev,
                    best_known_gap_avg=pdev,
                )
            ],
        ),
    )


def _input(
    *,
    config: dict | None = None,
    variants: tuple[VariantSummary, ...] | None = None,
) -> DatasetEvalInput:
    return DatasetEvalInput(
        seed=7,
        dataset_setting=DatasetSetting(
            "exp1",
            "DATA",
            ("p1",),
            "mkp",
            EvaluationSpec(name="literature_mkp", config={} if config is None else config),
        ),
        evaluation_name="literature_mkp",
        evaluation_config={} if config is None else config,
        variant_summaries=variants
        or (
            _variant_summary(solver_id="solver_a", param_set_index=0, params={"z": 0.08}, pdev=1.0),
            _variant_summary(solver_id="solver_b", param_set_index=1, params={"a": 1.5}, pdev=2.0),
        ),
        simulator_result=SimulatorResult(rows=(), variant_params={("solver_a", 0): {"z": 0.08}}),
    )


def test_literature_evaluator_passes_with_empty_config() -> None:
    decision = literature_mkp_evaluator(_input())

    assert decision.passed is True
    assert decision.verdict == PASS
    assert "variant_pdevs" in decision.details


def test_literature_evaluator_fails_when_required_variant_missing() -> None:
    decision = literature_mkp_evaluator(
        _input(
            config={
                "required_variants": [
                    {"solver": "solver_a", "param_set_index": 0},
                    {"solver": "solver_missing", "param_set_index": 9},
                ]
            }
        )
    )

    assert decision.passed is False
    assert decision.verdict == FAIL
    assert decision.details["missing_variants"][0]["solver_id"] == "solver_missing"


def test_literature_evaluator_fails_when_target_not_near_best() -> None:
    decision = literature_mkp_evaluator(
        _input(
            config={
                "pdev_tolerance": 0.1,
                "target_variant": {"solver": "solver_b", "param_set_index": 1},
            }
        )
    )

    assert decision.passed is False
    assert decision.verdict == FAIL
    assert decision.details["best_variant"]["solver_id"] == "solver_a"


def test_literature_evaluator_passes_when_target_within_tolerance() -> None:
    decision = literature_mkp_evaluator(
        _input(
            config={
                "pdev_tolerance": 1.1,
                "target_variant": {"solver": "solver_b", "param_set_index": 1},
            }
        )
    )

    assert decision.passed is True
    assert decision.verdict == PASS


def test_literature_evaluator_fails_on_invalid_summary() -> None:
    bad_variant = _variant_summary(
        solver_id="solver_a",
        param_set_index=0,
        params={"z": 0.08},
        pdev=1.0,
        valid_run_count=1,
    )
    decision = literature_mkp_evaluator(
        _input(
            variants=(
                bad_variant,
                _variant_summary(solver_id="solver_b", param_set_index=1, params={"a": 1.5}, pdev=2.0),
            )
        )
    )

    assert decision.passed is False
    assert decision.verdict == FAIL
    assert decision.details["failures"][0]["solver_id"] == "solver_a"
