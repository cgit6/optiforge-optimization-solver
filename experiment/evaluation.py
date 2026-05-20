from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from .config import DatasetSetting
from ..simulator.core import SimulatorResult
from ..tools.stat import SummaryReport


DatasetVerdict = Literal["PASS", "FAIL"]
PASS: DatasetVerdict = "PASS"
FAIL: DatasetVerdict = "FAIL"


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
    variant_summaries: tuple[VariantSummary, ...]
    simulator_result: SimulatorResult

    def __post_init__(self) -> None:
        if self.seed < 0:
            raise ValueError("seed must be >= 0.")
        if not self.evaluation_name.strip():
            raise ValueError("evaluation_name cannot be empty.")
        if not self.variant_summaries:
            raise ValueError("variant_summaries cannot be empty.")


@dataclass(frozen=True)
class DatasetEvalDecision:
    passed: bool
    verdict: DatasetVerdict
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.verdict not in {PASS, FAIL}:
            raise ValueError(f"unsupported verdict: {self.verdict!r}")
        if self.passed != (self.verdict == PASS):
            raise ValueError("passed must match verdict.")
        object.__setattr__(self, "details", dict(self.details))


DatasetEvaluator = Callable[[DatasetEvalInput], DatasetEvalDecision]
