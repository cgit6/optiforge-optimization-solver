
from __future__ import annotations

import argparse
from pathlib import Path

from ...experiment import ExperimentReport, build


def parser() -> argparse.ArgumentParser:
    arg_parser = argparse.ArgumentParser(description="Run an experiment config.")
    arg_parser.add_argument("--config", default="cli/exp/exp_cfg.yaml")
    arg_parser.add_argument("--problem-root", default="configs/problems")
    arg_parser.add_argument("--solver-root", default="configs/solvers")
    arg_parser.add_argument("--output-root", default="output")
    arg_parser.add_argument("--eval", default="literature_mkp")
    return arg_parser


def main(argv: list[str] | None = None) -> ExperimentReport:
    args = parser().parse_args(argv)
    experiment = build(
        Path(args.config),
        problem_root=Path(args.problem_root),
        solver_root=Path(args.solver_root),
    )
    return experiment.run(
        eval_name=args.eval,
        problem_root=Path(args.problem_root),
        solver_root=Path(args.solver_root),
        output_root=Path(args.output_root),
    )


if __name__ == "__main__":
    main()
