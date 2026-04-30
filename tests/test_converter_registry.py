from __future__ import annotations

from pathlib import Path

import pytest

from mkp.cli.convert import get_converter, list_converters, main, register_converter
from mkp.converter import ensure_problem_yaml_from_dat, load_problem_model_from_repo_dat, parse_weish_dat
from mkp.engine.repository import ProblemRepository


def _write_weish_dat(path: Path, *, best_known: int = 10) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"3 2 {best_known}\n\n1 2 3\n\n1 1 1\n2 2 2\n\n3 4\n",
        encoding="utf-8",
    )


def test_cli_converter_registry_has_weish():
    assert "weish" in set(list_converters())


def test_get_unknown_converter_raises():
    with pytest.raises(KeyError):
        get_converter("unknown_converter")


def test_register_duplicate_converter_raises():
    @register_converter("tmp_unique_converter")
    def _tmp_parser(_path: Path):
        return {
            "items": 1,
            "dim": 1,
            "best_known": 1,
            "values": [1],
            "weights": [[1]],
            "capacities": [1],
        }

    with pytest.raises(ValueError):

        @register_converter("tmp_unique_converter")
        def _tmp_parser_dup(_path: Path):
            return {}


def test_converter_core_writes_yaml_and_loads_model(tmp_path: Path):
    _write_weish_dat(tmp_path / "data/WEISH/weish01.dat")

    yaml_path = ensure_problem_yaml_from_dat(
        repo_root=tmp_path,
        dataset="WEISH",
        problem_id="weish01",
    )
    assert yaml_path.exists()
    assert "problem_id: weish01" in yaml_path.read_text(encoding="utf-8")

    model = load_problem_model_from_repo_dat(
        repo_root=tmp_path,
        dataset="WEISH",
        problem_id="weish01",
    )
    assert model.problem_id == "weish01"
    assert model.items == 3


def test_parse_weish_dat_transposes_weights(tmp_path: Path):
    dat_path = tmp_path / "data/WEISH/weish01.dat"
    _write_weish_dat(dat_path)

    payload = parse_weish_dat(dat_path)

    assert payload["weights"] == [[1, 2], [1, 2], [1, 2]]


def test_convert_cli_converts_dataset_and_overwrites_yaml(tmp_path: Path):
    _write_weish_dat(tmp_path / "data/WEISH/weish01.dat", best_known=10)
    _write_weish_dat(tmp_path / "data/WEISH/weish02.dat", best_known=20)
    old_yaml = tmp_path / "configs/problems/WEISH/weish01.yaml"
    old_yaml.parent.mkdir(parents=True, exist_ok=True)
    old_yaml.write_text("problem_id: old\n", encoding="utf-8")

    output_paths = main(
        [
            "--dataset",
            "WEISH",
            "--converter",
            "weish",
            "--repo-root",
            str(tmp_path),
        ]
    )

    assert output_paths == [
        tmp_path / "configs/problems/WEISH/weish01.yaml",
        tmp_path / "configs/problems/WEISH/weish02.yaml",
    ]
    repository = ProblemRepository(config_root=tmp_path / "configs/problems")
    assert repository.load("WEISH", "weish01").best_known == 10
    assert repository.load("WEISH", "weish02").best_known == 20
