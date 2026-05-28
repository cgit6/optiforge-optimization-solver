from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ...engine import Engine, SolverConfigsSnapshot
from ...engine.models import ExperimentSpec, RunTask
from ...experiment.seed_bank import load_seed_bank, matching_problem_entries, variant_config
from ...machine import MachinePool, MachineResult, SimulatorRunRow
from ...rng import DerivedPerProblemSeedStrategy
from ...simulator import SimulatorResult
from ...tools.show import write_simulator_result


def parser() -> argparse.ArgumentParser:
    arg_parser = argparse.ArgumentParser(description="Replay accepted runs from seed_bank.json.")
    arg_parser.add_argument("--seed-bank", required=True, type=Path)
    arg_parser.add_argument("--solver", required=True)
    arg_parser.add_argument("--set", required=True, type=int, dest="param_set_index", help="0-based solver params index")
    arg_parser.add_argument("--experiment-name", default=None)
    arg_parser.add_argument("--worker", default=1, type=int, dest="worker_count")
    return arg_parser


build_parser = parser


def main(
    argv: list[str] | None = None,
    *,
    problem_root: Path | str = Path("configs/problems"),
    output_root: Path | str = Path("output"),
) -> SimulatorResult:
    args = parser().parse_args(argv)
    return replay_seed_bank(
        seed_bank_path=args.seed_bank,
        solver_id=str(args.solver).strip(),
        param_set_index=int(args.param_set_index),
        experiment_name=args.experiment_name,
        worker_count=int(args.worker_count),
        problem_root=Path(problem_root),
        output_root=Path(output_root),
    )


def replay_seed_bank(
    *,
    seed_bank_path: Path,
    solver_id: str,
    param_set_index: int,
    experiment_name: str | None,
    worker_count: int,
    problem_root: Path,
    output_root: Path,
) -> SimulatorResult:
    if param_set_index < 0:
        raise ValueError("--set must be >= 0")
    if worker_count <= 0:
        raise ValueError("worker_count must be > 0.")
    payload = load_seed_bank(seed_bank_path)
    try:
        config = variant_config(payload, solver_id=solver_id, param_set_index=param_set_index)
    except KeyError as exc:
        raise ValueError(str(exc)) from exc
    problems = matching_problem_entries(payload, solver_id=solver_id, param_set_index=param_set_index)
    if not problems:
        raise ValueError(
            "seed_bank contains no replayable problems for "
            f"solver={solver_id!r} param_set_index={param_set_index!r}."
        )

    rows: list[SimulatorRunRow] = []
    for group in _group_problem_entries(problems):
        rows.extend(
            _run_replay_group(
                group,
                config=config,
                solver_id=solver_id,
                param_set_index=param_set_index,
                worker_count=worker_count,
                problem_root=problem_root,
            )
        )

    result = SimulatorResult(
        machine_results=(
            MachineResult(
                solver_id=solver_id,
                param_set_index=param_set_index,
                params=dict(config["params"]),
                rows=tuple(rows),
            ),
        )
    )
    write_simulator_result(
        result,
        experiment_name=experiment_name or f"{seed_bank_path.stem}_replay",
        output_root=output_root,
        variant_metadata={
            (solver_id, param_set_index): {
                "seed_bank": str(seed_bank_path),
                "source": dict(payload.get("source", {})),
            }
        },
    )
    return result


def _group_problem_entries(problems: tuple[dict[str, Any], ...]) -> tuple[tuple[dict[str, Any], ...], ...]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for problem in problems:
        key = (str(problem["dataset"]), str(problem["problem_type"]))
        grouped.setdefault(key, []).append(problem)
    return tuple(tuple(entries) for entries in grouped.values())


def _run_replay_group(
    problem_entries: tuple[dict[str, Any], ...],
    *,
    config: dict[str, Any],
    solver_id: str,
    param_set_index: int,
    worker_count: int,
    problem_root: Path,
) -> tuple[SimulatorRunRow, ...]:
    dataset = str(problem_entries[0]["dataset"])
    problem_type = str(problem_entries[0]["problem_type"])
    repeat = max(len(entry["run_seeds"]) for entry in problem_entries)
    spec = ExperimentSpec(
        experiment_name="seed_bank_replay",
        dataset=dataset,
        problem_ids=tuple(str(entry["problem_id"]) for entry in problem_entries),
        solver_ids=(solver_id,),
        repeat=repeat,
        worker_count=worker_count,
        problem_type=problem_type,
        base_seed=0,
    )
    bundle = Engine.build(
        spec=spec,
        problem_root=problem_root,
        solver_root=Path("configs/solvers"),
        seed_strategy=DerivedPerProblemSeedStrategy(),
        solver_configs=SolverConfigsSnapshot.from_configs((config,)),
    )
    sim = bundle.new_simulator()
    try:
        tasks = [
            RunTask(
                problem_id=str(entry["problem_id"]),
                dataset=dataset,
                problem_type=problem_type,
                solver_id=solver_id,
                repeat_index=repeat_index,
                task_seed=int(seed),
                param_set_index=param_set_index,
            )
            for entry in problem_entries
            for repeat_index, seed in enumerate(entry["run_seeds"])
        ]
        pool = MachinePool(sim.machines, worker_count=worker_count)
        machine_results = pool.run_tasks(tasks)
        return tuple(row for machine_result in machine_results for row in machine_result.rows)
    finally:
        sim.close()
