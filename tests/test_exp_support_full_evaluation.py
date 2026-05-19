from __future__ import annotations

from typing import Any

import pytest

from mkp.cli.exp import literature_mkp_support_full as full_eval
from mkp.experiment import (
    DatasetEvalDecision,
    DatasetRunResult,
    DatasetSetting,
    EvaluationSpec,
    ExperimentEvalInput,
    FAIL,
    PaperSetDecisionRecord,
    PaperSetEvalInput,
    SOFT_PASS,
    STRICT_PASS,
    VariantSummary,
)
from mkp.simulator import SimulatorResult
from mkp.tools.stat import ExcludedCounts, OverallSummary, ProblemSolverSummary, SummaryMeta, SummaryReport


_PROBLEMS = (
    ("WEISH", "p1"),
    ("WEISH", "p2"),
    ("WEISH", "p3"),
    ("WEISH", "p4"),
    ("WEISH", "p5"),
)


def _variant_summary(
    *,
    solver_id: str,
    param_set_index: int,
    params: dict[str, Any],
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
                for (dataset, problem_id), pdev in problem_pdevs.items()
            ],
        ),
    )


def _transfer_variants(*, random50_v_best: bool = True) -> tuple[VariantSummary, ...]:
    family_specs = (
        ("bsma_numba_transfer_literature", {"z": 0.08}),
        ("bsca_numba_transfer_literature", {"a": 1.5}),
        ("brlsmasca_numba_transfer_literature", {"z": 0.08, "a": 2.5, "policy_mode": "rl_best_method"}),
        (
            "brlsmasca_numba_random50_transfer_literature",
            {"z": 0.08, "a": 2.5, "policy_mode": "random_family_50_50"},
        ),
    )
    pdev_grid = {
        "sigmoid_s0": 0.08,
        "abs_pow_17": 0.07 if random50_v_best else 0.03,
        "tanh_abs": 0.03,
    }
    variants: list[VariantSummary] = []
    for solver_id, params in family_specs:
        per_ctf = dict(pdev_grid)
        if solver_id == "brlsmasca_numba_random50_transfer_literature" and not random50_v_best:
            per_ctf = {"sigmoid_s0": 0.08, "abs_pow_17": 0.02, "tanh_abs": 0.03}
        for index, ctf in enumerate(("sigmoid_s0", "abs_pow_17", "tanh_abs")):
            variants.append(
                _variant_summary(
                    solver_id=solver_id,
                    param_set_index=index,
                    params={**params, "ctf": ctf, "pop_size": 20},
                    overall_pdev=per_ctf[ctf],
                    problem_pdevs={problem: per_ctf[ctf] for problem in _PROBLEMS[:3]},
                )
            )
    return tuple(variants)


def _calibration_variants(*, break_calibration: bool = False) -> tuple[VariantSummary, ...]:
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
    hsmsca_problem_pdevs = {
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
    hsmsca_overall = {signature: 0.09 for signature in hsmsca_order}
    hsmsca_overall[(0.08, 2.5)] = 0.05
    for index, signature in enumerate(hsmsca_order):
        variants.append(
            _variant_summary(
                solver_id="brlsmasca_numba_literature",
                param_set_index=index,
                params={"pop_size": 20, "z": signature[0], "a": signature[1], "ctf": "tanh_abs"},
                overall_pdev=hsmsca_overall[signature],
                problem_pdevs=hsmsca_problem_pdevs[signature],
            )
        )
    return tuple(variants)


def _final_variants(
    *,
    hsmsca_overall: float = 0.03,
    random50_overall: float = 0.07,
    equal_isma_problem_pdevs: bool = False,
) -> tuple[VariantSummary, ...]:
    variants: list[VariantSummary] = []
    bsma_problem_grid = {
        (0.01,): {problem: 0.09 for problem in _PROBLEMS},
        (0.08,): {problem: (0.03 if equal_isma_problem_pdevs else 0.05) for problem in _PROBLEMS},
        (0.15,): {problem: 0.08 for problem in _PROBLEMS},
    }
    for index, signature in enumerate(((0.01,), (0.08,), (0.15,))):
        overall = 0.07 if signature == (0.08,) else 0.09
        variants.append(
            _variant_summary(
                solver_id="bsma_numba_literature",
                param_set_index=index,
                params={"pop_size": 20, "z": signature[0], "ctf": "tanh_abs"},
                overall_pdev=overall,
                problem_pdevs=bsma_problem_grid[signature],
            )
        )

    bsca_problem_grid = {
        (1.5,): {problem: 0.06 for problem in _PROBLEMS},
        (2.0,): {problem: 0.08 for problem in _PROBLEMS},
        (2.5,): {problem: 0.09 for problem in _PROBLEMS},
    }
    for index, signature in enumerate(((1.5,), (2.0,), (2.5,))):
        overall = 0.06 if signature == (1.5,) else 0.08
        variants.append(
            _variant_summary(
                solver_id="bsca_numba_literature",
                param_set_index=index,
                params={"pop_size": 20, "a": signature[0], "ctf": "tanh_abs"},
                overall_pdev=overall,
                problem_pdevs=bsca_problem_grid[signature],
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
    hsmsca_problem_grid = {signature: {problem: 0.09 for problem in _PROBLEMS} for signature in hsmsca_order}
    hsmsca_problem_grid[(0.08, 2.5)] = {problem: 0.03 for problem in _PROBLEMS}
    for index, signature in enumerate(hsmsca_order):
        overall = hsmsca_overall if signature == (0.08, 2.5) else 0.09
        variants.append(
            _variant_summary(
                solver_id="brlsmasca_numba_literature",
                param_set_index=index,
                params={"pop_size": 20, "z": signature[0], "a": signature[1], "ctf": "tanh_abs"},
                overall_pdev=overall,
                problem_pdevs=hsmsca_problem_grid[signature],
            )
        )

    variants.append(
        _variant_summary(
            solver_id="brlsmasca_numba_random50_literature",
            param_set_index=0,
            params={
                "pop_size": 20,
                "z": 0.08,
                "a": 2.5,
                "ctf": "tanh_abs",
                "policy_mode": "random_family_50_50",
            },
            overall_pdev=random50_overall,
            problem_pdevs={problem: 0.07 for problem in _PROBLEMS},
        )
    )
    return tuple(variants)


def _paper_input(*, random50_v_best: bool = True, break_calibration: bool = False) -> PaperSetEvalInput:
    setting = DatasetSetting(
        "weish-expTest",
        "WEISH",
        ("p1", "p2", "p3"),
        "mkp",
        "set2",
        EvaluationSpec(name="literature_mkp_support_full", config={}),
    )
    variants = _transfer_variants(random50_v_best=random50_v_best) + _calibration_variants(
        break_calibration=break_calibration
    )
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
        evaluation_name="literature_mkp_support_full",
        evaluation_config={},
        variant_summaries=variants,
        dataset_results=(dataset_result,),
    )


def _global_input(
    *,
    hsmsca_overall: float = 0.03,
    random50_overall: float = 0.07,
    equal_isma_problem_pdevs: bool = False,
) -> ExperimentEvalInput:
    setting = DatasetSetting(
        "weish-expTest",
        "WEISH",
        tuple(problem_id for _, problem_id in _PROBLEMS),
        "mkp",
        "set2",
        EvaluationSpec(name="literature_mkp_support_full", config={}),
    )
    variants = _final_variants(
        hsmsca_overall=hsmsca_overall,
        random50_overall=random50_overall,
        equal_isma_problem_pdevs=equal_isma_problem_pdevs,
    )
    dataset_result = DatasetRunResult(
        seed=11,
        dataset_setting=setting,
        simulator_result=SimulatorResult(rows=(), variant_params={}),
        variant_summaries=variants,
    )
    return ExperimentEvalInput(
        seed=11,
        evaluation_name="literature_mkp_support_full",
        evaluation_config={},
        variant_summaries=variants,
        dataset_results=(dataset_result,),
        paper_set_evaluations=(
            PaperSetDecisionRecord(
                paper_set="set2",
                dataset_settings=(setting,),
                decision=DatasetEvalDecision(passed=True, verdict=STRICT_PASS, message="paper strict"),
            ),
        ),
    )


def test_full_paper_set_evaluator_returns_strict_pass_when_transfer_and_calibration_match() -> None:
    decision = full_eval.literature_mkp_support_full_paper_set_evaluator(_paper_input())

    assert decision.passed is True
    assert decision.verdict == STRICT_PASS
    assert decision.details["transfer"]["verdict"] == STRICT_PASS
    assert decision.details["calibration"]["verdict"] == STRICT_PASS


def test_full_paper_set_evaluator_fails_when_any_family_does_not_prefer_v_shape() -> None:
    decision = full_eval.literature_mkp_support_full_paper_set_evaluator(
        _paper_input(random50_v_best=False)
    )

    assert decision.passed is False
    assert decision.verdict == FAIL
    assert decision.details["transfer"]["families"]["RANDOM50"]["best_transfer"] == "U"


def test_full_paper_set_evaluator_fails_when_no_calibration_pair_supports_targets() -> None:
    decision = full_eval.literature_mkp_support_full_paper_set_evaluator(
        _paper_input(break_calibration=True)
    )

    assert decision.passed is False
    assert decision.verdict == FAIL
    assert decision.details["calibration"]["verdict"] == FAIL


def test_full_global_evaluator_returns_strict_pass_when_internal_and_wilcoxon_pass(monkeypatch) -> None:
    monkeypatch.setattr(
        full_eval,
        "_paper_set_external_checks",
        lambda dataset_results, tolerance: {
            "set2": {
                "verdict": STRICT_PASS,
                "hsmsca_pdev": 0.03,
                "external_baselines": {"HLMS": 0.154},
                "strict": {"HLMS": True},
                "soft": {"HLMS": True},
            }
        },
    )

    decision = full_eval.literature_mkp_support_full_experiment_evaluator(_global_input())

    assert decision.passed is True
    assert decision.verdict == STRICT_PASS
    assert decision.details["final"]["verdict"] == STRICT_PASS
    assert decision.details["wilcoxon"]["verdict"] == STRICT_PASS


def test_full_global_evaluator_fails_when_hsmsca_rl_loses_final_comparison(monkeypatch) -> None:
    monkeypatch.setattr(
        full_eval,
        "_paper_set_external_checks",
        lambda dataset_results, tolerance: {
            "set2": {
                "verdict": STRICT_PASS,
                "hsmsca_pdev": 0.08,
                "external_baselines": {"HLMS": 0.154},
                "strict": {"HLMS": True},
                "soft": {"HLMS": True},
            }
        },
    )

    decision = full_eval.literature_mkp_support_full_experiment_evaluator(
        _global_input(hsmsca_overall=0.08, random50_overall=0.04)
    )

    assert decision.passed is False
    assert decision.verdict == FAIL
    assert decision.details["final"]["internal_comparisons"]["strict"]["RANDOM50"] is False


def test_full_global_evaluator_fails_when_wilcoxon_direction_or_significance_is_not_supported(monkeypatch) -> None:
    monkeypatch.setattr(
        full_eval,
        "_paper_set_external_checks",
        lambda dataset_results, tolerance: {
            "set2": {
                "verdict": STRICT_PASS,
                "hsmsca_pdev": 0.03,
                "external_baselines": {"HLMS": 0.154},
                "strict": {"HLMS": True},
                "soft": {"HLMS": True},
            }
        },
    )

    decision = full_eval.literature_mkp_support_full_experiment_evaluator(
        _global_input(equal_isma_problem_pdevs=True)
    )

    assert decision.passed is False
    assert decision.verdict == FAIL
    assert decision.details["wilcoxon"]["comparisons"]["ISMA"]["verdict"] == FAIL
