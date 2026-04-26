from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from mkp.tools.solver_config_loader import SolverConfigLoader


def _write_solver_yaml(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_load_valid_solver_config(tmp_path: Path):
    root = tmp_path / "solvers"
    _write_solver_yaml(
        root / "stub_solver.yaml",
        """
solver_id: stub_solver
solver_class: StubMaxIterationsSolver
stop_condition:
  type: max_iterations
  max_iterations: 10
  max_seconds: null
params: {}
""".strip(),
    )
    loader = SolverConfigLoader(config_root=root)
    config = loader.load("stub_solver")

    assert config["solver_id"] == "stub_solver"
    assert config["stop_condition"]["type"] == "max_iterations"


def test_solver_id_must_match_file_name(tmp_path: Path):
    root = tmp_path / "solvers"
    _write_solver_yaml(
        root / "stub_solver.yaml",
        """
solver_id: other_solver
solver_class: StubMaxIterationsSolver
stop_condition:
  type: max_iterations
  max_iterations: 10
params: {}
""".strip(),
    )
    loader = SolverConfigLoader(config_root=root)

    with pytest.raises(ValueError, match="solver_id mismatch"):
        loader.load("stub_solver")


def test_stop_condition_type_validation(tmp_path: Path):
    root = tmp_path / "solvers"
    _write_solver_yaml(
        root / "stub_solver.yaml",
        """
solver_id: stub_solver
solver_class: StubMaxIterationsSolver
stop_condition:
  type: unsupported
  max_iterations: 10
params: {}
""".strip(),
    )
    loader = SolverConfigLoader(config_root=root)

    with pytest.raises(ValueError, match="stop_condition.type"):
        loader.load("stub_solver")


@pytest.mark.parametrize(
    "content, error_match",
    [
        (
            """
solver_id: stub_solver
solver_class: StubMaxIterationsSolver
stop_condition:
  type: max_iterations
  max_iterations: 0
params: {}
""",
            "max_iterations must be > 0",
        ),
        (
            """
solver_id: stub_solver
solver_class: StubMaxIterationsSolver
stop_condition:
  type: max_seconds
  max_seconds: 0
params: {}
""",
            "max_seconds must be > 0",
        ),
    ],
)
def test_stop_condition_value_validation(tmp_path: Path, content: str, error_match: str):
    root = tmp_path / "solvers"
    _write_solver_yaml(root / "stub_solver.yaml", content.strip())
    loader = SolverConfigLoader(config_root=root)

    with pytest.raises(ValueError, match=error_match):
        loader.load("stub_solver")


def test_concurrent_solver_config_loads(tmp_path: Path) -> None:
    root = tmp_path / "solvers"
    _write_solver_yaml(
        root / "stub_solver.yaml",
        """
solver_id: stub_solver
solver_class: StubMaxIterationsSolver
stop_condition:
  type: max_iterations
  max_iterations: 10
params: {}
""".strip(),
    )
    loader = SolverConfigLoader(config_root=root)

    def _load(_: int) -> str:
        return loader.load("stub_solver")["solver_id"]

    with ThreadPoolExecutor(16) as pool:
        ids = list(pool.map(_load, range(32)))

    assert ids == ["stub_solver"] * 32
