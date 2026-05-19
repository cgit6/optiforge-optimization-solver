"""Experiment domain package: generic config, evaluation, and seed-search execution."""

from __future__ import annotations

from .config import DatasetSetting, EvaluationSpec, ExperimentConfig, load_config
from .evaluation import (
    DatasetEvalDecision,
    DatasetEvalInput,
    DatasetEvaluator,
    DatasetRunResult,
    DatasetVerdict,
    ExperimentEvalInput,
    ExperimentEvaluator,
    FAIL,
    PASS,
    PaperSetDecisionRecord,
    PaperSetEvalInput,
    PaperSetEvaluator,
    PaperSetRunResult,
    SOFT_PASS,
    STRICT_PASS,
    VariantSummary,
)
from .experiment import (
    CollectedSeed,
    Experiment,
    ExperimentReport,
    GlobalEvaluationRecord,
    PaperSetEvaluationRecord,
    SeedAttempt,
    build,
    executeExperiment,
)

__all__ = [
    "CollectedSeed",
    "DatasetEvalDecision",
    "DatasetEvalInput",
    "DatasetEvaluator",
    "DatasetRunResult",
    "DatasetSetting",
    "DatasetVerdict",
    "EvaluationSpec",
    "Experiment",
    "ExperimentConfig",
    "ExperimentEvalInput",
    "ExperimentEvaluator",
    "ExperimentReport",
    "FAIL",
    "GlobalEvaluationRecord",
    "PASS",
    "PaperSetDecisionRecord",
    "PaperSetEvalInput",
    "PaperSetEvaluationRecord",
    "PaperSetEvaluator",
    "PaperSetRunResult",
    "SeedAttempt",
    "SOFT_PASS",
    "STRICT_PASS",
    "VariantSummary",
    "build",
    "executeExperiment",
    "load_config",
]
