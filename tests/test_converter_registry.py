from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from mkp.cli.convert import (
    getConverter,
    listConverters,
    main,
    parseCb,
    parseGk,
    parseHp,
    parsePb,
    parsePet,
    parseSent,
    parseWeish,
    register,
)
from mkp.converter import transformToYaml
from mkp.engine.repository import ProblemRepository
from mkp.problem import buildProblemRegistry, problemBuilders


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_weish_dat(path: Path, *, best_known: int = 10) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"3 2 {best_known}\n\n1 2 3\n\n1 1 1\n2 2 2\n\n3 4\n",
        encoding="utf-8",
    )


def test_cli_converter_registry_has_expected_converters():
    assert {"weish", "weing", "pb", "pet", "sent", "hp", "cb", "gk"} <= set(listConverters())


def test_get_unknown_converter_raises():
    with pytest.raises(KeyError):
        getConverter("unknown_converter")


def test_register_duplicate_converter_raises():
    @register("tmp_unique_converter")
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

        @register("tmp_unique_converter")
        def _tmp_parser_dup(_path: Path):
            return {}


def test_converter_core_writes_yaml_and_loads_model(tmp_path: Path):
    _write_weish_dat(tmp_path / "data/WEISH/weish01.dat")

    yaml_path = transformToYaml(
        repo_root=tmp_path,
        dataset="WEISH",
        problem_id="weish01",
        parser=parseWeish,
    )
    assert yaml_path.exists()
    assert "problem_id: weish01" in yaml_path.read_text(encoding="utf-8")

    repository = ProblemRepository(
        config_root=tmp_path / "configs/problems",
        registry=buildProblemRegistry(problemBuilders()),
    )
    model = repository.load("WEISH", "weish01")
    assert model.problem_id == "weish01"
    assert model.items == 3


def test_parse_weish_transposes_weights(tmp_path: Path):
    dat_path = tmp_path / "data/WEISH/weish01.dat"
    _write_weish_dat(dat_path)

    payload = parseWeish(dat_path)

    assert payload["weights"] == [[1, 2], [1, 2], [1, 2]]


@pytest.mark.parametrize(
    ("parser", "relative_path", "expected_items", "expected_dim", "expected_best_known"),
    [
        (parsePb, "data/PB/pb1.dat", 27, 4, 3090),
        (parsePet, "data/PET/pet2.dat", 10, 10, 87061),
        (parseSent, "data/SENT/sent01.dat", 60, 30, 7772),
        (parseHp, "data/HP/hp1.dat", 28, 4, 3418),
        (parseGk, "data/GK/mk_gk01.txt", 100, 15, None),
        (parseCb, "data/OR5x100/OR5x100-0.25_1.dat", 100, 5, None),
        (parseCb, "data/OR5x100/OR5x100-0.50_1.dat", 100, 5, None),
    ],
)
def test_registered_dataset_parsers_read_expected_payloads(
    parser,
    relative_path: str,
    expected_items: int,
    expected_dim: int,
    expected_best_known: int | None,
):
    payload = parser(REPO_ROOT / relative_path)

    assert payload["items"] == expected_items
    assert payload["dim"] == expected_dim
    assert payload["best_known"] == expected_best_known
    assert len(payload["values"]) == expected_items
    assert len(payload["weights"]) == expected_items
    assert len(payload["weights"][0]) == expected_dim
    assert len(payload["capacities"]) == expected_dim


@pytest.mark.parametrize("relative_path", ["data/GK/mk_gk10.txt", "data/GK/mk_gk11.txt"])
def test_gk_parser_accepts_instances_without_best_known(relative_path: str):
    payload = parseGk(REPO_ROOT / relative_path)

    assert payload["best_known"] is None
    assert len(payload["values"]) == payload["items"]
    assert len(payload["weights"]) == payload["items"]
    assert len(payload["weights"][0]) == payload["dim"]
    assert len(payload["capacities"]) == payload["dim"]


def test_get_converter_returns_new_parsers():
    assert getConverter("pb") is parsePb
    assert getConverter("pet") is parsePet
    assert getConverter("sent") is parseSent
    assert getConverter("hp") is parseHp
    assert getConverter("cb") is parseCb
    assert getConverter("gk") is parseGk


def test_convert_cli_converts_dataset_and_overwrites_yaml(tmp_path: Path):
    _write_weish_dat(tmp_path / "data/WEISH/weish01.dat", best_known=10)
    _write_weish_dat(tmp_path / "data/WEISH/weish02.dat", best_known=20)
    old_yaml = tmp_path / "configs/problems/mkp/WEISH/weish01.yaml"
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
        tmp_path / "configs/problems/mkp/WEISH/weish01.yaml",
        tmp_path / "configs/problems/mkp/WEISH/weish02.yaml",
    ]
    repository = ProblemRepository(
        config_root=tmp_path / "configs/problems",
        registry=buildProblemRegistry(problemBuilders()),
    )
    assert repository.load("WEISH", "weish01").best_known == 10
    assert repository.load("WEISH", "weish02").best_known == 20


def test_convert_cli_converts_txt_dataset(tmp_path: Path):
    gk_path = tmp_path / "data/GK/mk_gk01.txt"
    gk_path.parent.mkdir(parents=True, exist_ok=True)
    gk_path.write_text((REPO_ROOT / "data/GK/mk_gk01.txt").read_text(encoding="utf-8"), encoding="utf-8")

    output_paths = main(
        [
            "--dataset",
            "GK",
            "--converter",
            "gk",
            "--repo-root",
            str(tmp_path),
        ]
    )

    assert output_paths == [tmp_path / "configs/problems/mkp/GK/mk_gk01.yaml"]
    yaml = YAML(typ="safe")
    payload = yaml.load(output_paths[0].read_text(encoding="utf-8"))
    assert payload["best_known"] is None


def test_convert_cli_skips_cb_bundle_file(tmp_path: Path):
    data_dir = tmp_path / "data/OR5x100"
    data_dir.mkdir(parents=True, exist_ok=True)
    single_payload = "2 1 0\n5 7\n1 2\n3\n"
    (data_dir / "OR5x100-0.25_1.dat").write_text(single_payload, encoding="utf-8")
    (data_dir / "OR5x100-0.25_2.dat").write_text(single_payload, encoding="utf-8")
    (data_dir / "OR5x100.dat").write_text(f"2\n{single_payload}{single_payload}", encoding="utf-8")

    output_paths = main(
        [
            "--dataset",
            "OR5x100",
            "--converter",
            "cb",
            "--repo-root",
            str(tmp_path),
        ]
    )

    assert output_paths == [
        tmp_path / "configs/problems/mkp/OR5x100/OR5x100-0.25_1.yaml",
        tmp_path / "configs/problems/mkp/OR5x100/OR5x100-0.25_2.yaml",
    ]
    assert not (tmp_path / "configs/problems/mkp/OR5x100/OR5x100.yaml").exists()
