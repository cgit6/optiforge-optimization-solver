from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from mkp.engine.models import ExperimentSpec, SolveResult, RunTask
from mkp.engine.bank import ProblemBank
from mkp.engine.repository import ProblemRepository
from mkp.engine.configs import SolverConfigsSnapshot
from mkp.simulator import Simulator
from mkp.solver.registry import SolverRegistry
from mkp.solver.validator import Validator
from mkp.tools.show import write_simulator_result
from mkp.tools.stat import result_entries, summarize


class CountingSolver:
    calls = 0

    def solve(self, problem, config, rng):
        CountingSolver.calls += 1
        return SolveResult(
            problem_id=problem.problem_id,
            solver_id=config["solver_id"],
            seed=int(rng.integers(0, np.iinfo(np.int32).max)),
            best_solution=np.array([1, 1, 1]),
            best_objective=60,
            feasible=True,
            evaluation_count=10,
            stop_reason="max_iterations_reached",
            runtime=0.1,
            linprog_runtime=0.0,
            error=None,
        )


def _write_problem_yaml(path: Path, *, problem_id: str | None = None) -> None:
    """寫入題目 YAML；未給 `problem_id` 時以檔名（不含副檔名）為 problem_id。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    pid = problem_id if problem_id is not None else path.stem
    path.write_text(
        f"""
problem_id: {pid}
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


def _write_solver_yaml(path: Path, solver_id: str = "stub_solver") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""
solver_id: {solver_id}
solver_class: CountingSolver
capabilities:
  problem_types: [mkp]
  encodings: [binary]
  directions: [max]
stop_condition:
  type: max_iterations
  max_iterations: 10
params: {{}}
""".strip(),
        encoding="utf-8",
    )


def _build_spec() -> ExperimentSpec:
    return ExperimentSpec(
        experiment_id="exp_batch",
        dataset="WEISH",
        problem_ids=("weish01",),
        solver_ids=("stub_solver",),
        repeat=3,
        seed=1234,
        output_dir=Path("output/exp_batch"),
        benchmark_enabled=False,
    )


def _build_simulator(tmp_path: Path) -> tuple[Simulator, Path]:
    """回傳 (Simulator, output_root)；輸出檔案由呼叫端透過 write_simulator_result 觸發。"""
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    output_root = tmp_path / "output"
    _write_problem_yaml(problem_root / "WEISH" / "weish01.yaml")
    _write_solver_yaml(solver_root / "stub_solver.yaml", solver_id="stub_solver")

    repository = ProblemRepository(config_root=problem_root)
    bank = ProblemBank.build_for_spec(repository=repository, spec=_build_spec())
    registry = SolverRegistry()
    registry.register("stub_solver", lambda: CountingSolver())
    solver_configs = SolverConfigsSnapshot.build(_build_spec(), solver_root)
    validator = Validator()
    return (
        Simulator(
            problem_bank=bank,
            solver_registry=registry,
            solver_configs=solver_configs,
            validator=validator,
        ),
        output_root,
    )


def test_expand_tasks_count_and_fields():
    simulator, _ = _build_simulator(Path("/tmp/sim_expand_1"))
    try:
        spec = _build_spec()
        tasks = simulator.expand_tasks(spec)

        assert len(tasks) == 3
        assert tasks[0].problem_id == "weish01"
        assert tasks[0].solver_id == "stub_solver"
        assert tasks[0].repeat_index == 0
        assert tasks[1].repeat_index == 1
        assert tasks[2].repeat_index == 2
    finally:
        simulator.close()


def test_rng_seed_reproducibility_and_independence():
    simulator, _ = _build_simulator(Path("/tmp/sim_expand_2"))
    try:
        spec = _build_spec()
        tasks_a = simulator.expand_tasks(spec)
        tasks_b = simulator.expand_tasks(spec)

        assert [t.seed for t in tasks_a] == [t.seed for t in tasks_b]
        assert len(set(t.seed for t in tasks_a)) == len(tasks_a)
    finally:
        simulator.close()


def _seed_map(tasks: list[RunTask]) -> dict[tuple[str, str, int], int]:
    return {(t.problem_id, t.solver_id, t.repeat_index): t.seed for t in tasks}


def test_expand_tasks_worker_curriculum_order_and_seed_parity(tmp_path: Path):
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    _write_problem_yaml(problem_root / "WEISH" / "p1.yaml", problem_id="p1")
    _write_problem_yaml(problem_root / "WEISH" / "p2.yaml", problem_id="p2")
    _write_solver_yaml(solver_root / "s_a.yaml", solver_id="s_a")
    _write_solver_yaml(solver_root / "s_b.yaml", solver_id="s_b")

    repository = ProblemRepository(config_root=problem_root)
    bank_spec = ExperimentSpec(
        experiment_id="exp_w",
        dataset="WEISH",
        problem_ids=("p1", "p2"),
        solver_ids=("s_a", "s_b"),
        repeat=2,
        seed=999,
        output_dir=Path("output/exp_w"),
    )
    bank = ProblemBank.build_for_spec(repository=repository, spec=bank_spec)
    registry = SolverRegistry()
    registry.register("s_a", lambda: CountingSolver())
    registry.register("s_b", lambda: CountingSolver())
    solver_configs = SolverConfigsSnapshot.build(bank_spec, solver_root)
    validator = Validator()
    simulator = Simulator(
        problem_bank=bank,
        solver_registry=registry,
        solver_configs=solver_configs,
        validator=validator,
    )
    try:
        spec_grid = ExperimentSpec(
            experiment_id="exp_w",
            dataset="WEISH",
            problem_ids=("p1", "p2"),
            solver_ids=("s_a", "s_b"),
            repeat=2,
            seed=999,
            output_dir=Path("output/exp_w"),
            execution_mode="grid",
        )
        spec_worker = ExperimentSpec(
            experiment_id="exp_w",
            dataset="WEISH",
            problem_ids=("p1", "p2"),
            solver_ids=("s_a", "s_b"),
            repeat=2,
            seed=999,
            output_dir=Path("output/exp_w"),
            execution_mode="worker_curriculum",
        )

        grid_tasks = simulator.expand_tasks(spec_grid)
        worker_tasks = simulator.expand_tasks(spec_worker)

        assert len(grid_tasks) == len(worker_tasks) == 2 * 2 * 2
        w0 = worker_tasks[0]
        assert w0.solver_id == "s_a"
        assert w0.repeat_index == 0
        assert w0.problem_id == "p1"

        gmap = _seed_map(grid_tasks)
        wmap = _seed_map(worker_tasks)
        assert gmap == wmap

        sample_keys = [("p1", "s_a", 0), ("p2", "s_b", 1), ("p1", "s_b", 0)]
        for key in sample_keys:
            assert gmap[key] == wmap[key]
    finally:
        simulator.close()


def test_run_batch_worker_curriculum_uses_process_pool(tmp_path: Path):
    """worker_curriculum + ProcessPoolExecutor：repeat 條線各跑 stub_solver，回傳筆數與 summary 正確。"""
    n = 4
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    output_root = tmp_path / "output"
    _write_problem_yaml(problem_root / "WEISH" / "weish01.yaml", problem_id="weish01")
    _write_solver_yaml(solver_root / "stub_solver.yaml", solver_id="stub_solver")

    repository = ProblemRepository(config_root=problem_root)
    bank_spec = ExperimentSpec(
        experiment_id="exp_par",
        dataset="WEISH",
        problem_ids=("weish01",),
        solver_ids=("stub_solver",),
        repeat=n,
        seed=100,
        output_dir=Path("output/exp_par"),
        execution_mode="worker_curriculum",
    )
    bank = ProblemBank.build_for_spec(repository=repository, spec=bank_spec)
    registry = SolverRegistry()
    registry.register("stub_solver", lambda: CountingSolver())
    solver_configs = SolverConfigsSnapshot.build(bank_spec, solver_root)
    validator = Validator()
    simulator = Simulator(
        problem_bank=bank,
        solver_registry=registry,
        solver_configs=solver_configs,
        validator=validator,
    )

    try:
        result = simulator.run_batch(bank_spec)
        assert len(result.rows) == n

        entries = result_entries(result)
        summary = summarize(entries)
        write_simulator_result(result, entries, summary, experiment_id="exp_par", output_root=output_root)
        summary_json = output_root / "exp_par" / "summary.json"
        assert summary_json.exists()
    finally:
        simulator.close()


def test_run_batch_fail_fast_on_problem_load_error(tmp_path: Path):
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    _write_problem_yaml(problem_root / "WEISH" / "weish01.yaml", problem_id="weish01")
    _write_solver_yaml(solver_root / "stub_solver.yaml", solver_id="stub_solver")

    repository = ProblemRepository(config_root=problem_root)
    spec = ExperimentSpec(
        experiment_id="exp_batch_fail_problem",
        dataset="WEISH",
        problem_ids=("missing", "weish01"),
        solver_ids=("stub_solver",),
        repeat=1,
        seed=1,
        output_dir=Path("output/exp_batch_fail_problem"),
    )

    CountingSolver.calls = 0
    with pytest.raises(FileNotFoundError):
        ProblemBank.build_for_spec(repository=repository, spec=spec)
    assert CountingSolver.calls == 0


def test_solver_snapshot_raises_when_solver_yaml_missing(tmp_path: Path) -> None:
    solver_root = tmp_path / "solvers"
    spec = ExperimentSpec(
        experiment_id="exp_snap_missing",
        dataset="WEISH",
        problem_ids=("weish01",),
        solver_ids=("no_such_solver",),
        repeat=1,
        seed=1,
        output_dir=Path("output/exp_snap_missing"),
    )
    with pytest.raises(FileNotFoundError):
        SolverConfigsSnapshot.build(spec, solver_root)


def test_run_task_key_error_when_solver_not_in_snapshot(tmp_path: Path) -> None:
    problem_root = tmp_path / "problems"
    _write_problem_yaml(problem_root / "WEISH" / "weish01.yaml", problem_id="weish01")
    solver_root = tmp_path / "solvers"
    _write_solver_yaml(solver_root / "stub_solver.yaml", solver_id="stub_solver")

    repository = ProblemRepository(config_root=problem_root)
    bank_spec = ExperimentSpec(
        experiment_id="exp_mismatch",
        dataset="WEISH",
        problem_ids=("weish01",),
        solver_ids=("stub_solver",),
        repeat=1,
        seed=1,
        output_dir=Path("output/exp_mismatch"),
    )
    bank = ProblemBank.build_for_spec(repository=repository, spec=bank_spec)
    registry = SolverRegistry()
    registry.register("stub_solver", lambda: CountingSolver())
    solver_configs = SolverConfigsSnapshot.build(bank_spec, solver_root)
    validator = Validator()
    simulator = Simulator(
        problem_bank=bank,
        solver_registry=registry,
        solver_configs=solver_configs,
        validator=validator,
    )
    try:
        task = RunTask(
            problem_id="weish01",
            dataset="WEISH",
            solver_id="other_solver",
            repeat_index=0,
            seed=1,
        )
        with pytest.raises(KeyError):
            simulator.run_task(task)
    finally:
        simulator.close()


def test_run_batch_writes_summary_files(tmp_path: Path):
    simulator, output_root = _build_simulator(tmp_path)
    spec = _build_spec()

    try:
        result = simulator.run_sequential(spec)

        assert len(result.rows) == 3
        entries = result_entries(result)
        summary = summarize(entries)
        write_simulator_result(result, entries, summary, experiment_id="exp_batch", output_root=output_root)
        summary_json = output_root / "exp_batch" / "summary.json"
        summary_csv = output_root / "exp_batch" / "summary.csv"
        assert summary_json.exists()
        assert summary_csv.exists()
    finally:
        simulator.close()
