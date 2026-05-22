from __future__ import annotations

from pathlib import Path

import pytest

from mkp.engine import Engine, SimulationBundle
from mkp.engine.models import ExperimentSpec
from mkp.engine.repository import ProblemRepository
from mkp.rng import DerivedPerProblemSeedStrategy, make_numpy_rng
from mkp.tools.show import write_simulator_result


def _write_problem_yaml(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
problem_id: weish01
dataset: WEISH
items: 3
dim: 2
best_known: 50
values: [10, 20, 30]
weights:
  - [2, 1]
  - [3, 2]
  - [4, 3]
capacities: [10, 8]
""".strip(),
        encoding="utf-8",
    )


def _write_solver_yaml(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
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
  - {pop_size: 20}
""".strip(),
        encoding="utf-8",
    )


def test_engine_build_returns_bundle_with_runnable_simulator(tmp_path: Path) -> None:
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    output_root = tmp_path / "output"
    _write_problem_yaml(problem_root / "mkp" / "WEISH" / "weish01.yaml")
    _write_solver_yaml(solver_root / "stub_solver.yaml")

    spec = ExperimentSpec(
        experiment_name="exp_engine_1",
        dataset="WEISH",
        problem_ids=("weish01",),
        solver_ids=("stub_solver",),
        repeat=1,
    )

    bundle = Engine.build(
        spec=spec,
        problem_root=problem_root,
        solver_root=solver_root,
        seed_strategy=DerivedPerProblemSeedStrategy(),
    )

    assert isinstance(bundle, SimulationBundle)
    assert bundle.spec is spec
    assert bundle.catalog_summary is not None
    assert len(bundle.catalog) > 0
    assert "WEISH" in bundle.catalog_summary.datasets
    assert bundle.problem_bank is not None
    assert bundle.solver_configs is not None
    assert bundle.solver_configs.solver_ids() == frozenset(spec.solver_ids)
    assert bundle.solver_configs.param_set_indices("stub_solver") == (0, 1)
    assert bundle.solver_builders
    assert isinstance(bundle.seed_strategy, DerivedPerProblemSeedStrategy)
    assert bundle.rng_factory is make_numpy_rng
    sim = bundle.new_simulator()
    try:
        result = sim.run_sequential(base_seed=7)
        assert len(result.rows) == 2
        write_simulator_result(result, experiment_name="exp_engine_1", output_root=output_root)
        assert (output_root / "exp_engine_1" / "stub_solver" / "param_0" / "runs.csv").exists()
        assert (output_root / "exp_engine_1" / "stub_solver" / "param_1" / "runs.csv").exists()
    finally:
        sim.close()


def test_engine_build_requires_explicit_seed_strategy(tmp_path: Path) -> None:
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    _write_problem_yaml(problem_root / "mkp" / "WEISH" / "weish01.yaml")
    _write_solver_yaml(solver_root / "stub_solver.yaml")

    spec = ExperimentSpec(
        experiment_name="exp_engine_missing_strategy",
        dataset="WEISH",
        problem_ids=("weish01",),
        solver_ids=("stub_solver",),
        repeat=1,
    )

    with pytest.raises(TypeError, match="seed_strategy"):
        Engine.build(
            spec=spec,
            problem_root=problem_root,
            solver_root=solver_root,
        )


def test_engine_build_fails_when_experiment_problem_yaml_is_invalid(tmp_path: Path) -> None:
    """僅本次 spec 指到的題目會被 load 驗證；壞檔必須在 problem_ids 內才會讓 build 失敗。"""
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    _write_problem_yaml(problem_root / "mkp" / "WEISH" / "weish01.yaml")
    (problem_root / "mkp" / "WEISH" / "broken.yaml").write_text("items: not_a_mapping\n", encoding="utf-8")
    _write_solver_yaml(solver_root / "stub_solver.yaml")

    spec = ExperimentSpec(
        experiment_name="exp_bad_cat",
        dataset="WEISH",
        problem_ids=("broken",),
        solver_ids=("stub_solver",),
        repeat=1,
    )

    with pytest.raises((ValueError, FileNotFoundError, TypeError)):
        Engine.build(
            spec=spec,
            problem_root=problem_root,
            solver_root=solver_root,
            seed_strategy=DerivedPerProblemSeedStrategy(),
        )


def test_engine_build_succeeds_when_unused_catalog_yaml_is_invalid(tmp_path: Path) -> None:
    """目錄內其他題目的壞檔不阻擋 build（與舊版「全庫驗證」語意不同）。"""
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    _write_problem_yaml(problem_root / "mkp" / "WEISH" / "weish01.yaml")
    (problem_root / "mkp" / "WEISH" / "broken.yaml").write_text("items: not_a_mapping\n", encoding="utf-8")
    _write_solver_yaml(solver_root / "stub_solver.yaml")

    spec = ExperimentSpec(
        experiment_name="exp_ok_unused_bad",
        dataset="WEISH",
        problem_ids=("weish01",),
        solver_ids=("stub_solver",),
        repeat=1,
    )

    bundle = Engine.build(
        spec=spec,
        problem_root=problem_root,
        solver_root=solver_root,
        seed_strategy=DerivedPerProblemSeedStrategy(),
    )
    try:
        assert bundle.problem_bank.get("WEISH", "weish01").problem_id == "weish01"
    finally:
        bundle.problem_bank.close()


def test_engine_build_fails_when_experiment_problem_has_unknown_best_known(tmp_path: Path) -> None:
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    _write_problem_yaml(problem_root / "mkp" / "WEISH" / "weish01.yaml")
    (problem_root / "mkp" / "WEISH" / "broken.yaml").write_text(
        """
problem_id: broken
dataset: WEISH
items: 3
dim: 2
best_known: null
values: [10, 20, 30]
weights:
  - [2, 1]
  - [3, 2]
  - [4, 3]
capacities: [10, 8]
""".strip(),
        encoding="utf-8",
    )
    _write_solver_yaml(solver_root / "stub_solver.yaml")

    spec = ExperimentSpec(
        experiment_name="exp_unknown_best",
        dataset="WEISH",
        problem_ids=("broken",),
        solver_ids=("stub_solver",),
        repeat=1,
    )

    with pytest.raises(ValueError, match="best_known must be a positive integer"):
        Engine.build(
            spec=spec,
            problem_root=problem_root,
            solver_root=solver_root,
            seed_strategy=DerivedPerProblemSeedStrategy(),
        )


def test_engine_build_fails_when_experiment_problem_not_in_catalog(tmp_path: Path) -> None:
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    _write_problem_yaml(problem_root / "mkp" / "WEISH" / "weish01.yaml")
    _write_solver_yaml(solver_root / "stub_solver.yaml")

    spec = ExperimentSpec(
        experiment_name="exp_missing_pid",
        dataset="WEISH",
        problem_ids=("not_in_folder",),
        solver_ids=("stub_solver",),
        repeat=1,
    )

    with pytest.raises(FileNotFoundError, match="catalog"):
        Engine.build(
            spec=spec,
            problem_root=problem_root,
            solver_root=solver_root,
            seed_strategy=DerivedPerProblemSeedStrategy(),
        )


def test_worker_curriculum_does_not_call_problem_repository_load_after_engine_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    _write_problem_yaml(problem_root / "mkp" / "WEISH" / "weish01.yaml")
    _write_solver_yaml(solver_root / "stub_solver.yaml")

    spec = ExperimentSpec(
        experiment_name="exp_shm",
        dataset="WEISH",
        problem_ids=("weish01",),
        solver_ids=("stub_solver",),
        repeat=2,
        worker_count=2,
    )

    load_calls = {"n": 0}
    orig_load = ProblemRepository.load

    def counting_load(self, *args, **kwargs):
        load_calls["n"] += 1
        return orig_load(self, *args, **kwargs)

    monkeypatch.setattr(ProblemRepository, "load", counting_load)

    bundle = Engine.build(
        spec=spec,
        problem_root=problem_root,
        solver_root=solver_root,
        seed_strategy=DerivedPerProblemSeedStrategy(),
    )
    load_calls["n"] = 0
    sim = bundle.new_simulator()
    try:
        sim.run_batch(base_seed=42)
        assert load_calls["n"] == 0
    finally:
        sim.close()
