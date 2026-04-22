from __future__ import annotations

from pathlib import Path

import pytest

from mkp.problem_repository import ProblemRepository


def _write_problem_yaml(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_load_valid_problem_yaml(tmp_path: Path):
    root = tmp_path / "problems"
    problem_file = root / "WEISH" / "weish01.yaml"
    _write_problem_yaml(
        problem_file,
        """
problem_id: weish01
dataset: WEISH
items: 3
dim: 2
best_known: 100
values: [10, 20, 30]
weights:
  - [1, 2]
  - [3, 4]
  - [5, 6]
capacities: [7, 8]
""".strip(),
    )

    repo = ProblemRepository(config_root=root)
    model = repo.load("WEISH", "weish01")

    assert model.problem_id == "weish01"
    assert model.dataset == "WEISH"
    assert model.items == 3
    assert model.dim == 2


@pytest.mark.parametrize("missing_field", ["values", "weights", "capacities"])
def test_load_missing_required_fields(tmp_path: Path, missing_field: str):
    root = tmp_path / "problems"
    lines = {
        "problem_id": "problem_id: weish01",
        "dataset": "dataset: WEISH",
        "items": "items: 3",
        "dim": "dim: 2",
        "best_known": "best_known: 100",
        "values": "values: [10, 20, 30]",
        "weights": "weights:\n  - [1, 2]\n  - [3, 4]\n  - [5, 6]",
        "capacities": "capacities: [7, 8]",
    }
    del lines[missing_field]
    content = "\n".join(lines.values())
    _write_problem_yaml(root / "WEISH" / "weish01.yaml", content)

    repo = ProblemRepository(config_root=root)
    with pytest.raises(ValueError, match="Missing required field"):
        repo.load("WEISH", "weish01")


@pytest.mark.parametrize(
    "content, error_match",
    [
        (
            """
problem_id: weish01
dataset: WEISH
items: 3
dim: 2
best_known: 100
values: [10, 20]
weights:
  - [1, 2]
  - [3, 4]
  - [5, 6]
capacities: [7, 8]
""",
            "len\\(values\\) must equal items",
        ),
        (
            """
problem_id: weish01
dataset: WEISH
items: 3
dim: 2
best_known: 100
values: [10, 20, 30]
weights:
  - [1, 2]
  - [3, 4]
capacities: [7, 8]
""",
            "weights shape must be \\(items, dim\\)",
        ),
        (
            """
problem_id: weish01
dataset: WEISH
items: 3
dim: 2
best_known: 100
values: [10, 20, 30]
weights:
  - [1, 2]
  - [3, 4]
  - [5, 6]
capacities: [7]
""",
            "len\\(capacities\\) must equal dim",
        ),
    ],
)
def test_load_dimension_mismatch(tmp_path: Path, content: str, error_match: str):
    root = tmp_path / "problems"
    _write_problem_yaml(root / "WEISH" / "weish01.yaml", content.strip())

    repo = ProblemRepository(config_root=root)
    with pytest.raises(ValueError, match=error_match):
        repo.load("WEISH", "weish01")


def test_load_best_known_null_fail_fast(tmp_path: Path):
    root = tmp_path / "problems"
    _write_problem_yaml(
        root / "WEISH" / "weish01.yaml",
        """
problem_id: weish01
dataset: WEISH
items: 3
dim: 2
best_known: null
values: [10, 20, 30]
weights:
  - [1, 2]
  - [3, 4]
  - [5, 6]
capacities: [7, 8]
""".strip(),
    )

    repo = ProblemRepository(config_root=root)
    with pytest.raises(ValueError, match="best_known cannot be null"):
        repo.load("WEISH", "weish01")


def test_load_hits_cache_on_second_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = tmp_path / "problems"
    _write_problem_yaml(
        root / "WEISH" / "weish01.yaml",
        """
problem_id: weish01
dataset: WEISH
items: 3
dim: 2
best_known: 100
values: [10, 20, 30]
weights:
  - [1, 2]
  - [3, 4]
  - [5, 6]
capacities: [7, 8]
""".strip(),
    )

    repo = ProblemRepository(config_root=root)
    call_count = {"n": 0}
    original_read_yaml = repo._read_yaml

    def counting_read_yaml(path: Path):
        call_count["n"] += 1
        return original_read_yaml(path)

    monkeypatch.setattr(repo, "_read_yaml", counting_read_yaml)

    first = repo.load("WEISH", "weish01")
    second = repo.load("WEISH", "weish01")

    assert call_count["n"] == 1
    assert first is second

