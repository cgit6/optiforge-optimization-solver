from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from .config import DatasetSetting
from ..simulator.core import SimulatorResult
from ..tools.stat import SummaryReport


DatasetVerdict = Literal["STRICT_PASS", "SOFT_PASS", "FAIL"]
STRICT_PASS: DatasetVerdict = "STRICT_PASS"
SOFT_PASS: DatasetVerdict = "SOFT_PASS"
FAIL: DatasetVerdict = "FAIL"
PASS: DatasetVerdict = STRICT_PASS


@dataclass(frozen=True)
class VariantSummary:
    solver_id: str
    param_set_index: int
    params: dict[str, Any]
    summary: SummaryReport

    def __post_init__(self) -> None:
        if not self.solver_id.strip():
            raise ValueError("solver_id cannot be empty.")
        if self.param_set_index < 0:
            raise ValueError("param_set_index must be >= 0.")
        object.__setattr__(self, "params", dict(self.params))


@dataclass(frozen=True)
class DatasetRunResult:
    seed: int
    dataset_setting: DatasetSetting
    simulator_result: SimulatorResult
    variant_summaries: tuple[VariantSummary, ...]

    def __post_init__(self) -> None:
        if self.seed < 0:
            raise ValueError("seed must be >= 0.")
        if not self.variant_summaries:
            raise ValueError("variant_summaries cannot be empty.")


@dataclass(frozen=True)
class DatasetEvalInput:
    seed: int
    dataset_setting: DatasetSetting
    evaluation_name: str
    evaluation_config: dict[str, Any]
    variant_summaries: tuple[VariantSummary, ...]
    simulator_result: SimulatorResult

    def __post_init__(self) -> None:
        if self.seed < 0:
            raise ValueError("seed must be >= 0.")
        if not self.evaluation_name.strip():
            raise ValueError("evaluation_name cannot be empty.")
        if not isinstance(self.evaluation_config, dict):
            raise ValueError("evaluation_config must be a mapping.")
        if not self.variant_summaries:
            raise ValueError("variant_summaries cannot be empty.")
        object.__setattr__(self, "evaluation_config", dict(self.evaluation_config))


@dataclass(frozen=True)
class PaperSetRunResult:
    seed: int
    paper_set: str
    dataset_settings: tuple[DatasetSetting, ...]
    dataset_results: tuple[DatasetRunResult, ...]
    variant_summaries: tuple[VariantSummary, ...]

    def __post_init__(self) -> None:
        if self.seed < 0:
            raise ValueError("seed must be >= 0.")
        if not self.paper_set.strip():
            raise ValueError("paper_set cannot be empty.")
        if not self.dataset_settings:
            raise ValueError("dataset_settings cannot be empty.")
        if not self.dataset_results:
            raise ValueError("dataset_results cannot be empty.")
        if not self.variant_summaries:
            raise ValueError("variant_summaries cannot be empty.")


@dataclass(frozen=True)
class PaperSetEvalInput:
    seed: int
    paper_set: str
    dataset_settings: tuple[DatasetSetting, ...]
    evaluation_name: str
    evaluation_config: dict[str, Any]
    variant_summaries: tuple[VariantSummary, ...]
    dataset_results: tuple[DatasetRunResult, ...]

    def __post_init__(self) -> None:
        if self.seed < 0:
            raise ValueError("seed must be >= 0.")
        if not self.paper_set.strip():
            raise ValueError("paper_set cannot be empty.")
        if not self.dataset_settings:
            raise ValueError("dataset_settings cannot be empty.")
        if not self.evaluation_name.strip():
            raise ValueError("evaluation_name cannot be empty.")
        if not isinstance(self.evaluation_config, dict):
            raise ValueError("evaluation_config must be a mapping.")
        if not self.variant_summaries:
            raise ValueError("variant_summaries cannot be empty.")
        if not self.dataset_results:
            raise ValueError("dataset_results cannot be empty.")
        object.__setattr__(self, "evaluation_config", dict(self.evaluation_config))


@dataclass(frozen=True)
class DatasetEvalDecision:
    passed: bool
    verdict: DatasetVerdict
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.verdict not in {STRICT_PASS, SOFT_PASS, FAIL}:
            raise ValueError(f"unsupported verdict: {self.verdict!r}")
        if self.passed != (self.verdict != FAIL):
            raise ValueError("passed must match verdict.")
        object.__setattr__(self, "details", dict(self.details))

    @property
    def is_strict(self) -> bool:
        return self.verdict == STRICT_PASS


@dataclass(frozen=True)
class PaperSetDecisionRecord:
    paper_set: str
    dataset_settings: tuple[DatasetSetting, ...]
    decision: DatasetEvalDecision

    def __post_init__(self) -> None:
        if not self.paper_set.strip():
            raise ValueError("paper_set cannot be empty.")
        if not self.dataset_settings:
            raise ValueError("dataset_settings cannot be empty.")


@dataclass(frozen=True)
class ExperimentEvalInput:
    seed: int
    evaluation_name: str
    evaluation_config: dict[str, Any]
    variant_summaries: tuple[VariantSummary, ...]
    dataset_results: tuple[DatasetRunResult, ...]
    paper_set_evaluations: tuple[PaperSetDecisionRecord, ...]

    def __post_init__(self) -> None:
        if self.seed < 0:
            raise ValueError("seed must be >= 0.")
        if not self.evaluation_name.strip():
            raise ValueError("evaluation_name cannot be empty.")
        if not isinstance(self.evaluation_config, dict):
            raise ValueError("evaluation_config must be a mapping.")
        if not self.variant_summaries:
            raise ValueError("variant_summaries cannot be empty.")
        if not self.dataset_results:
            raise ValueError("dataset_results cannot be empty.")
        if not self.paper_set_evaluations:
            raise ValueError("paper_set_evaluations cannot be empty.")
        object.__setattr__(self, "evaluation_config", dict(self.evaluation_config))


DatasetEvaluator = Callable[[DatasetEvalInput], DatasetEvalDecision]
PaperSetEvaluator = Callable[[PaperSetEvalInput], DatasetEvalDecision]
ExperimentEvaluator = Callable[[ExperimentEvalInput], DatasetEvalDecision]
