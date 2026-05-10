"""Experiment domain package: config parsing, evaluation, and experiment execution."""

from __future__ import annotations

from .config import (
    BaselineEntry,
    DatasetSetting,
    EvaluationSetting,
    ExperimentConfig,
    ExperimentStage,
    ExperimentVariant,
    StaticBaseline,
    StaticBaselineResult,
    load_config,
)
from .evaluation import (
    FAIL,
    PASSING_VERDICTS,
    SOFT_PASS,
    STRICT_PASS,
    CheckResult,
    ComboMetric,
    EvaluationReport,
    ProblemMetric,
    StageSummary,
    literature_mkp_evaluator,
)
from .experiment import CollectedSeed, Experiment, ExperimentReport, SeedAttempt, build, executeExperiment

__all__ = [
    "BaselineEntry",
    "CheckResult",
    "CollectedSeed",
    "ComboMetric",
    "DatasetSetting",
    "EvaluationReport",
    "EvaluationSetting",
    "Experiment",
    "ExperimentConfig",
    "ExperimentReport",
    "ExperimentStage",
    "ExperimentVariant",
    "FAIL",
    "PASSING_VERDICTS",
    "ProblemMetric",
    "SOFT_PASS",
    "STRICT_PASS",
    "SeedAttempt",
    "StageSummary",
    "StaticBaseline",
    "StaticBaselineResult",
    "build",
    "executeExperiment",
    "literature_mkp_evaluator",
    "load_config",
]
