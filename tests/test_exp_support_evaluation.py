from __future__ import annotations

from mkp.cli.exp.literature_mkp_support import literature_mkp_support_evaluator
from mkp.experiment import (
    DatasetRunResult,
    DatasetSetting,
    EvaluationSpec,
    FAIL,
    PASS,
    PaperSetEvalInput,
    VariantSummary,
)
from mkp.simulator import SimulatorResult
from mkp.tools.stat import ExcludedCounts, OverallSummary, ProblemSolverSummary, SummaryMeta, SummaryReport


_PROBLEMS = (("WEISH", "p1"), ("WEISH", "p2"), ("WEISH", "p3"))


def _variant_summary(
    *,
    solver_id: str,
    param_set_index: int,
    params: dict,
    overall_pdev: float,
    problem_pdevs: dict[tuple[str, str], float],
) -> VariantSummary:
    return VariantSummary(
        solver_id=solver_id,
        param_set_index=param_set_index,
        params=params,
        summary=SummaryReport(
            overall=OverallSummary(
                total_runs=20,
                valid_run_count=20,
                feasible_rate=1.0,
                avg_runtime=0.1,
                avg_evaluation_count=100000.0,
                meta=SummaryMeta(solver_id=solver_id, param_set_index=param_set_index, params=params),
                best_known=100.0,
                avg_objective=100.0 - overall_pdev,
                std_objective=0.0,
                best_objective=100.0 - overall_pdev,
                worst_objective=100.0 - overall_pdev,
                pdev=overall_pdev,
                direction="max",
                excluded_counts=ExcludedCounts(infeasible=0, objective_mismatch=0, runtime_error=0),
            ),
            by_problem_solver=[
                ProblemSolverSummary(
                    problem_type="mkp",
                    dataset=dataset,
                    encoding="binary",
                    direction="max",
                    problem_id=problem_id,
                    run_count=20,
                    valid_run_count=20,
                    feasible_rate=1.0,
                    avg_runtime=0.1,
                    avg_evaluation_count=100000.0,
                    best_known=100.0,
                    avg_objective=100.0 - pdev,
                    std_objective=0.0,
                    best_objective=100.0 - pdev,
                    worst_objective=100.0 - pdev,
                    pdev=pdev,
                    excluded_counts=ExcludedCounts(infeasible=0, objective_mismatch=0, runtime_error=0),
                    best_known_reached_count=0,
                    best_known_gap_min=pdev,
                    best_known_gap_avg=pdev,
                )
                for dataset, problem_id in _PROBLEMS
                for pdev in [problem_pdevs[(dataset, problem_id)]]
                if (dataset, problem_id) in problem_pdevs
            ],
        ),
    )


def _build_variants(*, hsmsca_overall: float = 0.05, break_calibration: bool = False) -> tuple[VariantSummary, ...]:
    bsma_problem_pdevs = {
        (0.01,): {("WEISH", "p1"): 0.10, ("WEISH", "p2"): 0.12, ("WEISH", "p3"): 0.01},
        (0.08,): {("WEISH", "p1"): 0.05, ("WEISH", "p2"): 0.06, ("WEISH", "p3"): 0.20},
        (0.15,): {("WEISH", "p1"): 0.09, ("WEISH", "p2"): 0.10, ("WEISH", "p3"): 0.03},
    }
    bsca_problem_pdevs = {
        (1.5,): {("WEISH", "p1"): 0.04, ("WEISH", "p2"): 0.05, ("WEISH", "p3"): 0.20},
        (2.0,): {("WEISH", "p1"): 0.07, ("WEISH", "p2"): 0.08, ("WEISH", "p3"): 0.04},
        (2.5,): {("WEISH", "p1"): 0.11, ("WEISH", "p2"): 0.12, ("WEISH", "p3"): 0.05},
    }
    if break_calibration:
        bsca_problem_pdevs[(1.5,)] = {("WEISH", "p1"): 0.12, ("WEISH", "p2"): 0.13, ("WEISH", "p3"): 0.20}

    hsm_problem_pdevs = {
        (0.01, 1.5): {("WEISH", "p1"): 0.09, ("WEISH", "p2"): 0.10, ("WEISH", "p3"): 0.09},
        (0.01, 2.0): {("WEISH", "p1"): 0.08, ("WEISH", "p2"): 0.09, ("WEISH", "p3"): 0.08},
        (0.01, 2.5): {("WEISH", "p1"): 0.07, ("WEISH", "p2"): 0.08, ("WEISH", "p3"): 0.07},
        (0.08, 1.5): {("WEISH", "p1"): 0.06, ("WEISH", "p2"): 0.07, ("WEISH", "p3"): 0.06},
        (0.08, 2.0): {("WEISH", "p1"): 0.04, ("WEISH", "p2"): 0.05, ("WEISH", "p3"): 0.06},
        (0.08, 2.5): {("WEISH", "p1"): 0.03, ("WEISH", "p2"): 0.04, ("WEISH", "p3"): 0.07},
        (0.15, 1.5): {("WEISH", "p1"): 0.05, ("WEISH", "p2"): 0.06, ("WEISH", "p3"): 0.05},
        (0.15, 2.0): {("WEISH", "p1"): 0.05, ("WEISH", "p2"): 0.06, ("WEISH", "p3"): 0.05},
        (0.15, 2.5): {("WEISH", "p1"): 0.06, ("WEISH", "p2"): 0.07, ("WEISH", "p3"): 0.04},
    }

    variants: list[VariantSummary] = []
    bsma_overall = {(0.01,): 0.12, (0.08,): 0.07, (0.15,): 0.09}
    for index, signature in enumerate(((0.01,), (0.08,), (0.15,))):
        variants.append(
            _variant_summary(
                solver_id="bsma_numba_literature",
                param_set_index=index,
                params={"pop_size": 20, "z": signature[0], "ctf": "tanh_abs"},
                overall_pdev=bsma_overall[signature],
                problem_pdevs=bsma_problem_pdevs[signature],
            )
        )

    bsca_overall = {(1.5,): 0.08, (2.0,): 0.10, (2.5,): 0.12}
    for index, signature in enumerate(((1.5,), (2.0,), (2.5,))):
        variants.append(
            _variant_summary(
                solver_id="bsca_numba_literature",
                param_set_index=index,
                params={"pop_size": 20, "a": signature[0], "ctf": "tanh_abs"},
                overall_pdev=bsca_overall[signature],
                problem_pdevs=bsca_problem_pdevs[signature],
            )
        )

    hsmsca_order = (
        (0.01, 1.5),
        (0.01, 2.0),
        (0.01, 2.5),
        (0.08, 1.5),
        (0.08, 2.0),
        (0.08, 2.5),
        (0.15, 1.5),
        (0.15, 2.0),
        (0.15, 2.5),
    )
    hsmsca_overall_map = {signature: 0.09 for signature in hsmsca_order}
    hsmsca_overall_map[(0.08, 2.5)] = hsmsca_overall
    for index, signature in enumerate(hsmsca_order):
        variants.append(
            _variant_summary(
                solver_id="brlsmasca_numba_literature",
                param_set_index=index,
                params={
                    "pop_size": 20,
                    "z": signature[0],
                    "a": signature[1],
                    "prob_arr": [0.04, 0.46, 0.25, 0.25],
                    "ctf": "tanh_abs",
                },
                overall_pdev=hsmsca_overall_map[signature],
                problem_pdevs=hsm_problem_pdevs[signature],
            )
        )
    return tuple(variants)


def _input(*, hsmsca_overall: float = 0.05, break_calibration: bool = False) -> PaperSetEvalInput:
    setting = DatasetSetting(
        "weish-expTest",
        "WEISH",
        ("p1", "p2", "p3"),
        "mkp",
        "set2",
        EvaluationSpec(name="literature_mkp_support", config={}),
    )
    variants = _build_variants(hsmsca_overall=hsmsca_overall, break_calibration=break_calibration)
    dataset_result = DatasetRunResult(
        seed=7,
        dataset_setting=setting,
        simulator_result=SimulatorResult(rows=(), variant_params={}),
        variant_summaries=variants,
    )
    return PaperSetEvalInput(
        seed=7,
        paper_set="set2",
        dataset_settings=(setting,),
        evaluation_name="literature_mkp_support",
        evaluation_config={},
        variant_summaries=variants,
        dataset_results=(dataset_result,),
    )


def test_literature_support_evaluator_passes_and_records_calibration_pair() -> None:
    decision = literature_mkp_support_evaluator(_input())

    assert decision.passed is True
    assert decision.verdict == PASS
    assert decision.details["calibration_pair"] == [
        {"dataset": "WEISH", "problem_id": "p1"},
        {"dataset": "WEISH", "problem_id": "p2"},
    ]
    assert decision.details["set_pdevs"]["HSMSCA"] == 0.05


def test_literature_support_evaluator_fails_when_no_calibration_pair_supports_paper() -> None:
    decision = literature_mkp_support_evaluator(_input(break_calibration=True))

    assert decision.passed is False
    assert decision.verdict == FAIL
    assert "calibration subset" in decision.message


def test_literature_support_evaluator_fails_when_full_set_rank_is_not_supported() -> None:
    decision = literature_mkp_support_evaluator(_input(hsmsca_overall=0.20))

    assert decision.passed is False
    assert decision.verdict == FAIL
    assert decision.details["comparisons"]["hsmsca_vs_external"]["IBSMA_U1"] is False
