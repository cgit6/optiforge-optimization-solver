from __future__ import annotations

import argparse
from pathlib import Path

from tqdm import tqdm

from ...converter import getConverter, listConverters, transformToYaml


def _is_cb_bundle_file(*, dataset: str, converter_key: str, source_path: Path) -> bool:
    return converter_key == "cb" and source_path.suffix == ".dat" and source_path.stem.lower() == dataset.lower()


# 命令行解析器
def build() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert MKP raw dataset files into problem YAML files.")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--converter", required=True, choices=listConverters())
    parser.add_argument("--repo-root", default=".")
    return parser


def main(argv: list[str] | None = None) -> list[Path]:

    # 1. 解析命令
    parser = build() # 命令行解析器
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root)
    dataset = str(args.dataset).strip()
    if not dataset:
        raise ValueError("--dataset must be a non-empty string.")

    data_dir = repo_root / "data" / dataset
    if not data_dir.is_dir():
        raise FileNotFoundError(f"Dataset directory not found: {data_dir}")

    converter_key = str(args.converter).strip()
    source_paths = [
        source_path
        for source_path in sorted([*data_dir.glob("*.dat"), *data_dir.glob("*.txt")])
        if not _is_cb_bundle_file(dataset=dataset, converter_key=converter_key, source_path=source_path)
    ]
    if not source_paths:
        raise FileNotFoundError(f"No .dat or .txt files found in dataset directory: {data_dir}")

    converter = getConverter(converter_key)
    output_paths: list[Path] = []
    for source_path in tqdm(source_paths, desc=f"Converting {dataset}", unit="file", dynamic_ncols=True):
        output_paths.append(
            transformToYaml(
                repo_root=repo_root,
                dataset=dataset,
                problem_id=source_path.stem,
                parser=converter,
                source_path=source_path,
            )
        )

    return output_paths
