from __future__ import annotations

from mkp.experiment.config import (
    DatasetSetting,
    EvaluationSetting,
    ExperimentConfig,
    ExperimentStage,
    ExperimentVariant,
    StaticBaseline,
    StaticBaselineResult,
)
from mkp.experiment.evaluation import FAIL, SOFT_PASS, STRICT_PASS, StageSummary, literature_mkp_evaluator
from mkp.tools.stat import ExcludedCounts, OverallSummary, ProblemSolverSummary, SummaryMeta, SummaryReport


def _variant(
    *,
    stage: str,
    combo_id: str,
    algorithm: str,
    solver_id: str,
    params: dict,
    transfer_type: str | None = None,
    pdevs: tuple[float, float] = (1.0, 1.0),
    valid_run_count: int = 2,
) -> StageSummary:
    return StageSummary(
        stage=stage,
        dataset_experiment_id="ds1",
        dataset="DATA",
        combo_id=combo_id,
        algorithm=algorithm,
        solver_id=solver_id,
        param_set_index=0,
        params=params,
        transfer_type=transfer_type,
        summary=_summary(
            solver_id=solver_id,
            params=params,
            pdevs=pdevs,
            valid_run_count=valid_run_count,
        ),
    )


def _summary(
    *,
    solver_id: str,
    params: dict,
    pdevs: tuple[float, float],
    valid_run_count: int = 2,
) -> SummaryReport:
    groups = [
        _problem_group(problem_id=f"p{index}", pdev=pdev, valid_run_count=valid_run_count)
        for index, pdev in enumerate(pdevs, start=1)
    ]
    avg_pdev = sum(pdevs) / len(pdevs)
    return SummaryReport(
        overall=OverallSummary(
            total_runs=4,
            valid_run_count=4,
            feasible_rate=1.0,
            avg_runtime=0.1,
            avg_evaluation_count=10.0,
            meta=SummaryMeta(solver_id=solver_id, param_set_index=0, params=params),
            best_known=100,
            avg_objective=100 - avg_pdev,
            std_objective=0.0,
            best_objective=100,
            worst_objective=100 - max(pdevs),
            pdev=avg_pdev,
            direction="max",
            excluded_counts=ExcludedCounts(infeasible=0, objective_mismatch=0, runtime_error=0),
        ),
        by_problem_solver=groups,
    )


def _problem_group(*, problem_id: str, pdev: float, valid_run_count: int = 2) -> ProblemSolverSummary:
    avg_objective = 100 - pdev
    return ProblemSolverSummary(
        problem_type="mkp",
        dataset="DATA",
        encoding="binary",
        direction="max",
        problem_id=problem_id,
        run_count=2,
        valid_run_count=valid_run_count,
        feasible_rate=1.0,
        avg_runtime=0.1,
        avg_evaluation_count=10.0,
        best_known=100,
        avg_objective=avg_objective,
        std_objective=0.0,
        best_objective=avg_objective,
        worst_objective=avg_objective,
        pdev=pdev,
        excluded_counts=ExcludedCounts(infeasible=0, objective_mismatch=0, runtime_error=0),
        best_known_reached_count=0,
        best_known_gap_min=pdev,
        best_known_gap_avg=pdev,
    )


def _cfg(*, tolerance: float = 0.005, alpha: float = 0.5) -> ExperimentConfig:
    return ExperimentConfig(
        experiment_name="eval_test",
        seed_range=(1, 1),
        collects=1,
        solver_ids=("transfer_solver", "isma_solver", "isca_solver", "hsmsca_solver", "competitor_solver"),
        repeat=2,
        dataset_settings=(DatasetSetting("ds1", "DATA", ("p1", "p2"), "mkp"),),
        stages=(
            ExperimentStage(
                "transfer",
                (
                    ExperimentVariant("transfer_s", "transfer_solver", 0, "HSMSCA", "transfer", "S"),
                    ExperimentVariant("transfer_u", "transfer_solver", 0, "HSMSCA", "transfer", "U"),
                    ExperimentVariant("transfer_v", "transfer_solver", 0, "HSMSCA", "transfer", "V"),
                ),
            ),
            ExperimentStage(
                "param",
                (
                    ExperimentVariant("isma_target", "isma_solver", 0, "ISMA", "param"),
                    ExperimentVariant("isma_other", "isma_solver", 0, "ISMA", "param"),
                    ExperimentVariant("isca_target", "isca_solver", 0, "ISCA", "param"),
                    ExperimentVariant("hsmsca_target", "hsmsca_solver", 0, "HSMSCA", "param"),
                ),
            ),
            ExperimentStage(
                "final",
                (
                    ExperimentVariant("final_hsmsca", "hsmsca_solver", 0, "HSMSCA", "final"),
                    ExperimentVariant("final_isma", "isma_solver", 0, "ISMA", "final"),
                ),
            ),
        ),
        evaluation=EvaluationSetting(
            pdev_tolerance=tolerance,
            alpha=alpha,
            target_algorithm="HSMSCA",
        ),
        static_baselines=(
            StaticBaseline(
                combo_id="static_hlms",
                algorithm="HLMS",
                results=(
                    StaticBaselineResult("DATA", "p1", "mkp", "max", avg=96, best=100, pdev=4),
                    StaticBaselineResult("DATA", "p2", "mkp", "max", avg=96, best=100, pdev=4),
                ),
            ),
        ),
    )


def _strict_pass_summaries() -> tuple[StageSummary, ...]:
    return (
        _variant(
            stage="transfer",
            combo_id="transfer_s",
            algorithm="HSMSCA",
            solver_id="transfer_solver",
            params={"ctf": "sigmoid"},
            transfer_type="S",
            pdevs=(2.0, 2.0),
        ),
        _variant(
            stage="transfer",
            combo_id="transfer_u",
            algorithm="HSMSCA",
            solver_id="transfer_solver",
            params={"ctf": "u_shape"},
            transfer_type="U",
            pdevs=(3.0, 3.0),
        ),
        _variant(
            stage="transfer",
            combo_id="transfer_v",
            algorithm="HSMSCA",
            solver_id="transfer_solver",
            params={"ctf": "v_shape"},
            transfer_type="V",
            pdevs=(1.0, 1.0),
        ),
        _variant(
            stage="param",
            combo_id="isma_target",
            algorithm="ISMA",
            solver_id="isma_solver",
            params={"z": 0.08},
            pdevs=(1.0, 1.0),
        ),
        _variant(
            stage="param",
            combo_id="isma_other",
            algorithm="ISMA",
            solver_id="isma_solver",
            params={"z": 0.03},
            pdevs=(2.0, 2.0),
        ),
        _variant(
            stage="param",
            combo_id="isca_target",
            algorithm="ISCA",
            solver_id="isca_solver",
            params={"a": 1.5},
            pdevs=(1.0, 1.0),
        ),
        _variant(
            stage="param",
            combo_id="hsmsca_target",
            algorithm="HSMSCA",
            solver_id="hsmsca_solver",
            params={"z": 0.08, "a": 2.5},
            pdevs=(1.0, 1.0),
        ),
        _variant(
            stage="final",
            combo_id="final_hsmsca",
            algorithm="HSMSCA",
            solver_id="hsmsca_solver",
            params={"z": 0.08, "a": 2.5},
            pdevs=(1.0, 1.0),
        ),
        _variant(
            stage="final",
            combo_id="final_isma",
            algorithm="ISMA",
            solver_id="isma_solver",
            params={"z": 0.08},
            pdevs=(3.0, 3.0),
        ),
    )


def test_literature_evaluator_strict_pass_with_static_baseline_and_wilcoxon() -> None:
    report = literature_mkp_evaluator(_cfg(), 7, _strict_pass_summaries())

    assert report.verdict == STRICT_PASS
    assert {check.name: check.verdict for check in report.checks}["transfer"] == STRICT_PASS
    assert {check.name: check.verdict for check in report.checks}["param"] == STRICT_PASS
    assert {check.name: check.verdict for check in report.checks}["final"] == STRICT_PASS
    assert {check.name: check.verdict for check in report.checks}["wilcoxon"] == STRICT_PASS
    assert report.best_transfer["V"]["combo_id"] == "transfer_v"
    assert report.final_all_level_metrics["target_combo_id"] == "final_hsmsca"
    assert "static_hlms" in report.wilcoxon["competitors"]
    assert any(metric.combo_id == "static_hlms" for metric in report.combo_metrics)


def test_literature_evaluator_validity_fail() -> None:
    summaries = list(_strict_pass_summaries())
    summaries[0] = _variant(
        stage="transfer",
        combo_id="transfer_s",
        algorithm="HSMSCA",
        solver_id="transfer_solver",
        params={"ctf": "sigmoid"},
        transfer_type="S",
        pdevs=(2.0, 2.0),
        valid_run_count=1,
    )

    report = literature_mkp_evaluator(_cfg(), 7, tuple(summaries))

    assert report.verdict == FAIL
    assert {check.name: check.verdict for check in report.checks}["validity"] == FAIL


def test_literature_evaluator_transfer_soft_pass() -> None:
    cfg = _cfg(tolerance=0.01)
    summaries = list(_strict_pass_summaries())
    summaries[0] = _variant(
        stage="transfer",
        combo_id="transfer_s",
        algorithm="HSMSCA",
        solver_id="transfer_solver",
        params={"ctf": "sigmoid"},
        transfer_type="S",
        pdevs=(1.0, 1.0),
    )
    summaries[2] = _variant(
        stage="transfer",
        combo_id="transfer_v",
        algorithm="HSMSCA",
        solver_id="transfer_solver",
        params={"ctf": "v_shape"},
        transfer_type="V",
        pdevs=(1.005, 1.005),
    )

    report = literature_mkp_evaluator(cfg, 7, tuple(summaries))

    assert {check.name: check.verdict for check in report.checks}["transfer"] == SOFT_PASS


def test_literature_evaluator_param_fail_when_target_not_near_best() -> None:
    summaries = list(_strict_pass_summaries())
    summaries[3] = _variant(
        stage="param",
        combo_id="isma_target",
        algorithm="ISMA",
        solver_id="isma_solver",
        params={"z": 0.08},
        pdevs=(5.0, 5.0),
    )

    report = literature_mkp_evaluator(_cfg(), 7, tuple(summaries))

    assert report.verdict == FAIL
    assert {check.name: check.verdict for check in report.checks}["param"] == FAIL
