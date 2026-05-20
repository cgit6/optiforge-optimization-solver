"""Experiment domain package: generic config, evaluation, and seed-search execution."""

from __future__ import annotations

from .config import DatasetSetting, EvaluationBaseline, EvaluationSpec, ExperimentConfig, load_config
from .evaluation import (
    DatasetEvalDecision,
    DatasetEvalInput,
    DatasetEvaluator,
    DatasetRunResult,
    DatasetVerdict,
    FAIL,
    PASS,
    VariantSummary,
)
from .experiment import (
    CollectedSeed,
    DatasetEvaluationRecord,
    Experiment,
    ExperimentReport,
    SeedAttempt,
    build,
    executeExperiment,
)

__all__ = [
    "CollectedSeed",
    "DatasetEvalDecision",
    "DatasetEvalInput",
    "DatasetEvaluationRecord",
    "DatasetEvaluator",
    "DatasetRunResult",
    "DatasetSetting",
    "DatasetVerdict",
    "EvaluationBaseline",
    "EvaluationSpec",
    "Experiment",
    "ExperimentConfig",
    "ExperimentReport",
    "FAIL",
    "PASS",
    "SeedAttempt",
    "VariantSummary",
    "build",
    "executeExperiment",
    "load_config",
]
