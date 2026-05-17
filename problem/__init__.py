"""Optimization problem definitions and registration helpers."""

from __future__ import annotations

from .builders import buildProblemRegistry, problemBuilders
from .interface import Direction, Problem
from .mkp import MKPProblem
from .registry import ProblemRegistry, ProblemTypeSpec
from .tsp import TSPProblem

ProblemModel = MKPProblem

__all__ = [
    "Direction",
    "Problem",
    "ProblemModel",
    "MKPProblem",
    "TSPProblem",
    "ProblemRegistry",
    "ProblemTypeSpec",
    "problemBuilders",
    "buildProblemRegistry",
]
