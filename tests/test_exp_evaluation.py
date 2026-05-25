from __future__ import annotations

from mkp.cli.exp.mkp_base import mkp_base_evaluator
from mkp.cli.exp.mkp_base2 import mkp_base2_evaluator
from mkp.experiment import (
    DatasetSetting,
    EvaluationBaseline,
    EvaluationSpec,
    FAIL,
    PASS,
    ProblemSetting,
    RoundEvalInput,
    VariantSummary,
)
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
    evaluation: EvaluationSpec | None = None,
    variants: tuple[VariantSummary, ...] | None = None,
) -> RoundEvalInput:
    eval_spec = evaluation or EvaluationSpec(
        name="mkp_base",
        base_line=(EvaluationBaseline(name="baseline", pdev=2.0),),
    )
    problem_setting = ProblemSetting(problem_id="p1", evaluations=(eval_spec,))
    dataset_setting = DatasetSetting(
        experiment_id="exp1",
        dataset="DATA",
        problem_settings=(problem_setting,),
        problem_type="mkp",
    )
    result = SimulatorResult(machine_results=())
    return RoundEvalInput(
        dataset_setting=dataset_setting,
        problem_setting=problem_setting,
        problem_id="p1",
        repeat_index=0,
        evaluation=eval_spec,
        evaluation_name=eval_spec.name,
        variant_summaries=variants
        or (
            _variant_summary(solver_id="solver_a", param_set_index=0, params={"z": 0.08}, pdev=1.0),
            _variant_summary(solver_id="solver_b", param_set_index=1, params={"a": 1.5}, pdev=2.0),
        ),
        simulator_result=result,
        collected_result=result,
        candidate_result=result,
        projected_result=result,
    )


def test_mkp_base_passes_when_all_variants_beat_best_baseline() -> None:
    decision = mkp_base_evaluator(_input())

    assert decision.passed is True
    assert decision.verdict == PASS
    assert decision.details["threshold_pdev"] == 2.0


def test_mkp_base_fails_when_any_variant_is_worse_than_best_baseline() -> None:
    decision = mkp_base_evaluator(
        _input(
            variants=(
                _variant_summary(solver_id="solver_a", param_set_index=0, params={}, pdev=1.0),
                _variant_summary(solver_id="solver_b", param_set_index=0, params={}, pdev=2.1),
            )
        )
    )

    assert decision.passed is False
    assert decision.verdict == FAIL
    assert decision.details["worse_variants"][0]["variant"] == "solver_b/param_0"


def test_mkp_base_zero_pdev_baseline_is_strict() -> None:
    decision = mkp_base_evaluator(
        _input(
            evaluation=EvaluationSpec(
                name="mkp_base",
                base_line=(EvaluationBaseline(name="zero", pdev=0.0),),
            ),
            variants=(
                _variant_summary(solver_id="solver_a", param_set_index=0, params={}, pdev=0.1),
            ),
        )
    )

    assert decision.passed is False


def test_mkp_base_fails_on_invalid_summary() -> None:
    bad_variant = _variant_summary(
        solver_id="solver_a",
        param_set_index=0,
        params={"z": 0.08},
        pdev=1.0,
        valid_run_count=1,
    )
    decision = mkp_base_evaluator(_input(variants=(bad_variant,)))

    assert decision.passed is False
    assert decision.verdict == FAIL
    assert decision.details["failures"][0]["solver_id"] == "solver_a"


def test_mkp_base2_passes_when_brlsmasca_is_best_or_tied() -> None:
    decision = mkp_base2_evaluator(
        _input(
            evaluation=EvaluationSpec(name="mkp_base2"),
            variants=(
                _variant_summary(solver_id="bsma_numba", param_set_index=0, params={}, pdev=1.1),
                _variant_summary(solver_id="brlsmasca_rl_numba", param_set_index=0, params={}, pdev=1.1),
            ),
        )
    )

    assert decision.passed is True
    assert decision.verdict == PASS


def test_mkp_base2_fails_when_brlsmasca_is_not_best() -> None:
    decision = mkp_base2_evaluator(
        _input(
            evaluation=EvaluationSpec(name="mkp_base2"),
            variants=(
                _variant_summary(solver_id="bsma_numba", param_set_index=0, params={}, pdev=1.0),
                _variant_summary(solver_id="brlsmasca_rl_numba", param_set_index=0, params={}, pdev=1.1),
            ),
        )
    )

    assert decision.passed is False
    assert decision.verdict == FAIL
    assert decision.details["worse_targets"][0]["target"] == "brlsmasca_rl_numba/param_0"
