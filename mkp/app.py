from __future__ import annotations

import argparse
from pathlib import Path

from .contracts import ExperimentSpec
from .problem_repository import ProblemRepository
from .result_writer import ResultWriter
from .simulator import Simulator
from .bsma_v1_008_solver import BSMAV1008Solver
from .solver_config_loader import SolverConfigLoader
from .solver_registry import SolverRegistry, StubMaxIterationsSolver
from .validator import Validator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run MKP simulation batch.")
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--problems", required=True, help="Comma-separated problem ids")
    parser.add_argument("--solvers", required=True, help="Comma-separated solver ids")
    parser.add_argument("--repeat", required=True, type=int)
    parser.add_argument("--base-seed", required=True, type=int)
    parser.add_argument("--output-dir", required=True)
    return parser


def _split_csv_values(raw: str) -> tuple[str, ...]:
    values = tuple(part.strip() for part in raw.split(",") if part.strip())
    if not values:
        raise ValueError("CSV argument cannot be empty.")
    return values


def create_experiment_spec(args: argparse.Namespace) -> ExperimentSpec:
    problem_ids = _split_csv_values(args.problems)
    solver_ids = _split_csv_values(args.solvers)
    output_base = Path(args.output_dir)
    output_dir = output_base / args.experiment_id
    return ExperimentSpec(
        experiment_id=args.experiment_id,
        dataset=args.dataset,
        problem_ids=problem_ids,
        solver_ids=solver_ids,
        repeat=args.repeat,
        base_seed=args.base_seed,
        output_dir=output_dir,
        benchmark_enabled=False,
    )


def preflight_validate(spec: ExperimentSpec, problem_root: Path, solver_root: Path) -> None:
    missing_problem_paths = [
        problem_root / spec.dataset / f"{problem_id}.yaml"
        for problem_id in spec.problem_ids
        if not (problem_root / spec.dataset / f"{problem_id}.yaml").exists()
    ]
    if missing_problem_paths:
        missing = ", ".join(str(path) for path in missing_problem_paths)
        raise FileNotFoundError(f"Missing problem YAML file(s): {missing}")

    missing_solver_paths = [
        solver_root / f"{solver_id}.yaml"
        for solver_id in spec.solver_ids
        if not (solver_root / f"{solver_id}.yaml").exists()
    ]
    if missing_solver_paths:
        missing = ", ".join(str(path) for path in missing_solver_paths)
        raise FileNotFoundError(f"Missing solver YAML file(s): {missing}")


def build_simulator(
    *,
    spec: ExperimentSpec,
    problem_root: Path,
    solver_root: Path,
    output_root: Path,
) -> Simulator:
    problem_repository = ProblemRepository(config_root=problem_root)
    solver_registry = SolverRegistry()
    solver_registry.register("stub_solver", lambda: StubMaxIterationsSolver())
    solver_registry.register("bsma_v1_008", lambda: BSMAV1008Solver())
    solver_config_loader = SolverConfigLoader(config_root=solver_root)
    validator = Validator()
    result_writer = ResultWriter(experiment_id=spec.experiment_id, output_root=output_root)
    return Simulator(
        problem_repository=problem_repository,
        solver_registry=solver_registry,
        solver_config_loader=solver_config_loader,
        validator=validator,
        result_writer=result_writer,
    )


def main(
    argv: list[str] | None = None,
    *,
    problem_root: Path | str = Path("mkp/configs/problems"),
    solver_root: Path | str = Path("mkp/configs/solvers"),
) -> list[tuple]:
    parser = build_parser()
    args = parser.parse_args(argv)
    spec = create_experiment_spec(args)

    problem_root_path = Path(problem_root)
    solver_root_path = Path(solver_root)
    output_root_path = Path(args.output_dir)
    preflight_validate(spec, problem_root_path, solver_root_path)

    simulator = build_simulator(
        spec=spec,
        problem_root=problem_root_path,
        solver_root=solver_root_path,
        output_root=output_root_path,
    )
    return simulator.run_batch(spec)


if __name__ == "__main__":
    main()
