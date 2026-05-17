from __future__ import annotations

from .mkp import mkpProblemSpec
from .registry import ProblemRegistry, ProblemTypeSpec
from .tsp import tspProblemSpec


def problemBuilders() -> dict[str, ProblemTypeSpec]:
    """Built-in optimization problem definitions."""
    return {
        "mkp": mkpProblemSpec(),
        "tsp": tspProblemSpec(),
    }


def buildProblemRegistry(builders: dict[str, ProblemTypeSpec] | None = None) -> ProblemRegistry:
    registry = ProblemRegistry()
    for problem_type, spec in (builders or problemBuilders()).items():
        if problem_type != spec.problem_type:
            raise ValueError(f"Problem builder key mismatch: {problem_type!r} != {spec.problem_type!r}")
        registry.register(spec)
    return registry
