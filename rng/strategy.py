from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .context import SeedContext
from .seeding import stable_task_seed, validate_base_seed


class SeedStrategy(Protocol):
    def build_task_seed(
        self,
        context: SeedContext,
        *,
        base_seed: int,
        problem_id: str,
        repeat_index: int,
    ) -> int:
        """Build one task seed for a specific (problem_id, repeat_index)."""

    def build_task_seeds(
        self,
        context: SeedContext,
        *,
        base_seed: int,
    ) -> dict[tuple[str, int], int]:
        """Build task seeds keyed by (problem_id, repeat_index)."""


@dataclass(frozen=True)
class DerivedPerProblemSeedStrategy:
    """Derive stable task seeds from problem identity and repeat index."""

    def build_task_seeds(
        self,
        context: SeedContext,
        *,
        base_seed: int,
    ) -> dict[tuple[str, int], int]:
        base_seed = validate_base_seed(base_seed)
        task_seeds: dict[tuple[str, int], int] = {}
        for problem_id in context.problem_ids:
            for repeat_index in range(context.repeat):
                task_seeds[(problem_id, repeat_index)] = stable_task_seed(
                    base_seed=base_seed,
                    problem_type=context.problem_type,
                    dataset=context.dataset,
                    problem_id=problem_id,
                    repeat_index=repeat_index,
                )
        return task_seeds

    def build_task_seed(
        self,
        context: SeedContext,
        *,
        base_seed: int,
        problem_id: str,
        repeat_index: int,
    ) -> int:
        base_seed = validate_base_seed(base_seed)
        if problem_id not in context.problem_ids:
            raise ValueError(f"problem_id is not in context.problem_ids: {problem_id!r}")
        if repeat_index < 0 or repeat_index >= context.repeat:
            raise ValueError(f"repeat_index out of range: {repeat_index!r}")
        return stable_task_seed(
            base_seed=base_seed,
            problem_type=context.problem_type,
            dataset=context.dataset,
            problem_id=problem_id,
            repeat_index=repeat_index,
        )


@dataclass(frozen=True)
class SharedRepeatSeedListStrategy:
    """Reuse the same repeat-index seed list for every problem in the dataset."""

    seeds: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.seeds:
            raise ValueError("seeds cannot be empty.")
        object.__setattr__(
            self,
            "seeds",
            tuple(validate_base_seed(seed) for seed in self.seeds),
        )

    def build_task_seeds(
        self,
        context: SeedContext,
        *,
        base_seed: int,
    ) -> dict[tuple[str, int], int]:
        validate_base_seed(base_seed)
        if len(self.seeds) != context.repeat:
            raise ValueError(
                "shared repeat seed list length must equal context.repeat: "
                f"{len(self.seeds)} != {context.repeat}."
            )

        task_seeds: dict[tuple[str, int], int] = {}
        for problem_id in context.problem_ids:
            for repeat_index, seed in enumerate(self.seeds):
                task_seeds[(problem_id, repeat_index)] = seed
        return task_seeds

    def build_task_seed(
        self,
        context: SeedContext,
        *,
        base_seed: int,
        problem_id: str,
        repeat_index: int,
    ) -> int:
        validate_base_seed(base_seed)
        if problem_id not in context.problem_ids:
            raise ValueError(f"problem_id is not in context.problem_ids: {problem_id!r}")
        if repeat_index < 0 or repeat_index >= context.repeat:
            raise ValueError(f"repeat_index out of range: {repeat_index!r}")
        if len(self.seeds) != context.repeat:
            raise ValueError(
                "shared repeat seed list length must equal context.repeat: "
                f"{len(self.seeds)} != {context.repeat}."
            )
        return self.seeds[repeat_index]
