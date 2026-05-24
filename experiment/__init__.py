"""Experiment domain package: streaming round collection execution."""

from __future__ import annotations

from .config import (
    DEFAULT_WORKER_COUNT,
    DatasetSetting,
    EvaluationBaseline,
    EvaluationSpec,
    ExperimentConfig,
    ProblemSetting,
    SolverSelection,
    load_config,
)
from .evaluation import (
    DatasetEvalDecision,
    DatasetEvalInput,
    DatasetEvaluator,
    DatasetVerdict,
    FAIL,
    PASS,
    RoundEvalDecision,
    RoundEvalInput,
    RoundEvaluator,
    VariantSummary,
)
from .experiment import (
    Experiment,
    ExperimentReport,
    ProblemCollectionReport,
    build,
    executeExperiment,
    register,
)

__all__ = [
    "DEFAULT_WORKER_COUNT",
    "DatasetEvalDecision",
    "DatasetEvalInput",
    "DatasetEvaluator",
    "DatasetSetting",
    "DatasetVerdict",
    "EvaluationBaseline",
    "EvaluationSpec",
    "Experiment",
    "ExperimentConfig",
    "ExperimentReport",
    "FAIL",
    "PASS",
    "ProblemSetting",
    "ProblemCollectionReport",
    "RoundEvalDecision",
    "RoundEvalInput",
    "RoundEvaluator",
    "SolverSelection",
    "VariantSummary",
    "build",
    "executeExperiment",
    "load_config",
    "register",
]
