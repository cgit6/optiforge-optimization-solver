from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from .config import DatasetSetting, EvaluationSpec, ProblemSetting
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
class RoundEvalInput:
    dataset_setting: DatasetSetting
    problem_setting: ProblemSetting
    problem_id: str
    repeat_index: int
    evaluation: EvaluationSpec
    evaluation_name: str
    variant_summaries: tuple[VariantSummary, ...]
    simulator_result: SimulatorResult
    collected_result: SimulatorResult
    candidate_result: SimulatorResult
    projected_result: SimulatorResult

    def __post_init__(self) -> None:
        if not self.problem_id.strip():
            raise ValueError("problem_id cannot be empty.")
        if self.repeat_index < 0:
            raise ValueError("repeat_index must be >= 0.")
        if not self.evaluation_name.strip():
            raise ValueError("evaluation_name cannot be empty.")
        if self.evaluation_name != self.evaluation.name:
            raise ValueError("evaluation_name must match evaluation.name.")
        if not self.variant_summaries:
            raise ValueError("variant_summaries cannot be empty.")


@dataclass(frozen=True)
class RoundEvalDecision:
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


RoundEvaluator = Callable[[RoundEvalInput], RoundEvalDecision]

# Backward-compatible names with the new single-round semantics.
DatasetEvalInput = RoundEvalInput
DatasetEvalDecision = RoundEvalDecision
DatasetEvaluator = RoundEvaluator
