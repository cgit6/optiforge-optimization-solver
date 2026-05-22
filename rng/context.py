from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SeedContext:
    problem_type: str
    dataset: str
    problem_ids: tuple[str, ...]
    repeat: int

    def __post_init__(self) -> None:
        if not self.problem_type.strip():
            raise ValueError("problem_type cannot be empty.")
        if not self.dataset.strip():
            raise ValueError("dataset cannot be empty.")
        if not self.problem_ids:
            raise ValueError("problem_ids cannot be empty.")
        if any(not problem_id.strip() for problem_id in self.problem_ids):
            raise ValueError("problem_ids cannot contain empty value.")
        if self.repeat <= 0:
            raise ValueError("repeat must be > 0.")
