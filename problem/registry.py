from __future__ import annotations

from dataclasses import dataclass
from multiprocessing.shared_memory import SharedMemory
from pathlib import Path
from typing import Any, Callable, Protocol

from .interface import Problem
from .validation import DirectionSpec, normalize_direction_spec


class ProblemShmPack(Protocol):
    problem_type: str
    dataset: str
    problem_id: str


ProblemLoader = Callable[[dict[str, Any], str, str, Path], Problem]
ProblemShmPacker = Callable[[Problem, list[SharedMemory]], ProblemShmPack]
ProblemShmAttacher = Callable[[ProblemShmPack, list[SharedMemory]], Problem]


@dataclass(frozen=True)
class ProblemTypeSpec:
    problem_type: str
    encoding: str
    direction: DirectionSpec
    model_type: type[Problem]
    loader: ProblemLoader
    yaml_required_fields: tuple[str, ...]
    make_shm_pack: ProblemShmPacker
    attach_shm_pack: ProblemShmAttacher


class ProblemRegistry:
    """Registry for problem type definitions."""

    def __init__(self) -> None:
        self._specs: dict[str, ProblemTypeSpec] = {}

    def register(self, spec: ProblemTypeSpec) -> None:
        if not spec.problem_type.strip():
            raise ValueError("problem_type cannot be empty.")
        if spec.problem_type in self._specs:
            raise ValueError(f"Problem type already registered: {spec.problem_type}")
        if not issubclass(spec.model_type, Problem):
            raise TypeError(f"model_type must inherit Problem: {spec.model_type!r}")
        object.__setattr__(spec, "direction", normalize_direction_spec(spec.direction))
        self._specs[spec.problem_type] = spec

    def get(self, problem_type: str) -> ProblemTypeSpec:
        try:
            return self._specs[problem_type]
        except KeyError as exc:
            raise KeyError(f"Problem type is not registered: {problem_type}") from exc

    def validate_model(self, model: Problem, problem_type: str) -> None:
        spec = self.get(problem_type)
        if not isinstance(model, Problem):
            raise TypeError(f"Problem loader must return Problem, got {type(model).__name__}")
        if not isinstance(model, spec.model_type):
            raise TypeError(
                f"Problem loader for {problem_type!r} returned {type(model).__name__}, "
                f"expected {spec.model_type.__name__}"
            )
        if model.problem_type != problem_type:
            raise ValueError(f"Loaded problem_type mismatch: expected {problem_type}, got {model.problem_type}")

    def list_problem_types(self) -> tuple[str, ...]:
        return tuple(sorted(self._specs))

    def specs(self) -> tuple[ProblemTypeSpec, ...]:
        return tuple(self._specs[key] for key in sorted(self._specs))


def registryFromSpecs(specs: tuple[ProblemTypeSpec, ...] | list[ProblemTypeSpec]) -> ProblemRegistry:
    registry = ProblemRegistry()
    for spec in specs:
        registry.register(spec)
    return registry
