from __future__ import annotations

import math

from mkp.cli.exp.mkp_base import mkp_base_evaluator, mkp_bsca_base_margin_2_evaluator
from mkp.cli.exp.mkp_base2 import mkp_base2_evaluator, mkp_base2_margin_005_evaluator
from mkp.cli.exp.mkp_calibration import (
    mkp_calibration_evaluator,
    mkp_target_combo_brlsmasca_margin_004_evaluator,
    mkp_target_combo_bsma_strict_evaluator,
    mkp_target_combo_bsca_margin_005_evaluator,
    mkp_target_combo_best_evaluator,
    mkp_target_combo_core_strict_evaluator,
    mkp_transfer_bsca_margin_005_evaluator,
    mkp_transfer_core_strict_evaluator,
    mkp_transfer_paired_strict_evaluator,
)
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


def test_mkp_base_passes_when_bsma_and_brlsmasca_beat_best_baseline() -> None:
    decision = mkp_base_evaluator(
        _input(
            variants=(
                _variant_summary(solver_id="bsma_numba", param_set_index=1, params={}, pdev=1.0),
                _variant_summary(solver_id="bsca_numba", param_set_index=0, params={}, pdev=5.0),
                _variant_summary(solver_id="brlsmasca_rl_numba", param_set_index=5, params={}, pdev=2.0),
                _variant_summary(solver_id="brlsmasca_test_numba", param_set_index=2, params={}, pdev=5.0),
            )
        )
    )

    assert decision.passed is True
    assert decision.verdict == PASS
    assert decision.details["threshold_pdev"] == 2.0
    assert sorted(decision.details["target_pdevs"]) == [
        "brlsmasca_rl_numba/param_5",
        "bsma_numba/param_1",
    ]


def test_mkp_base_fails_when_bsma_or_brlsmasca_is_worse_than_best_baseline() -> None:
    decision = mkp_base_evaluator(
        _input(
            variants=(
                _variant_summary(solver_id="bsma_numba", param_set_index=1, params={}, pdev=1.0),
                _variant_summary(solver_id="bsca_numba", param_set_index=0, params={}, pdev=1.0),
                _variant_summary(solver_id="brlsmasca_rl_numba", param_set_index=5, params={}, pdev=2.1),
            )
        )
    )

    assert decision.passed is False
    assert decision.verdict == FAIL
    assert decision.details["worse_variants"][0]["variant"] == "brlsmasca_rl_numba/param_5"


def test_mkp_base_zero_pdev_baseline_is_strict() -> None:
    decision = mkp_base_evaluator(
        _input(
            evaluation=EvaluationSpec(
                name="mkp_base",
                base_line=(EvaluationBaseline(name="zero", pdev=0.0),),
            ),
            variants=(
                _variant_summary(solver_id="bsma_numba", param_set_index=1, params={}, pdev=0.0),
                _variant_summary(solver_id="brlsmasca_rl_numba", param_set_index=5, params={}, pdev=0.1),
            ),
        )
    )

    assert decision.passed is False


def test_mkp_base_fails_on_invalid_summary() -> None:
    bad_variant = _variant_summary(
        solver_id="bsma_numba",
        param_set_index=1,
        params={"z": 0.08},
        pdev=1.0,
        valid_run_count=1,
    )
    decision = mkp_base_evaluator(_input(variants=(bad_variant,)))

    assert decision.passed is False
    assert decision.verdict == FAIL
    assert decision.details["failures"][0]["solver_id"] == "bsma_numba"


def test_mkp_bsca_base_margin_2_passes_when_bsca_is_within_margin() -> None:
    decision = mkp_bsca_base_margin_2_evaluator(
        _input(
            evaluation=EvaluationSpec(
                name="mkp_bsca_base_margin_2",
                base_line=(EvaluationBaseline(name="baseline", pdev=0.879),),
            ),
            variants=(
                _variant_summary(solver_id="bsma_numba", param_set_index=1, params={}, pdev=0.1),
                _variant_summary(solver_id="bsca_numba", param_set_index=0, params={}, pdev=2.879),
                _variant_summary(solver_id="brlsmasca_rl_numba", param_set_index=5, params={}, pdev=0.1),
            ),
        )
    )

    assert decision.passed is True
    assert decision.verdict == PASS
    assert decision.details["threshold_pdev"] == 2.879


def test_mkp_bsca_base_margin_2_fails_when_bsca_exceeds_margin() -> None:
    decision = mkp_bsca_base_margin_2_evaluator(
        _input(
            evaluation=EvaluationSpec(
                name="mkp_bsca_base_margin_2",
                base_line=(EvaluationBaseline(name="baseline", pdev=0.879),),
            ),
            variants=(
                _variant_summary(solver_id="bsma_numba", param_set_index=1, params={}, pdev=0.1),
                _variant_summary(solver_id="bsca_numba", param_set_index=0, params={}, pdev=2.88),
                _variant_summary(solver_id="brlsmasca_rl_numba", param_set_index=5, params={}, pdev=0.1),
            ),
        )
    )

    assert decision.passed is False
    assert decision.verdict == FAIL
    assert decision.details["worse_variants"][0]["variant"] == "bsca_numba/param_0"


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


def test_mkp_base2_margin_005_passes_when_brlsmasca_is_within_margin() -> None:
    decision = mkp_base2_margin_005_evaluator(
        _input(
            evaluation=EvaluationSpec(name="mkp_base2_margin_005"),
            variants=(
                _variant_summary(solver_id="bsma_numba", param_set_index=0, params={}, pdev=1.00),
                _variant_summary(solver_id="bsca_numba", param_set_index=0, params={}, pdev=1.04),
                _variant_summary(solver_id="brlsmasca_rl_numba", param_set_index=5, params={}, pdev=1.05),
                _variant_summary(solver_id="brlsmasca_test_numba", param_set_index=2, params={}, pdev=1.02),
            ),
        )
    )

    assert decision.passed is True
    assert decision.verdict == PASS
    assert decision.details["best_pdev"] == 1.00
    assert decision.details["threshold_pdev"] == 1.05


def test_mkp_base2_margin_005_fails_when_brlsmasca_exceeds_margin() -> None:
    decision = mkp_base2_margin_005_evaluator(
        _input(
            evaluation=EvaluationSpec(name="mkp_base2_margin_005"),
            variants=(
                _variant_summary(solver_id="bsma_numba", param_set_index=0, params={}, pdev=1.00),
                _variant_summary(solver_id="bsca_numba", param_set_index=0, params={}, pdev=1.03),
                _variant_summary(solver_id="brlsmasca_rl_numba", param_set_index=5, params={}, pdev=1.051),
                _variant_summary(solver_id="brlsmasca_test_numba", param_set_index=2, params={}, pdev=1.02),
            ),
        )
    )

    assert decision.passed is False
    assert decision.verdict == FAIL
    assert decision.details["worse_targets"][0]["target"] == "brlsmasca_rl_numba/param_5"


def _calibration_variants(*, break_bsma_target: bool = False) -> tuple[VariantSummary, ...]:
    variants: list[VariantSummary] = []
    index = 0
    for ctf in ("tanh_abs", "sigmoid_s0", "abs_pow_16"):
        for z in (0.01, 0.08, 0.15):
            pdev = {
                "tanh_abs": 0.6,
                "sigmoid_s0": 0.4,
                "abs_pow_16": 0.2,
            }[ctf]
            if ctf == "tanh_abs" and z == 0.08:
                pdev = 0.1
            if break_bsma_target and ctf == "tanh_abs" and z == 0.15:
                pdev = 0.01
            variants.append(
                _variant_summary(
                    solver_id="bsma_numba",
                    param_set_index=index,
                    params={"z": z, "ctf": ctf},
                    pdev=pdev,
                )
            )
            index += 1

    index = 0
    for ctf in ("tanh_abs", "sigmoid_s0", "abs_pow_16"):
        for a in (1.5, 2.0, 2.5):
            pdev = {
                "tanh_abs": 0.6,
                "sigmoid_s0": 0.4,
                "abs_pow_16": 0.2,
            }[ctf]
            if ctf == "tanh_abs" and a == 1.5:
                pdev = 0.1
            variants.append(
                _variant_summary(
                    solver_id="bsca_numba",
                    param_set_index=index,
                    params={"a": a, "ctf": ctf},
                    pdev=pdev,
                )
            )
            index += 1

    index = 0
    for ctf in ("tanh_abs", "sigmoid_s0", "abs_pow_16"):
        for z in (0.01, 0.08, 0.15):
            for a in (1.5, 2.0, 2.5):
                pdev = {
                    "tanh_abs": 0.6,
                    "sigmoid_s0": 0.4,
                    "abs_pow_16": 0.2,
                }[ctf]
                if ctf == "tanh_abs" and z == 0.08 and a == 2.5:
                    pdev = 0.1
                variants.append(
                    _variant_summary(
                        solver_id="brlsmasca_rl_numba",
                        param_set_index=index,
                        params={"z": z, "a": a, "ctf": ctf},
                        pdev=pdev,
                    )
                )
                index += 1
    return tuple(variants)


def _replace_calibration_variant(
    variants: tuple[VariantSummary, ...],
    *,
    solver_id: str,
    param_set_index: int,
    pdev: float,
) -> tuple[VariantSummary, ...]:
    updated = list(variants)
    for index, variant in enumerate(updated):
        if variant.solver_id == solver_id and variant.param_set_index == param_set_index:
            updated[index] = _variant_summary(
                solver_id=variant.solver_id,
                param_set_index=variant.param_set_index,
                params=variant.params,
                pdev=pdev,
            )
            return tuple(updated)
    raise AssertionError(f"variant not found: {solver_id}/param_{param_set_index}")


def test_mkp_transfer_paired_strict_passes_when_abs_pow_16_is_best_by_paired_average() -> None:
    decision = mkp_transfer_paired_strict_evaluator(
        _input(
            evaluation=EvaluationSpec(name="mkp_transfer_paired_strict"),
            variants=_calibration_variants(),
        )
    )

    assert decision.passed is True
    assert decision.verdict == PASS
    bsma_check = next(
        check for check in decision.details["transfer_checks"] if check["algorithm"] == "bsma"
    )
    assert decision.details["expected_transfer_ctf"] == "abs_pow_16"
    assert bsma_check["expected_ctf"] == "abs_pow_16"
    assert math.isclose(bsma_check["transfer_metrics"]["abs_pow_16"]["avg_pdev"], 0.2)
    assert math.isclose(bsma_check["transfer_metrics"]["abs_pow_16"]["avg_rank"], 4 / 3)


def test_mkp_transfer_paired_strict_fails_when_non_expected_transfer_has_better_paired_average() -> None:
    variants = list(_calibration_variants())
    variants[3] = _variant_summary(
        solver_id="bsma_numba",
        param_set_index=3,
        params={"z": 0.01, "ctf": "sigmoid_s0"},
        pdev=0.01,
    )
    variants[4] = _variant_summary(
        solver_id="bsma_numba",
        param_set_index=4,
        params={"z": 0.08, "ctf": "sigmoid_s0"},
        pdev=0.01,
    )
    variants[5] = _variant_summary(
        solver_id="bsma_numba",
        param_set_index=5,
        params={"z": 0.15, "ctf": "sigmoid_s0"},
        pdev=0.01,
    )

    decision = mkp_transfer_paired_strict_evaluator(
        _input(
            evaluation=EvaluationSpec(name="mkp_transfer_paired_strict"),
            variants=tuple(variants),
        )
    )

    assert decision.passed is False
    assert decision.verdict == FAIL
    assert any(
        failure["algorithm"] == "bsma"
        for failure in decision.details["failures"]
    )


def test_mkp_transfer_core_strict_passes_when_core_algorithms_pass_even_if_bsca_lags() -> None:
    variants = list(_calibration_variants())
    for index in range(9, 18):
        variant = variants[index]
        pdev = 0.0 if variant.params["ctf"] == "sigmoid_s0" else 0.0274
        variants[index] = _variant_summary(
            solver_id=variant.solver_id,
            param_set_index=variant.param_set_index,
            params=variant.params,
            pdev=pdev,
        )

    decision = mkp_transfer_core_strict_evaluator(
        _input(
            evaluation=EvaluationSpec(name="mkp_transfer_core_strict"),
            variants=tuple(variants),
        )
    )

    assert decision.passed is True
    assert decision.verdict == PASS
    assert {
        check["algorithm"] for check in decision.details["core_transfer_checks"]
    } == {"bsma", "bscasma"}


def test_mkp_transfer_bsca_margin_005_passes_when_bsca_is_slightly_worse() -> None:
    variants = list(_calibration_variants())
    for index in range(9, 18):
        variant = variants[index]
        pdev = 0.0 if variant.params["ctf"] == "sigmoid_s0" else 0.0274
        variants[index] = _variant_summary(
            solver_id=variant.solver_id,
            param_set_index=variant.param_set_index,
            params=variant.params,
            pdev=pdev,
        )

    decision = mkp_transfer_bsca_margin_005_evaluator(
        _input(
            evaluation=EvaluationSpec(name="mkp_transfer_bsca_margin_005"),
            variants=tuple(variants),
        )
    )

    assert decision.passed is True
    assert decision.verdict == PASS
    assert decision.details["bsca_margin_check"]["strict_passed"] is False
    assert decision.details["bsca_margin_check"]["margin_passed"] is True
    assert math.isclose(decision.details["bsca_margin_check"]["gap_to_best"], 0.0274)


def test_mkp_transfer_bsca_margin_005_fails_when_bsca_exceeds_margin() -> None:
    variants = list(_calibration_variants())
    for index in range(9, 18):
        variant = variants[index]
        pdev = 0.0 if variant.params["ctf"] == "sigmoid_s0" else 0.051
        variants[index] = _variant_summary(
            solver_id=variant.solver_id,
            param_set_index=variant.param_set_index,
            params=variant.params,
            pdev=pdev,
        )

    decision = mkp_transfer_bsca_margin_005_evaluator(
        _input(
            evaluation=EvaluationSpec(name="mkp_transfer_bsca_margin_005"),
            variants=tuple(variants),
        )
    )

    assert decision.passed is False
    assert decision.verdict == FAIL
    assert decision.details["bsca_margin_check"]["margin_passed"] is False
    assert math.isclose(decision.details["bsca_margin_check"]["gap_to_best"], 0.051)


def test_mkp_transfer_core_strict_fails_when_core_algorithm_fails() -> None:
    variants = list(_calibration_variants())
    for index in (3, 4, 5):
        variant = variants[index]
        variants[index] = _variant_summary(
            solver_id=variant.solver_id,
            param_set_index=variant.param_set_index,
            params=variant.params,
            pdev=0.01,
        )

    decision = mkp_transfer_core_strict_evaluator(
        _input(
            evaluation=EvaluationSpec(name="mkp_transfer_core_strict"),
            variants=tuple(variants),
        )
    )

    assert decision.passed is False
    assert decision.verdict == FAIL
    assert any(
        failure["algorithm"] == "bsma"
        for failure in decision.details["failures"]
    )


def test_mkp_target_combo_best_passes_when_target_combos_are_algorithm_best() -> None:
    decision = mkp_target_combo_best_evaluator(
        _input(
            evaluation=EvaluationSpec(name="mkp_target_combo_best"),
            variants=_calibration_variants(),
        )
    )

    assert decision.passed is True
    assert decision.verdict == PASS
    assert len(decision.details["target_checks"]) == 3


def test_mkp_target_combo_best_fails_when_target_combo_is_not_best() -> None:
    decision = mkp_target_combo_best_evaluator(
        _input(
            evaluation=EvaluationSpec(name="mkp_target_combo_best"),
            variants=_calibration_variants(break_bsma_target=True),
        )
    )

    assert decision.passed is False
    assert decision.verdict == FAIL
    assert any(
        failure["algorithm"] == "bsma"
        for failure in decision.details["failures"]
    )


def test_mkp_target_combo_bsma_strict_passes_when_bsma_target_is_best() -> None:
    decision = mkp_target_combo_bsma_strict_evaluator(
        _input(
            evaluation=EvaluationSpec(name="mkp_target_combo_bsma_strict"),
            variants=_calibration_variants(),
        )
    )

    assert decision.passed is True
    assert decision.verdict == PASS
    assert decision.details["target_check"]["algorithm"] == "bsma"


def test_mkp_target_combo_bsma_strict_fails_when_bsma_target_is_not_best() -> None:
    decision = mkp_target_combo_bsma_strict_evaluator(
        _input(
            evaluation=EvaluationSpec(name="mkp_target_combo_bsma_strict"),
            variants=_calibration_variants(break_bsma_target=True),
        )
    )

    assert decision.passed is False
    assert decision.verdict == FAIL
    assert decision.details["target_check"]["algorithm"] == "bsma"


def test_mkp_target_combo_core_strict_passes_when_core_targets_pass_even_if_bsca_lags() -> None:
    variants = list(_calibration_variants())
    variants[9] = _variant_summary(
        solver_id="bsca_numba",
        param_set_index=0,
        params={"a": 1.5, "ctf": "tanh_abs"},
        pdev=0.0274,
    )
    variants[12] = _variant_summary(
        solver_id="bsca_numba",
        param_set_index=3,
        params={"a": 1.5, "ctf": "sigmoid_s0"},
        pdev=0.0,
    )

    decision = mkp_target_combo_core_strict_evaluator(
        _input(
            evaluation=EvaluationSpec(name="mkp_target_combo_core_strict"),
            variants=tuple(variants),
        )
    )

    assert decision.passed is True
    assert decision.verdict == PASS
    assert {
        check["algorithm"] for check in decision.details["core_target_checks"]
    } == {"bsma", "bscasma"}


def test_mkp_target_combo_bsca_margin_005_passes_when_bsca_target_is_within_margin() -> None:
    variants = list(_calibration_variants())
    variants[9] = _variant_summary(
        solver_id="bsca_numba",
        param_set_index=0,
        params={"a": 1.5, "ctf": "tanh_abs"},
        pdev=0.0274,
    )
    variants[12] = _variant_summary(
        solver_id="bsca_numba",
        param_set_index=3,
        params={"a": 1.5, "ctf": "sigmoid_s0"},
        pdev=0.0,
    )

    decision = mkp_target_combo_bsca_margin_005_evaluator(
        _input(
            evaluation=EvaluationSpec(name="mkp_target_combo_bsca_margin_005"),
            variants=tuple(variants),
        )
    )

    assert decision.passed is True
    assert decision.verdict == PASS
    assert decision.details["bsca_margin_check"]["strict_passed"] is False
    assert decision.details["bsca_margin_check"]["margin_passed"] is True
    assert math.isclose(decision.details["bsca_margin_check"]["gap_to_best"], 0.0274)


def test_mkp_target_combo_bsca_margin_005_fails_when_bsca_target_exceeds_margin() -> None:
    variants = list(_calibration_variants())
    variants[9] = _variant_summary(
        solver_id="bsca_numba",
        param_set_index=0,
        params={"a": 1.5, "ctf": "tanh_abs"},
        pdev=0.051,
    )
    variants[12] = _variant_summary(
        solver_id="bsca_numba",
        param_set_index=3,
        params={"a": 1.5, "ctf": "sigmoid_s0"},
        pdev=0.0,
    )

    decision = mkp_target_combo_bsca_margin_005_evaluator(
        _input(
            evaluation=EvaluationSpec(name="mkp_target_combo_bsca_margin_005"),
            variants=tuple(variants),
        )
    )

    assert decision.passed is False
    assert decision.verdict == FAIL
    assert decision.details["bsca_margin_check"]["margin_passed"] is False
    assert math.isclose(decision.details["bsca_margin_check"]["gap_to_best"], 0.051)


def test_mkp_target_combo_brlsmasca_margin_004_passes_when_brlsmasca_target_is_within_margin() -> None:
    variants = _replace_calibration_variant(
        _calibration_variants(),
        solver_id="brlsmasca_rl_numba",
        param_set_index=19,
        pdev=0.018,
    )
    variants = _replace_calibration_variant(
        variants,
        solver_id="brlsmasca_rl_numba",
        param_set_index=5,
        pdev=0.055,
    )

    decision = mkp_target_combo_brlsmasca_margin_004_evaluator(
        _input(
            evaluation=EvaluationSpec(name="mkp_target_combo_brlsmasca_margin_004"),
            variants=variants,
        )
    )

    assert decision.passed is True
    assert decision.verdict == PASS
    assert decision.details["brlsmasca_margin_check"]["strict_passed"] is False
    assert decision.details["brlsmasca_margin_check"]["margin_passed"] is True
    assert math.isclose(decision.details["brlsmasca_margin_check"]["gap_to_best"], 0.037)


def test_mkp_target_combo_brlsmasca_margin_004_fails_when_brlsmasca_target_exceeds_margin() -> None:
    variants = _replace_calibration_variant(
        _calibration_variants(),
        solver_id="brlsmasca_rl_numba",
        param_set_index=19,
        pdev=0.018,
    )
    variants = _replace_calibration_variant(
        variants,
        solver_id="brlsmasca_rl_numba",
        param_set_index=5,
        pdev=0.059,
    )

    decision = mkp_target_combo_brlsmasca_margin_004_evaluator(
        _input(
            evaluation=EvaluationSpec(name="mkp_target_combo_brlsmasca_margin_004"),
            variants=variants,
        )
    )

    assert decision.passed is False
    assert decision.verdict == FAIL
    assert decision.details["brlsmasca_margin_check"]["margin_passed"] is False
    assert math.isclose(decision.details["brlsmasca_margin_check"]["gap_to_best"], 0.041)


def test_mkp_target_combo_core_strict_fails_when_core_target_fails() -> None:
    decision = mkp_target_combo_core_strict_evaluator(
        _input(
            evaluation=EvaluationSpec(name="mkp_target_combo_core_strict"),
            variants=_calibration_variants(break_bsma_target=True),
        )
    )

    assert decision.passed is False
    assert decision.verdict == FAIL
    assert any(
        failure["algorithm"] == "bsma"
        for failure in decision.details["failures"]
    )


def test_calibration_labels_fail_when_combo_pair_is_missing() -> None:
    variants = tuple(
        variant
        for variant in _calibration_variants()
        if not (
            variant.solver_id == "bsma_numba"
            and variant.params == {"z": 0.01, "ctf": "sigmoid_s0"}
        )
    )
    transfer_decision = mkp_transfer_paired_strict_evaluator(
        _input(
            evaluation=EvaluationSpec(name="mkp_transfer_paired_strict"),
            variants=variants,
        )
    )
    target_decision = mkp_target_combo_best_evaluator(
        _input(
            evaluation=EvaluationSpec(name="mkp_target_combo_best"),
            variants=variants,
        )
    )

    assert transfer_decision.passed is False
    assert target_decision.passed is False
    assert transfer_decision.details["integrity_checks"]["combo_count"]["actual"] == 44
    assert target_decision.details["integrity_checks"]["combo_count"]["actual"] == 44


def test_mkp_calibration_alias_requires_both_new_labels_to_pass() -> None:
    decision = mkp_calibration_evaluator(
        _input(
            evaluation=EvaluationSpec(name="mkp_calibration"),
            variants=_calibration_variants(),
        )
    )

    assert decision.passed is True
    assert decision.verdict == PASS
    assert decision.details["pdev_tolerance"] == 0.0
