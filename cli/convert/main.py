from __future__ import annotations

import argparse
from pathlib import Path

from ...converter import ensure_problem_yaml_from_dat
from .register import get_converter, list_converters


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert MKP raw dataset files into problem YAML files.")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--converter", required=True, choices=list_converters())
    parser.add_argument("--repo-root", default=".")
    return parser


def main(argv: list[str] | None = None) -> list[Path]:
    parser = build_parser()
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root)
    dataset = str(args.dataset).strip()
    if not dataset:
        raise ValueError("--dataset must be a non-empty string.")

    data_dir = repo_root / "data" / dataset
    if not data_dir.is_dir():
        raise FileNotFoundError(f"Dataset directory not found: {data_dir}")

    source_paths = sorted(data_dir.glob("*.dat"))
    if not source_paths:
        raise FileNotFoundError(f"No .dat files found in dataset directory: {data_dir}")

    converter = get_converter(args.converter)
    output_paths: list[Path] = []
    for source_path in source_paths:
        output_paths.append(
            ensure_problem_yaml_from_dat(
                repo_root=repo_root,
                dataset=dataset,
                problem_id=source_path.stem,
                parser=converter,
            )
        )

    for output_path in output_paths:
        print(output_path)
    return output_paths
