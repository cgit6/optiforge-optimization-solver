from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from mkp.engine.models import ExperimentSpec, SolveResult, RunTask
from mkp.engine.bank import ProblemBank
from mkp.engine.repository import ProblemRepository
from mkp.engine.configs import SolverConfigsSnapshot
from mkp.problem import buildProblemRegistry, problemBuilders
from mkp.rng import DerivedPerProblemSeedStrategy, make_numpy_rng
from mkp.simulator import Simulator
from mkp.solver.registry import SolverRegistry
from mkp.tools.show import write_simulator_result


class CountingSolver:
    calls = 0

    def solve(self, problem, config, rng):
        CountingSolver.calls += 1
        run_seed_value = config.get("run_seed")
        run_seed = int(run_seed_value) if run_seed_value is not None else int(rng.integers(0, np.iinfo(np.int32).max))
        first_random = int(rng.integers(0, np.iinfo(np.int32).max))
        return SolveResult(
            problem_id=problem.problem_id,
            solver_id=config["solver_id"],
            run_seed=run_seed,
            best_solution=np.array([1, 1, 1]),
            best_objective=60,
            feasible=True,
            evaluation_count=10,
            stop_reason="max_iterations_reached",
            runtime=0.1,
            linprog_runtime=0.0,
            error=None,
            metadata={"first_random": first_random},
        )


def _offset_rng_factory(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed + 1)


def _write_problem_yaml(path: Path, *, problem_id: str | None = None, dataset: str = "WEISH") -> None:
    """寫入題目 YAML；未給 `problem_id` 時以檔名（不含副檔名）為 problem_id。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    pid = problem_id if problem_id is not None else path.stem
    path.write_text(
        f"""
problem_id: {pid}
dataset: {dataset}
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


def _build_spec(*, base_seed: int = 1234) -> ExperimentSpec:
    return ExperimentSpec(
        experiment_name="exp_batch",
        dataset="WEISH",
        problem_ids=("weish01",),
        solver_ids=("stub_solver",),
        repeat=3,
        base_seed=base_seed,
    )


def _build_simulator(tmp_path: Path, *, base_seed: int = 1234) -> tuple[Simulator, Path]:
    """回傳 (Simulator, output_root)；輸出檔案由呼叫端透過 write_simulator_result 觸發。"""
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    output_root = tmp_path / "output"
    _write_problem_yaml(problem_root / "mkp" / "WEISH" / "weish01.yaml")
    _write_solver_yaml(solver_root / "stub_solver.yaml", solver_id="stub_solver")

    spec = _build_spec(base_seed=base_seed)
    bank = _build_problem_bank(problem_root, spec)
    registry = SolverRegistry()
    registry.register("stub_solver", lambda: CountingSolver())
    solver_configs = SolverConfigsSnapshot.build(spec, solver_root)
    return (
        Simulator(
            spec=spec,
            problem_bank=bank,
            solver_registry=registry,
            solver_configs=solver_configs,
            seed_strategy=DerivedPerProblemSeedStrategy(),
            rng_factory=make_numpy_rng,
        ),
        output_root,
    )


def test_expand_tasks_count_and_fields():
    simulator, _ = _build_simulator(Path("/tmp/sim_expand_1"))
    try:
        tasks = simulator.expand_tasks()

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
        tasks_a = simulator.expand_tasks()
        tasks_b = simulator.expand_tasks()

        assert [t.task_seed for t in tasks_a] == [t.task_seed for t in tasks_b]
        assert len(set(t.task_seed for t in tasks_a)) == len(tasks_a)
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
    return {(t.problem_id, t.solver_id, t.param_set_index, t.repeat_index): t.task_seed for t in tasks}


def _build_seed_simulators(
    tmp_path: Path,
    *,
    solver_ids: tuple[str, ...],
    solver_params: dict[str, tuple[str, ...]],
    repeat: int = 2,
    base_seed: int = 999,
    dataset: str = "WEISH",
    problem_ids: tuple[str, ...] = ("p1",),
) -> tuple[Simulator, ...]:
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    for problem_id in problem_ids:
        _write_problem_yaml(
            problem_root / "mkp" / dataset / f"{problem_id}.yaml",
            problem_id=problem_id,
            dataset=dataset,
        )
    for solver_id, params in solver_params.items():
        params_yaml = "\n".join(f"  - {param}" for param in params)
        _write_solver_yaml_with_params(
            solver_root / f"{solver_id}.yaml",
            solver_id=solver_id,
            params_yaml=params_yaml,
        )

    spec = ExperimentSpec(
        experiment_name="exp_seed",
        dataset=dataset,
        problem_ids=problem_ids,
        solver_ids=solver_ids,
        repeat=repeat,
        base_seed=base_seed,
    )
    bank = _build_problem_bank(problem_root, spec)
    registry = SolverRegistry()
    for solver_id in solver_ids:
        registry.register(solver_id, lambda: CountingSolver())
    solver_configs = SolverConfigsSnapshot.build(spec, solver_root)
    return tuple(
        Simulator(
            spec=ExperimentSpec(
                experiment_name="exp_seed",
                dataset=dataset,
                problem_ids=problem_ids,
                solver_ids=(solver_id,),
                repeat=repeat,
                base_seed=base_seed,
            ),
            problem_bank=bank,
            solver_registry=registry,
            solver_configs=solver_configs,
            seed_strategy=DerivedPerProblemSeedStrategy(),
            rng_factory=make_numpy_rng,
        )
        for solver_id in solver_ids
    )


def _build_seed_simulator(
    tmp_path: Path,
    *,
    solver_ids: tuple[str, ...],
    solver_params: dict[str, tuple[str, ...]],
    repeat: int = 2,
    base_seed: int = 999,
    dataset: str = "WEISH",
    problem_ids: tuple[str, ...] = ("p1",),
) -> Simulator:
    simulators = _build_seed_simulators(
        tmp_path,
        solver_ids=solver_ids,
        solver_params=solver_params,
        repeat=repeat,
        base_seed=base_seed,
        dataset=dataset,
        problem_ids=problem_ids,
    )
    if len(simulators) != 1:
        raise ValueError("_build_seed_simulator requires exactly one solver.")
    return simulators[0]


def _find_seed(
    tasks: list[RunTask],
    *,
    solver_id: str,
    param_set_index: int,
    repeat_index: int = 0,
    problem_id: str = "p1",
) -> int:
    for task in tasks:
        if (
            task.problem_id == problem_id
            and task.solver_id == solver_id
            and task.param_set_index == param_set_index
            and task.repeat_index == repeat_index
        ):
            return task.task_seed
    raise AssertionError(
        f"seed not found: {problem_id=} {solver_id=} {param_set_index=} {repeat_index=}"
    )


def test_expand_tasks_order_and_seed_keys_preserve_variants(tmp_path: Path):
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
        base_seed=999,
    )
    bank = _build_problem_bank(problem_root, bank_spec)
    registry = SolverRegistry()
    registry.register("s_a", lambda: CountingSolver())
    registry.register("s_b", lambda: CountingSolver())
    solver_configs = SolverConfigsSnapshot.build(bank_spec, solver_root)
    simulators = tuple(
        Simulator(
            spec=ExperimentSpec(
                experiment_name="exp_w",
                dataset="WEISH",
                problem_ids=("p1", "p2"),
                solver_ids=(solver_id,),
                repeat=2,
                base_seed=999,
            ),
            problem_bank=bank,
            solver_registry=registry,
            solver_configs=solver_configs,
            seed_strategy=DerivedPerProblemSeedStrategy(),
            rng_factory=make_numpy_rng,
        )
        for solver_id in ("s_a", "s_b")
    )
    try:
        tasks = [task for simulator in simulators for task in simulator.expand_tasks()]

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
        assert _find_seed(tasks, problem_id="p1", solver_id="s_a", param_set_index=0, repeat_index=0) == _find_seed(
            tasks,
            problem_id="p1",
            solver_id="s_b",
            param_set_index=0,
            repeat_index=0,
        )
        assert _find_seed(tasks, problem_id="p1", solver_id="s_a", param_set_index=0, repeat_index=0) != _find_seed(
            tasks,
            problem_id="p1",
            solver_id="s_a",
            param_set_index=0,
            repeat_index=1,
        )
        assert _find_seed(tasks, problem_id="p1", solver_id="s_a", param_set_index=0, repeat_index=0) != _find_seed(
            tasks,
            problem_id="p2",
            solver_id="s_a",
            param_set_index=0,
            repeat_index=0,
        )
    finally:
        for simulator in simulators:
            simulator.close()


def test_task_seed_is_independent_of_other_solvers_and_solver_order(tmp_path: Path) -> None:
    solver_params = {
        "s_a": ("{pop_size: 10, z: 0.01}",),
        "s_b": ("{pop_size: 20, z: 0.02}",),
    }
    sims_ab = _build_seed_simulators(
        tmp_path / "ab",
        solver_ids=("s_a", "s_b"),
        solver_params=solver_params,
    )
    sims_ba = _build_seed_simulators(
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
        sim_ab = {sim.spec.solver_ids[0]: sim for sim in sims_ab}["s_b"]
        sim_ba = {sim.spec.solver_ids[0]: sim for sim in sims_ba}["s_b"]
        seed_ab = _find_seed(sim_ab.expand_tasks(), solver_id="s_b", param_set_index=0)
        seed_ba = _find_seed(sim_ba.expand_tasks(), solver_id="s_b", param_set_index=0)
        seed_b = _find_seed(sim_b.expand_tasks(), solver_id="s_b", param_set_index=0)

        assert seed_ab == seed_ba == seed_b
    finally:
        for simulator in sims_ab:
            simulator.close()
        for simulator in sims_ba:
            simulator.close()
        sim_b.close()


def test_task_seed_is_independent_of_param_order_and_count(tmp_path: Path) -> None:
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
    sim_reordered = _build_seed_simulator(
        tmp_path / "reordered",
        solver_ids=("s_a",),
        solver_params={
            "s_a": (
                "{pop_size: 30, z: 0.03}",
                "{pop_size: 10, z: 0.01}",
                "{pop_size: 20, z: 0.02}",
            )
        },
    )
    sim_reduced = _build_seed_simulator(
        tmp_path / "reduced",
        solver_ids=("s_a",),
        solver_params={"s_a": ("{pop_size: 20, z: 0.02}",)},
    )
    try:
        full_tasks = sim_full.expand_tasks()
        reordered_tasks = sim_reordered.expand_tasks()
        reduced_tasks = sim_reduced.expand_tasks()

        expected_seed = _find_seed(full_tasks, solver_id="s_a", param_set_index=0)

        assert _find_seed(full_tasks, solver_id="s_a", param_set_index=1) == expected_seed
        assert _find_seed(full_tasks, solver_id="s_a", param_set_index=2) == expected_seed
        assert _find_seed(reordered_tasks, solver_id="s_a", param_set_index=0) == expected_seed
        assert _find_seed(reordered_tasks, solver_id="s_a", param_set_index=1) == expected_seed
        assert _find_seed(reordered_tasks, solver_id="s_a", param_set_index=2) == expected_seed
        assert _find_seed(reduced_tasks, solver_id="s_a", param_set_index=0) == expected_seed
    finally:
        sim_full.close()
        sim_reordered.close()
        sim_reduced.close()


def test_task_seed_changes_when_base_seed_or_repeat_changes(tmp_path: Path) -> None:
    solver_params = {"s_a": ("{pop_size: 20, z: 0.02}",)}
    sim_seed_1 = _build_seed_simulator(
        tmp_path / "seed1",
        solver_ids=("s_a",),
        solver_params=solver_params,
        base_seed=1,
    )
    sim_seed_2 = _build_seed_simulator(
        tmp_path / "seed2",
        solver_ids=("s_a",),
        solver_params=solver_params,
        base_seed=2,
    )
    try:
        tasks_seed_1 = sim_seed_1.expand_tasks()
        tasks_seed_2 = sim_seed_2.expand_tasks()

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


def test_task_seed_changes_when_dataset_changes(tmp_path: Path) -> None:
    solver_params = {"s_a": ("{pop_size: 20, z: 0.02}",)}
    sim_weish = _build_seed_simulator(
        tmp_path / "weish",
        solver_ids=("s_a",),
        solver_params=solver_params,
        dataset="WEISH",
    )
    sim_alt = _build_seed_simulator(
        tmp_path / "alt",
        solver_ids=("s_a",),
        solver_params=solver_params,
        dataset="ALT",
    )
    try:
        seed_weish = _find_seed(sim_weish.expand_tasks(), solver_id="s_a", param_set_index=0)
        seed_alt = _find_seed(sim_alt.expand_tasks(), solver_id="s_a", param_set_index=0)

        assert seed_weish != seed_alt
    finally:
        sim_weish.close()
        sim_alt.close()


def test_task_seed_is_independent_of_problem_order_and_subset(tmp_path: Path) -> None:
    solver_params = {"s_a": ("{pop_size: 20, z: 0.02}",)}
    sim_ordered = _build_seed_simulator(
        tmp_path / "ordered",
        solver_ids=("s_a",),
        solver_params=solver_params,
        problem_ids=("p1", "p2"),
    )
    sim_reordered = _build_seed_simulator(
        tmp_path / "reordered_problems",
        solver_ids=("s_a",),
        solver_params=solver_params,
        problem_ids=("p2", "p1"),
    )
    sim_subset = _build_seed_simulator(
        tmp_path / "subset",
        solver_ids=("s_a",),
        solver_params=solver_params,
        problem_ids=("p2",),
    )
    try:
        seed_ordered = _find_seed(
            sim_ordered.expand_tasks(),
            problem_id="p2",
            solver_id="s_a",
            param_set_index=0,
        )
        seed_reordered = _find_seed(
            sim_reordered.expand_tasks(),
            problem_id="p2",
            solver_id="s_a",
            param_set_index=0,
        )
        seed_subset = _find_seed(
            sim_subset.expand_tasks(),
            problem_id="p2",
            solver_id="s_a",
            param_set_index=0,
        )

        assert seed_ordered == seed_reordered == seed_subset
    finally:
        sim_ordered.close()
        sim_reordered.close()
        sim_subset.close()


def test_run_batch_uses_machine_pool(tmp_path: Path):
    """worker_count > 1 時使用 MachinePool，回傳筆數與 summary 正確。"""
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
        base_seed=100,
    )
    bank = _build_problem_bank(problem_root, bank_spec)
    registry = SolverRegistry()
    registry.register("stub_solver", lambda: CountingSolver())
    solver_configs = SolverConfigsSnapshot.build(bank_spec, solver_root)
    simulator = Simulator(
        spec=bank_spec,
        problem_bank=bank,
        solver_registry=registry,
        solver_configs=solver_configs,
        seed_strategy=DerivedPerProblemSeedStrategy(),
        rng_factory=make_numpy_rng,
    )

    try:
        result = simulator.run_batch()
        rows = result.iter_rows()
        assert len(rows) == n
        assert all(row.solve_result.run_seed == row.task.task_seed for row in rows)

        write_simulator_result(result, experiment_name="exp_par", output_root=output_root)
        summary_json = output_root / "exp_par" / "stub_solver" / "param_0" / "summary.json"
        assert summary_json.exists()
    finally:
        simulator.close()


def test_run_batch_matches_sequential_seed_assignment(tmp_path: Path):
    n = 4
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    _write_problem_yaml(problem_root / "mkp" / "WEISH" / "weish01.yaml", problem_id="weish01")
    _write_solver_yaml(solver_root / "stub_solver.yaml", solver_id="stub_solver")

    bank_spec = ExperimentSpec(
        experiment_name="exp_par",
        dataset="WEISH",
        problem_ids=("weish01",),
        solver_ids=("stub_solver",),
        repeat=n,
        worker_count=2,
        base_seed=100,
    )
    bank = _build_problem_bank(problem_root, bank_spec)
    registry = SolverRegistry()
    registry.register("stub_solver", lambda: CountingSolver())
    solver_configs = SolverConfigsSnapshot.build(bank_spec, solver_root)
    simulator = Simulator(
        spec=bank_spec,
        problem_bank=bank,
        solver_registry=registry,
        solver_configs=solver_configs,
        seed_strategy=DerivedPerProblemSeedStrategy(),
        rng_factory=make_numpy_rng,
    )

    try:
        sequential = simulator.run_sequential(show_progress=False)
        batch = simulator.run_batch(show_progress=False)

        sequential_seeds = [(row.task.task_seed, row.solve_result.run_seed) for row in sequential.iter_rows()]
        batch_seeds = [(row.task.task_seed, row.solve_result.run_seed) for row in batch.iter_rows()]
        assert sequential_seeds == batch_seeds
    finally:
        simulator.close()


def test_run_batch_process_worker_uses_snapshot_run_seed(tmp_path: Path) -> None:
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    _write_problem_yaml(problem_root / "mkp" / "WEISH" / "weish01.yaml", problem_id="weish01")
    _write_solver_yaml(solver_root / "stub_solver.yaml", solver_id="stub_solver")

    bank_spec = ExperimentSpec(
        experiment_name="exp_par_rng",
        dataset="WEISH",
        problem_ids=("weish01",),
        solver_ids=("stub_solver",),
        repeat=1,
        worker_count=2,
        base_seed=100,
    )
    bank = _build_problem_bank(problem_root, bank_spec)
    registry = SolverRegistry()
    registry.register("stub_solver", lambda: CountingSolver())
    solver_configs = SolverConfigsSnapshot.build(bank_spec, solver_root)
    simulator = Simulator(
        spec=bank_spec,
        problem_bank=bank,
        solver_registry=registry,
        solver_configs=solver_configs,
        seed_strategy=DerivedPerProblemSeedStrategy(),
        rng_factory=_offset_rng_factory,
    )

    try:
        tasks = simulator.expand_tasks()
        result = simulator.run_batch(show_progress=False)
    finally:
        simulator.close()

    row = result.by_variant[("stub_solver", 0)].rows[0]
    assert row.task == tasks[0]
    assert row.solve_result.run_seed == tasks[0].task_seed


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
    simulator = Simulator(
        spec=bank_spec,
        problem_bank=bank,
        solver_registry=registry,
        solver_configs=solver_configs,
        seed_strategy=DerivedPerProblemSeedStrategy(),
        rng_factory=make_numpy_rng,
    )
    try:
        task = RunTask(
            problem_id="weish01",
            dataset="WEISH",
            solver_id="other_solver",
            repeat_index=0,
            task_seed=1,
            param_set_index=0,
        )
        with pytest.raises(ValueError):
            simulator.run_task(task)
    finally:
        simulator.close()


def test_run_batch_writes_summary_files(tmp_path: Path):
    simulator, output_root = _build_simulator(tmp_path, base_seed=1)

    try:
        result = simulator.run_sequential()

        assert len(result.iter_rows()) == 3
        write_simulator_result(result, experiment_name="exp_batch", output_root=output_root)
        summary_json = output_root / "exp_batch" / "stub_solver" / "param_0" / "summary.json"
        summary_csv = output_root / "exp_batch" / "stub_solver" / "param_0" / "summary.csv"
        assert summary_json.exists()
        assert summary_csv.exists()
    finally:
        simulator.close()
