from __future__ import annotations

import json
from pathlib import Path

import pytest

from mkp.cli.replay import main as replay_main
from mkp.experiment import PASS, RoundEvalDecision, build, register
from mkp.experiment.experiment import _clear_registered_evaluators_for_tests


@pytest.fixture(autouse=True)
def _clear_evaluators():
    _clear_registered_evaluators_for_tests()
    yield
    _clear_registered_evaluators_for_tests()


def _write_problem_yaml(path: Path, *, problem_id: str = "p1") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""
problem_id: {problem_id}
dataset: DATA
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


def _write_solver_yaml(path: Path, *, params: str = "  - {index: 0}") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""
solver_id: stub_solver
solver_class: StubMaxIterationsSolver
capabilities:
  problem_types: [mkp]
  encodings: [binary]
  directions: [max]
stop_condition:
  type: max_iterations
  max_iterations: 2
params:
{params}
""".strip(),
        encoding="utf-8",
    )


def _write_exp_yaml(path: Path) -> None:
    path.write_text(
        """
experiment_name: exp_search
collects: 2
solvers:
  - solver: stub_solver
    param_idx: [0]
repeat: 2
dataset_settings:
  - experiment-id: exp1
    dataset: DATA
    type: mkp
    problems:
      - problem: p1
        evaluation: [custom]
""".strip(),
        encoding="utf-8",
    )


def _run_experiment(tmp_path: Path) -> tuple[Path, Path, Path]:
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    output_root = tmp_path / "output"
    exp_path = tmp_path / "exp_cfg.yaml"
    _write_problem_yaml(problem_root / "mkp" / "DATA" / "p1.yaml")
    _write_solver_yaml(solver_root / "stub_solver.yaml")
    _write_exp_yaml(exp_path)
    register("custom", lambda _input: RoundEvalDecision(passed=True, verdict=PASS))

    experiment = build(exp_path, problem_root=problem_root, solver_root=solver_root)
    experiment.run(problem_root=problem_root, solver_root=solver_root, output_root=output_root)
    return problem_root, solver_root, output_root


def test_exp_writes_seed_bank_with_problem_seeds_and_variant_snapshot(tmp_path: Path) -> None:
    _problem_root, _solver_root, output_root = _run_experiment(tmp_path)

    payload = json.loads((output_root / "exp_search" / "seed_bank.json").read_text(encoding="utf-8"))

    assert payload["version"] == 1
    assert payload["source"]["experiment_name"] == "exp_search"
    assert set(payload["variants"]) == {"stub_solver:0"}
    assert payload["variants"]["stub_solver:0"]["params"] == {"index": 0}
    assert payload["problems"] == [
        {
            "dataset_experiment_id": "exp1",
            "dataset": "DATA",
            "problem_type": "mkp",
            "problem_id": "p1",
            "collected_repeat_indices": [0, 1],
            "run_seeds": payload["problems"][0]["run_seeds"],
            "variants": ["stub_solver:0"],
        }
    ]
    assert len(payload["problems"][0]["run_seeds"]) == 2


def test_replay_uses_seed_bank_solver_config_snapshot_not_current_yaml(tmp_path: Path) -> None:
    problem_root, solver_root, output_root = _run_experiment(tmp_path)
    seed_bank = output_root / "exp_search" / "seed_bank.json"
    _write_solver_yaml(solver_root / "stub_solver.yaml", params="  - {index: 99}")

    result = replay_main(
        [
            "--seed-bank",
            str(seed_bank),
            "--solver",
            "stub_solver",
            "--set",
            "0",
            "--experiment-name",
            "replay_exp",
        ],
        problem_root=problem_root,
        output_root=output_root,
    )

    rows = result.iter_rows()
    assert len(rows) == 2
    assert [row.task.repeat_index for row in rows] == [0, 1]
    replay_summary = json.loads(
        (output_root / "replay_exp" / "stub_solver" / "param_0" / "summary.json").read_text(encoding="utf-8")
    )
    assert replay_summary["overall"]["meta"]["params"] == {"index": 0}


def test_replay_fails_for_unrecorded_solver_variant(tmp_path: Path) -> None:
    problem_root, _solver_root, output_root = _run_experiment(tmp_path)

    with pytest.raises(ValueError, match="does not contain solver variant"):
        replay_main(
            [
                "--seed-bank",
                str(output_root / "exp_search" / "seed_bank.json"),
                "--solver",
                "stub_solver",
                "--set",
                "1",
            ],
            problem_root=problem_root,
            output_root=output_root,
        )
