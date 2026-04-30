from __future__ import annotations

import argparse
from pathlib import Path

from ...engine.models import ExperimentSpec
from .support import executeSimulator, preflight_validate, build_parser, create_experiment_spec

def main(
    argv: list[str] | None = None,
    *,
    problem_root: Path | str = Path("configs/problems"),
    solver_root: Path | str = Path("configs/solvers"),
) -> list[tuple]:
    parser = build_parser()
    args = parser.parse_args(argv)
    spec = create_experiment_spec(args)
    output_root_path = Path(args.output_dir)
    return executeSimulator(
        spec=spec,
        problem_root=Path(problem_root),
        solver_root=Path(solver_root),
        output_root=output_root_path,
    )
