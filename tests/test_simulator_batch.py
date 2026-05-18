from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from mkp.engine.models import ExperimentSpec, SolveResult, RunTask
from mkp.engine.bank import ProblemBank
from mkp.engine.repository import ProblemRepository
from mkp.engine.configs import SolverConfigsSnapshot
from mkp.problem import buildProblemRegistry, problemBuilders
from mkp.simulator import Simulator
from mkp.solver.registry import SolverRegistry
from mkp.solver.validator import Validator
from mkp.tools.show import write_simulator_result


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
    _write_solver_yaml_with_params(path, solver_id=solver_id, params_yaml="  - {}")


def _write_solver_yaml_with_params(path: Path, *, solver_id: str, params_yaml: str) -> None:
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
params:
{params_yaml}
""".strip(),
        encoding="utf-8",
    )


def _build_problem_bank(problem_root: Path, spec: ExperimentSpec) -> ProblemBank:
    problem_registry = buildProblemRegistry(problemBuilders())
    repository = ProblemRepository(config_root=problem_root, registry=problem_registry)
    return ProblemBank.build(repository=repository, spec=spec, registry=problem_registry)


def _build_spec() -> ExperimentSpec:
    return ExperimentSpec(
        experiment_name="exp_batch",
        dataset="WEISH",
        problem_ids=("weish01",),
        solver_ids=("stub_solver",),
        repeat=3,
    )


def _build_simulator(tmp_path: Path) -> tuple[Simulator, Path]:
    """回傳 (Simulator, output_root)；輸出檔案由呼叫端透過 write_simulator_result 觸發。"""
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    output_root = tmp_path / "output"
    _write_problem_yaml(problem_root / "mkp" / "WEISH" / "weish01.yaml")
    _write_solver_yaml(solver_root / "stub_solver.yaml", solver_id="stub_solver")

    bank = _build_problem_bank(problem_root, _build_spec())
    registry = SolverRegistry()
    registry.register("stub_solver", lambda: CountingSolver())
    solver_configs = SolverConfigsSnapshot.build(_build_spec(), solver_root)
    validator = Validator()
    return (
        Simulator(
            spec=_build_spec(),
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
        tasks = simulator.expand_tasks(seed=1234)

        assert len(tasks) == 3
        assert tasks[0].problem_id == "weish01"
        assert tasks[0].solver_id == "stub_solver"
        assert tasks[0].repeat_index == 0
        assert tasks[0].param_set_index == 0
        assert tasks[1].repeat_index == 1
        assert tasks[2].repeat_index == 2
    finally:
        simulator.close()


def test_rng_seed_reproducibility_and_independence():
    simulator, _ = _build_simulator(Path("/tmp/sim_expand_2"))
    try:
        tasks_a = simulator.expand_tasks(seed=1234)
        tasks_b = simulator.expand_tasks(seed=1234)

        assert [t.seed for t in tasks_a] == [t.seed for t in tasks_b]
        assert len(set(t.seed for t in tasks_a)) == len(tasks_a)
    finally:
        simulator.close()


def test_solver_snapshot_selects_requested_param_set(tmp_path: Path) -> None:
    solver_root = tmp_path / "solvers"
    _write_solver_yaml(
        solver_root / "stub_solver.yaml",
        solver_id="stub_solver",
    )
    (solver_root / "stub_solver.yaml").write_text(
        """
solver_id: stub_solver
solver_class: CountingSolver
capabilities:
  problem_types: [mkp]
  encodings: [binary]
  directions: [max]
stop_condition:
  type: max_iterations
  max_iterations: 10
params:
  - {pop_size: 20, z: 0.08}
  - {pop_size: 30, z: 0.03}
""".strip(),
        encoding="utf-8",
    )
    spec = ExperimentSpec(
        experiment_name="exp_param_set",
        dataset="WEISH",
        problem_ids=("weish01",),
        solver_ids=("stub_solver",),
        repeat=1,
    )

    snapshot = SolverConfigsSnapshot.build(spec, solver_root)
    config = snapshot.get("stub_solver", 1)

    assert config["param_set_index"] == 1
    assert config["params"] == {"pop_size": 30, "z": 0.03}


def _seed_map(tasks: list[RunTask]) -> dict[tuple[str, str, int, int], int]:
    return {(t.problem_id, t.solver_id, t.param_set_index, t.repeat_index): t.seed for t in tasks}


def _build_seed_simulator(
    tmp_path: Path,
    *,
    solver_ids: tuple[str, ...],
    solver_params: dict[str, tuple[str, ...]],
    repeat: int = 2,
) -> Simulator:
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    _write_problem_yaml(problem_root / "mkp" / "WEISH" / "p1.yaml", problem_id="p1")
    for solver_id, params in solver_params.items():
        params_yaml = "\n".join(f"  - {param}" for param in params)
        _write_solver_yaml_with_params(
            solver_root / f"{solver_id}.yaml",
            solver_id=solver_id,
            params_yaml=params_yaml,
        )

    spec = ExperimentSpec(
        experiment_name="exp_seed",
        dataset="WEISH",
        problem_ids=("p1",),
        solver_ids=solver_ids,
        repeat=repeat,
    )
    bank = _build_problem_bank(problem_root, spec)
    registry = SolverRegistry()
    for solver_id in solver_ids:
        registry.register(solver_id, lambda: CountingSolver())
    return Simulator(
        spec=spec,
        problem_bank=bank,
        solver_registry=registry,
        solver_configs=SolverConfigsSnapshot.build(spec, solver_root),
        validator=Validator(),
    )


def _find_seed(tasks: list[RunTask], *, solver_id: str, param_set_index: int, repeat_index: int = 0) -> int:
    for task in tasks:
        if (
            task.solver_id == solver_id
            and task.param_set_index == param_set_index
            and task.repeat_index == repeat_index
        ):
            return task.seed
    raise AssertionError(
        f"seed not found: {solver_id=} {param_set_index=} {repeat_index=}"
    )


def test_expand_tasks_order_and_seed_keys_include_param_set(tmp_path: Path):
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    _write_problem_yaml(problem_root / "mkp" / "WEISH" / "p1.yaml", problem_id="p1")
    _write_problem_yaml(problem_root / "mkp" / "WEISH" / "p2.yaml", problem_id="p2")
    _write_solver_yaml(solver_root / "s_a.yaml", solver_id="s_a")
    _write_solver_yaml(solver_root / "s_b.yaml", solver_id="s_b")

    bank_spec = ExperimentSpec(
        experiment_name="exp_w",
        dataset="WEISH",
        problem_ids=("p1", "p2"),
        solver_ids=("s_a", "s_b"),
        repeat=2,
    )
    bank = _build_problem_bank(problem_root, bank_spec)
    registry = SolverRegistry()
    registry.register("s_a", lambda: CountingSolver())
    registry.register("s_b", lambda: CountingSolver())
    solver_configs = SolverConfigsSnapshot.build(bank_spec, solver_root)
    validator = Validator()
    simulator = Simulator(
        spec=bank_spec,
        problem_bank=bank,
        solver_registry=registry,
        solver_configs=solver_configs,
        validator=validator,
    )
    try:
        tasks = simulator.expand_tasks(seed=999)

        assert len(tasks) == 2 * 2 * 1 * 2
        first = tasks[0]
        assert first.problem_id == "p1"
        assert first.solver_id == "s_a"
        assert first.param_set_index == 0
        assert first.repeat_index == 0
        assert set(_seed_map(tasks)) == {
            ("p1", "s_a", 0, 0),
            ("p1", "s_a", 0, 1),
            ("p1", "s_b", 0, 0),
            ("p1", "s_b", 0, 1),
            ("p2", "s_a", 0, 0),
            ("p2", "s_a", 0, 1),
            ("p2", "s_b", 0, 0),
            ("p2", "s_b", 0, 1),
        }
    finally:
        simulator.close()


def test_task_seed_is_independent_of_other_solvers_and_solver_order(tmp_path: Path) -> None:
    solver_params = {
        "s_a": ("{pop_size: 10, z: 0.01}",),
        "s_b": ("{pop_size: 20, z: 0.02}",),
    }
    sim_ab = _build_seed_simulator(
        tmp_path / "ab",
        solver_ids=("s_a", "s_b"),
        solver_params=solver_params,
    )
    sim_ba = _build_seed_simulator(
        tmp_path / "ba",
        solver_ids=("s_b", "s_a"),
        solver_params=solver_params,
    )
    sim_b = _build_seed_simulator(
        tmp_path / "b",
        solver_ids=("s_b",),
        solver_params={"s_b": solver_params["s_b"]},
    )
    try:
        seed_ab = _find_seed(sim_ab.expand_tasks(seed=999), solver_id="s_b", param_set_index=0)
        seed_ba = _find_seed(sim_ba.expand_tasks(seed=999), solver_id="s_b", param_set_index=0)
        seed_b = _find_seed(sim_b.expand_tasks(seed=999), solver_id="s_b", param_set_index=0)

        assert seed_ab == seed_ba == seed_b
    finally:
        sim_ab.close()
        sim_ba.close()
        sim_b.close()


def test_task_seed_uses_param_content_not_param_set_index(tmp_path: Path) -> None:
    sim_full = _build_seed_simulator(
        tmp_path / "full",
        solver_ids=("s_a",),
        solver_params={
            "s_a": (
                "{pop_size: 10, z: 0.01}",
                "{pop_size: 20, z: 0.02}",
                "{pop_size: 30, z: 0.03}",
            )
        },
    )
    sim_reduced = _build_seed_simulator(
        tmp_path / "reduced",
        solver_ids=("s_a",),
        solver_params={"s_a": ("{pop_size: 20, z: 0.02}",)},
    )
    try:
        full_tasks = sim_full.expand_tasks(seed=999)
        reduced_tasks = sim_reduced.expand_tasks(seed=999)

        seed_full_param_1 = _find_seed(full_tasks, solver_id="s_a", param_set_index=1)
        seed_reduced_param_0 = _find_seed(reduced_tasks, solver_id="s_a", param_set_index=0)

        assert seed_full_param_1 == seed_reduced_param_0
        assert seed_full_param_1 != _find_seed(full_tasks, solver_id="s_a", param_set_index=0)
        assert seed_full_param_1 != _find_seed(full_tasks, solver_id="s_a", param_set_index=2)
    finally:
        sim_full.close()
        sim_reduced.close()


def test_task_seed_changes_when_base_seed_or_repeat_changes(tmp_path: Path) -> None:
    solver_params = {"s_a": ("{pop_size: 20, z: 0.02}",)}
    sim_seed_1 = _build_seed_simulator(
        tmp_path / "seed1",
        solver_ids=("s_a",),
        solver_params=solver_params,
    )
    sim_seed_2 = _build_seed_simulator(
        tmp_path / "seed2",
        solver_ids=("s_a",),
        solver_params=solver_params,
    )
    try:
        tasks_seed_1 = sim_seed_1.expand_tasks(seed=1)
        tasks_seed_2 = sim_seed_2.expand_tasks(seed=2)

        assert _find_seed(tasks_seed_1, solver_id="s_a", param_set_index=0, repeat_index=0) != _find_seed(
            tasks_seed_2,
            solver_id="s_a",
            param_set_index=0,
            repeat_index=0,
        )
        assert _find_seed(tasks_seed_1, solver_id="s_a", param_set_index=0, repeat_index=0) != _find_seed(
            tasks_seed_1,
            solver_id="s_a",
            param_set_index=0,
            repeat_index=1,
        )
    finally:
        sim_seed_1.close()
        sim_seed_2.close()


def test_run_batch_uses_process_pool(tmp_path: Path):
    """worker_count > 1 時使用 ProcessPoolExecutor，回傳筆數與 summary 正確。"""
    n = 4
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    output_root = tmp_path / "output"
    _write_problem_yaml(problem_root / "mkp" / "WEISH" / "weish01.yaml", problem_id="weish01")
    _write_solver_yaml(solver_root / "stub_solver.yaml", solver_id="stub_solver")

    bank_spec = ExperimentSpec(
        experiment_name="exp_par",
        dataset="WEISH",
        problem_ids=("weish01",),
        solver_ids=("stub_solver",),
        repeat=n,
        worker_count=2,
    )
    bank = _build_problem_bank(problem_root, bank_spec)
    registry = SolverRegistry()
    registry.register("stub_solver", lambda: CountingSolver())
    solver_configs = SolverConfigsSnapshot.build(bank_spec, solver_root)
    validator = Validator()
    simulator = Simulator(
        spec=bank_spec,
        problem_bank=bank,
        solver_registry=registry,
        solver_configs=solver_configs,
        validator=validator,
    )

    try:
        result = simulator.run_batch(seed=100)
        assert len(result.rows) == n

        write_simulator_result(result, experiment_name="exp_par", output_root=output_root)
        summary_json = output_root / "exp_par" / "stub_solver" / "param_0" / "summary.json"
        assert summary_json.exists()
    finally:
        simulator.close()


def test_run_batch_fail_fast_on_problem_load_error(tmp_path: Path):
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    _write_problem_yaml(problem_root / "mkp" / "WEISH" / "weish01.yaml", problem_id="weish01")
    _write_solver_yaml(solver_root / "stub_solver.yaml", solver_id="stub_solver")

    problem_registry = buildProblemRegistry(problemBuilders())
    repository = ProblemRepository(config_root=problem_root, registry=problem_registry)
    spec = ExperimentSpec(
        experiment_name="exp_batch_fail_problem",
        dataset="WEISH",
        problem_ids=("missing", "weish01"),
        solver_ids=("stub_solver",),
        repeat=1,
    )

    CountingSolver.calls = 0
    with pytest.raises(FileNotFoundError):
        ProblemBank.build(repository=repository, spec=spec, registry=problem_registry)
    assert CountingSolver.calls == 0


def test_solver_snapshot_raises_when_solver_yaml_missing(tmp_path: Path) -> None:
    solver_root = tmp_path / "solvers"
    spec = ExperimentSpec(
        experiment_name="exp_snap_missing",
        dataset="WEISH",
        problem_ids=("weish01",),
        solver_ids=("no_such_solver",),
        repeat=1,
    )
    with pytest.raises(FileNotFoundError):
        SolverConfigsSnapshot.build(spec, solver_root)


def test_run_task_key_error_when_solver_not_in_snapshot(tmp_path: Path) -> None:
    problem_root = tmp_path / "problems"
    _write_problem_yaml(problem_root / "mkp" / "WEISH" / "weish01.yaml", problem_id="weish01")
    solver_root = tmp_path / "solvers"
    _write_solver_yaml(solver_root / "stub_solver.yaml", solver_id="stub_solver")

    bank_spec = ExperimentSpec(
        experiment_name="exp_mismatch",
        dataset="WEISH",
        problem_ids=("weish01",),
        solver_ids=("stub_solver",),
        repeat=1,
    )
    bank = _build_problem_bank(problem_root, bank_spec)
    registry = SolverRegistry()
    registry.register("stub_solver", lambda: CountingSolver())
    solver_configs = SolverConfigsSnapshot.build(bank_spec, solver_root)
    validator = Validator()
    simulator = Simulator(
        spec=bank_spec,
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
            param_set_index=0,
        )
        with pytest.raises(KeyError):
            simulator.run_task(task)
    finally:
        simulator.close()


def test_run_batch_writes_summary_files(tmp_path: Path):
    simulator, output_root = _build_simulator(tmp_path)

    try:
        result = simulator.run_sequential(seed=1)

        assert len(result.rows) == 3
        write_simulator_result(result, experiment_name="exp_batch", output_root=output_root)
        summary_json = output_root / "exp_batch" / "stub_solver" / "param_0" / "summary.json"
        summary_csv = output_root / "exp_batch" / "stub_solver" / "param_0" / "summary.csv"
        assert summary_json.exists()
        assert summary_csv.exists()
    finally:
        simulator.close()
