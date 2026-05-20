"""Optimization problem definitions and registration helpers."""

from __future__ import annotations

from .builders import buildProblemRegistry, problemBuilders
from .interface import Direction, Problem
from .mkp import MKPProblem
from .registry import ProblemRegistry, ProblemTypeSpec
from .tsp import TSPProblem
from .validation import DirectionSpec, ObjectiveValue, ScalarObjective, ValidationReport

ProblemModel = MKPProblem

__all__ = [
    "Direction",
    "DirectionSpec",
    "ObjectiveValue",
    "ScalarObjective",
    "Problem",
    "ProblemModel",
    "MKPProblem",
    "TSPProblem",
    "ProblemRegistry",
    "ProblemTypeSpec",
    "ValidationReport",
    "problemBuilders",
    "buildProblemRegistry",
]
