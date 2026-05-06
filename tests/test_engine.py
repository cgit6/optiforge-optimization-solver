from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from mkp.engine import Engine, SimulationBundle
from mkp.engine.models import ExperimentSpec
from mkp.engine.repository import ProblemRepository
from mkp.tools.show import write_simulator_result
from mkp.tools.stat import result_entries, summarize


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
params: {}
""".strip(),
        encoding="utf-8",
    )


def test_engine_build_returns_bundle_with_runnable_simulator(tmp_path: Path) -> None:
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    output_root = tmp_path / "output"
    _write_problem_yaml(problem_root / "WEISH" / "weish01.yaml")
    _write_solver_yaml(solver_root / "stub_solver.yaml")

    spec = ExperimentSpec(
        experiment_id="exp_engine_1",
        dataset="WEISH",
        problem_ids=("weish01",),
        solver_ids=("stub_solver",),
        repeat=1,
        seed=7,
        output_dir=output_root / "exp_engine_1",
    )

    bundle = Engine.build(
        spec=spec,
        problem_root=problem_root,
        solver_root=solver_root,
        output_root=output_root,
    )

    assert isinstance(bundle, SimulationBundle)
    assert bundle.spec is spec
    assert bundle.game_setting is not None
    assert len(bundle.catalog) > 0
    assert "WEISH" in bundle.game_setting.datasets
    assert bundle.problem_bank is not None
    assert bundle.solver_configs is not None
    assert bundle.solver_configs.solver_ids() == frozenset(spec.solver_ids)
    assert bundle.solver_builders
    assert bundle.default_rng is np.random.default_rng
    sim = bundle.NewSimulatorWithSeed("stub_solver", spec.seed)
    try:
        result = sim.run_sequential(spec)
        assert len(result.rows) == 1
        entries = result_entries(result)
        summary = summarize(entries)
        write_simulator_result(result, entries, summary, experiment_id="exp_engine_1", output_root=output_root)
        assert (output_root / "exp_engine_1" / "runs.csv").exists()
    finally:
        sim.close()


def test_engine_build_fails_when_experiment_problem_yaml_is_invalid(tmp_path: Path) -> None:
    """僅本次 spec 指到的題目會被 load 驗證；壞檔必須在 problem_ids 內才會讓 build 失敗。"""
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    output_root = tmp_path / "output"
    _write_problem_yaml(problem_root / "WEISH" / "weish01.yaml")
    (problem_root / "WEISH" / "broken.yaml").write_text("items: not_a_mapping\n", encoding="utf-8")
    _write_solver_yaml(solver_root / "stub_solver.yaml")

    spec = ExperimentSpec(
        experiment_id="exp_bad_cat",
        dataset="WEISH",
        problem_ids=("broken",),
        solver_ids=("stub_solver",),
        repeat=1,
        seed=1,
        output_dir=output_root / "exp_bad_cat",
    )

    with pytest.raises((ValueError, FileNotFoundError, TypeError)):
        Engine.build(
            spec=spec,
            problem_root=problem_root,
            solver_root=solver_root,
            output_root=output_root,
        )


def test_engine_build_succeeds_when_unused_catalog_yaml_is_invalid(tmp_path: Path) -> None:
    """目錄內其他題目的壞檔不阻擋 build（與舊版「全庫驗證」語意不同）。"""
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    output_root = tmp_path / "output"
    _write_problem_yaml(problem_root / "WEISH" / "weish01.yaml")
    (problem_root / "WEISH" / "broken.yaml").write_text("items: not_a_mapping\n", encoding="utf-8")
    _write_solver_yaml(solver_root / "stub_solver.yaml")

    spec = ExperimentSpec(
        experiment_id="exp_ok_unused_bad",
        dataset="WEISH",
        problem_ids=("weish01",),
        solver_ids=("stub_solver",),
        repeat=1,
        seed=1,
        output_dir=output_root / "exp_ok_unused_bad",
    )

    bundle = Engine.build(
        spec=spec,
        problem_root=problem_root,
        solver_root=solver_root,
        output_root=output_root,
    )
    try:
        assert bundle.problem_bank.get("WEISH", "weish01").problem_id == "weish01"
    finally:
        bundle.problem_bank.close()


def test_engine_build_fails_when_experiment_problem_has_unknown_best_known(tmp_path: Path) -> None:
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    output_root = tmp_path / "output"
    _write_problem_yaml(problem_root / "WEISH" / "weish01.yaml")
    (problem_root / "WEISH" / "broken.yaml").write_text(
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
        experiment_id="exp_unknown_best",
        dataset="WEISH",
        problem_ids=("broken",),
        solver_ids=("stub_solver",),
        repeat=1,
        seed=1,
        output_dir=output_root / "exp_unknown_best",
    )

    with pytest.raises(ValueError, match="best_known must be a positive integer"):
        Engine.build(
            spec=spec,
            problem_root=problem_root,
            solver_root=solver_root,
            output_root=output_root,
        )


def test_engine_build_fails_when_experiment_problem_not_in_catalog(tmp_path: Path) -> None:
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    output_root = tmp_path / "output"
    _write_problem_yaml(problem_root / "WEISH" / "weish01.yaml")
    _write_solver_yaml(solver_root / "stub_solver.yaml")

    spec = ExperimentSpec(
        experiment_id="exp_missing_pid",
        dataset="WEISH",
        problem_ids=("not_in_folder",),
        solver_ids=("stub_solver",),
        repeat=1,
        seed=1,
        output_dir=output_root / "exp_missing_pid",
    )

    with pytest.raises(FileNotFoundError, match="catalog"):
        Engine.build(
            spec=spec,
            problem_root=problem_root,
            solver_root=solver_root,
            output_root=output_root,
        )


def test_worker_curriculum_does_not_call_problem_repository_load_after_engine_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    output_root = tmp_path / "output"
    _write_problem_yaml(problem_root / "WEISH" / "weish01.yaml")
    _write_solver_yaml(solver_root / "stub_solver.yaml")

    spec = ExperimentSpec(
        experiment_id="exp_shm",
        dataset="WEISH",
        problem_ids=("weish01",),
        solver_ids=("stub_solver",),
        repeat=2,
        seed=42,
        output_dir=output_root / "exp_shm",
        execution_mode="worker_curriculum",
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
        output_root=output_root,
    )
    load_calls["n"] = 0
    sim = bundle.NewSimulatorWithSeed("stub_solver", spec.seed)
    try:
        sim.run_batch(spec)
        assert load_calls["n"] == 0
    finally:
        sim.close()
