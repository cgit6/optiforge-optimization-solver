from __future__ import annotations

from pathlib import Path

import pytest

from mkp.converter import (
    ensure_problem_yaml_from_dat,
    get_converter,
    list_converters,
    load_problem_model_from_repo_dat,
    register_converter,
)


def test_default_converters_registered():
    names = set(list_converters())
    assert "mkp_dat_v1" in names
    assert "weish_dat" in names
    assert "weing_dat" in names


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


def test_converter_name_can_be_selected(tmp_path: Path):
    dat_dir = tmp_path / "data/WEISH"
    dat_dir.mkdir(parents=True, exist_ok=True)
    (dat_dir / "weish01.dat").write_text(
        "3 2 10\n\n1 2 3\n\n1 1 1\n2 2 2\n\n3 4\n",
        encoding="utf-8",
    )

    yaml_path = ensure_problem_yaml_from_dat(
        repo_root=tmp_path,
        dataset="WEISH",
        problem_id="weish01",
        converter_name="weish_dat",
    )
    assert yaml_path.exists()

    model = load_problem_model_from_repo_dat(
        repo_root=tmp_path,
        dataset="WEISH",
        problem_id="weish01",
        converter_name="weish_dat",
    )
    assert model.problem_id == "weish01"
    assert model.items == 3
