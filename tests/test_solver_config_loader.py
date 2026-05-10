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
capabilities:
  problem_types: [mkp]
  encodings: [binary]
  directions: [max]
stop_condition:
  type: max_iterations
  max_iterations: 10
  max_seconds: null
params:
  - {}
""".strip(),
    )
    loader = SolverConfigLoader(config_root=root)
    config = loader.load("stub_solver", param_set_index=0)

    assert config["solver_id"] == "stub_solver"
    assert config["stop_condition"]["type"] == "max_iterations"
    assert config["params"] == {}
    assert config["param_set_index"] == 0


def test_load_selects_requested_param_set(tmp_path: Path) -> None:
    root = tmp_path / "solvers"
    _write_solver_yaml(
        root / "stub_solver.yaml",
        """
solver_id: stub_solver
solver_class: StubMaxIterationsSolver
capabilities:
  problem_types: [mkp]
  encodings: [binary]
  directions: [max]
stop_condition:
  type: max_iterations
  max_iterations: 10
  max_seconds: null
params:
  - {pop_size: 20, z: 0.08}
  - {pop_size: 30, z: 0.03, ctf: sigmoid_s0}
""".strip(),
    )
    loader = SolverConfigLoader(config_root=root)

    config = loader.load("stub_solver", param_set_index=1)

    assert config["params"] == {"pop_size": 30, "z": 0.03, "ctf": "sigmoid_s0"}
    assert config["param_set_index"] == 1


def test_load_all_returns_each_param_set(tmp_path: Path) -> None:
    root = tmp_path / "solvers"
    _write_solver_yaml(
        root / "stub_solver.yaml",
        """
solver_id: stub_solver
solver_class: StubMaxIterationsSolver
capabilities:
  problem_types: [mkp]
  encodings: [binary]
  directions: [max]
stop_condition:
  type: max_iterations
  max_iterations: 10
  max_seconds: null
params:
  - {pop_size: 20, z: 0.08}
  - {pop_size: 30, z: 0.03}
""".strip(),
    )
    loader = SolverConfigLoader(config_root=root)

    configs = loader.load_all("stub_solver")

    assert [config["param_set_index"] for config in configs] == [0, 1]
    assert [config["params"] for config in configs] == [
        {"pop_size": 20, "z": 0.08},
        {"pop_size": 30, "z": 0.03},
    ]


def test_solver_id_must_match_file_name(tmp_path: Path):
    root = tmp_path / "solvers"
    _write_solver_yaml(
        root / "stub_solver.yaml",
        """
solver_id: other_solver
solver_class: StubMaxIterationsSolver
capabilities:
  problem_types: [mkp]
  encodings: [binary]
  directions: [max]
stop_condition:
  type: max_iterations
  max_iterations: 10
params:
  - {}
""".strip(),
    )
    loader = SolverConfigLoader(config_root=root)

    with pytest.raises(ValueError, match="solver_id mismatch"):
        loader.load("stub_solver", param_set_index=0)


def test_stop_condition_type_validation(tmp_path: Path):
    root = tmp_path / "solvers"
    _write_solver_yaml(
        root / "stub_solver.yaml",
        """
solver_id: stub_solver
solver_class: StubMaxIterationsSolver
capabilities:
  problem_types: [mkp]
  encodings: [binary]
  directions: [max]
stop_condition:
  type: unsupported
  max_iterations: 10
params:
  - {}
""".strip(),
    )
    loader = SolverConfigLoader(config_root=root)

    with pytest.raises(ValueError, match="stop_condition.type"):
        loader.load("stub_solver", param_set_index=0)


def test_missing_capabilities_rejected(tmp_path: Path) -> None:
    root = tmp_path / "solvers"
    _write_solver_yaml(
        root / "stub_solver.yaml",
        """
solver_id: stub_solver
solver_class: StubMaxIterationsSolver
stop_condition:
  type: max_iterations
  max_iterations: 10
params:
  - {}
""".strip(),
    )
    loader = SolverConfigLoader(config_root=root)

    with pytest.raises(ValueError, match="Missing required field"):
        loader.load("stub_solver", param_set_index=0)


@pytest.mark.parametrize(
    "content, error_match",
    [
        (
            """
solver_id: stub_solver
solver_class: StubMaxIterationsSolver
capabilities:
  problem_types: [mkp]
  encodings: [binary]
  directions: [max]
stop_condition:
  type: max_iterations
  max_iterations: 0
params:
  - {}
""",
            "max_iterations must be > 0",
        ),
        (
            """
solver_id: stub_solver
solver_class: StubMaxIterationsSolver
capabilities:
  problem_types: [mkp]
  encodings: [binary]
  directions: [max]
stop_condition:
  type: max_seconds
  max_seconds: 0
params:
  - {}
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
        loader.load("stub_solver", param_set_index=0)


@pytest.mark.parametrize(
    "content, error_match",
    [
        (
            """
solver_id: stub_solver
solver_class: StubMaxIterationsSolver
capabilities:
  problem_types: [mkp]
  encodings: [binary]
  directions: [max]
stop_condition:
  type: max_iterations
  max_iterations: 10
params: {}
""",
            "params must be a non-empty list",
        ),
        (
            """
solver_id: stub_solver
solver_class: StubMaxIterationsSolver
capabilities:
  problem_types: [mkp]
  encodings: [binary]
  directions: [max]
stop_condition:
  type: max_iterations
  max_iterations: 10
params: []
""",
            "params must be a non-empty list",
        ),
        (
            """
solver_id: stub_solver
solver_class: StubMaxIterationsSolver
capabilities:
  problem_types: [mkp]
  encodings: [binary]
  directions: [max]
stop_condition:
  type: max_iterations
  max_iterations: 10
params:
  - {}
  - 123
""",
            "params\\[1\\] must be a mapping",
        ),
    ],
)
def test_params_schema_validation(tmp_path: Path, content: str, error_match: str) -> None:
    root = tmp_path / "solvers"
    _write_solver_yaml(root / "stub_solver.yaml", content.strip())
    loader = SolverConfigLoader(config_root=root)

    with pytest.raises(ValueError, match=error_match):
        loader.load("stub_solver", param_set_index=0)


def test_param_set_index_range_validation(tmp_path: Path) -> None:
    root = tmp_path / "solvers"
    _write_solver_yaml(
        root / "stub_solver.yaml",
        """
solver_id: stub_solver
solver_class: StubMaxIterationsSolver
capabilities:
  problem_types: [mkp]
  encodings: [binary]
  directions: [max]
stop_condition:
  type: max_iterations
  max_iterations: 10
params:
  - {}
""".strip(),
    )
    loader = SolverConfigLoader(config_root=root)

    with pytest.raises(ValueError, match="param_set_index out of range"):
        loader.load("stub_solver", param_set_index=1)


def test_concurrent_solver_config_loads(tmp_path: Path) -> None:
    root = tmp_path / "solvers"
    _write_solver_yaml(
        root / "stub_solver.yaml",
        """
solver_id: stub_solver
solver_class: StubMaxIterationsSolver
capabilities:
  problem_types: [mkp]
  encodings: [binary]
  directions: [max]
stop_condition:
  type: max_iterations
  max_iterations: 10
params:
  - {}
""".strip(),
    )
    loader = SolverConfigLoader(config_root=root)

    def _load(_: int) -> str:
        return loader.load("stub_solver", param_set_index=0)["solver_id"]

    with ThreadPoolExecutor(16) as pool:
        ids = list(pool.map(_load, range(32)))

    assert ids == ["stub_solver"] * 32
