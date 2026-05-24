from __future__ import annotations

import json
from pathlib import Path

import pytest

from mkp.experiment import FAIL, PASS, RoundEvalDecision, RoundEvalInput, build, register
from mkp.experiment.experiment import _clear_registered_evaluators_for_tests


@pytest.fixture(autouse=True)
def _clear_evaluators():
    _clear_registered_evaluators_for_tests()
    yield
    _clear_registered_evaluators_for_tests()


def _write_problem_yaml(path: Path, *, problem_id: str, dataset: str = "DATA") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""
problem_id: {problem_id}
dataset: {dataset}
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


def _write_solver_yaml(path: Path, *, params: str = "  - {}") -> None:
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


def _config_text(
    *,
    collects: int = 1,
    repeat: int = 3,
    datasets: str | None = None,
    solvers: str | None = None,
) -> str:
    dataset_block = datasets or """
  - experiment-id: exp1
    dataset: DATA
    type: mkp
    problems:
      - problem: p1
        evaluation: [custom]
"""
    solver_block = solvers or """
  - solver: stub_solver
    param_idx: [0]
"""
    return f"""
experiment_name: exp_search
collects: {collects}
solvers:
{solver_block.rstrip()}
repeat: {repeat}
dataset_settings:
{dataset_block}
""".strip()


def _project(
    tmp_path: Path,
    *,
    collects: int = 1,
    repeat: int = 3,
    datasets: str | None = None,
    solvers: str | None = None,
    solver_params: str = "  - {}",
):
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    exp_path = tmp_path / "exp_cfg.yaml"
    _write_problem_yaml(problem_root / "mkp" / "DATA" / "p1.yaml", problem_id="p1")
    _write_problem_yaml(problem_root / "mkp" / "DATA" / "p2.yaml", problem_id="p2")
    _write_solver_yaml(solver_root / "stub_solver.yaml", params=solver_params)
    exp_path.write_text(
        _config_text(collects=collects, repeat=repeat, datasets=datasets, solvers=solvers),
        encoding="utf-8",
    )
    return build(exp_path, problem_root=problem_root, solver_root=solver_root), problem_root, solver_root


def test_streaming_scheduler_collects_per_problem_and_discards_failed_rounds(tmp_path: Path) -> None:
    datasets = """
  - experiment-id: exp1
    dataset: DATA
    type: mkp
    problems:
      - problem: p1
        evaluation: [custom]
      - problem: p2
        evaluation: [custom]
"""
    experiment, problem_root, solver_root = _project(
        tmp_path,
        collects=2,
        repeat=4,
        datasets=datasets,
    )
    calls: list[tuple[str, int, int, int]] = []

    def evaluator(input_data: RoundEvalInput) -> RoundEvalDecision:
        calls.append(
            (
                input_data.problem_id,
                input_data.repeat_index,
                len(input_data.simulator_result.iter_rows()),
                len(input_data.projected_result.iter_rows()),
            )
        )
        passed = input_data.repeat_index in {1, 3}
        return RoundEvalDecision(passed=passed, verdict=PASS if passed else FAIL)

    register("custom", evaluator)
    report = experiment.run(
        problem_root=problem_root,
        solver_root=solver_root,
        output_root=tmp_path / "output",
    )

    assert calls == [
        ("p1", 0, 1, 1),
        ("p1", 1, 1, 1),
        ("p1", 2, 1, 2),
        ("p1", 3, 1, 2),
        ("p2", 0, 1, 1),
        ("p2", 1, 1, 1),
        ("p2", 2, 1, 2),
        ("p2", 3, 1, 2),
    ]
    assert [problem.problem_id for problem in report.problems] == ["p1", "p2"]
    assert all(problem.collected_repeat_indices == (1, 3) for problem in report.problems)
    assert all(problem.collected_count == 2 for problem in report.problems)
    assert all(problem.attempted_repeats == 4 for problem in report.problems)

    runs_path = tmp_path / "output" / "exp_search" / "exp1" / "p1" / "stub_solver" / "param_0" / "runs.json"
    rows = json.loads(runs_path.read_text(encoding="utf-8"))
    assert [row["repeat_index"] for row in rows] == [1, 3]
    assert (tmp_path / "output" / "exp_search" / "summary.json").exists()


def test_problem_stops_after_collects_is_reached_and_discards_prefetched_rounds(tmp_path: Path) -> None:
    datasets = """
  - experiment-id: exp1
    dataset: DATA
    type: mkp
    problems:
      - problem: p1
        evaluation: [custom]
      - problem: p2
        evaluation: [custom]
"""
    experiment, problem_root, solver_root = _project(
        tmp_path,
        collects=1,
        repeat=5,
        datasets=datasets,
    )
    calls: list[tuple[str, int]] = []

    def evaluator(input_data: RoundEvalInput) -> RoundEvalDecision:
        calls.append((input_data.problem_id, input_data.repeat_index))
        passed = input_data.repeat_index == 1
        return RoundEvalDecision(passed=passed, verdict=PASS if passed else FAIL)

    register("custom", evaluator)
    report = experiment.run(
        problem_root=problem_root,
        solver_root=solver_root,
        output_root=tmp_path / "output",
    )

    assert calls == [("p1", 0), ("p1", 1), ("p2", 0), ("p2", 1)]
    assert [problem.attempted_repeats for problem in report.problems] == [2, 2]
    rows = json.loads(
        (tmp_path / "output" / "exp_search" / "exp1" / "p1" / "stub_solver" / "param_0" / "runs.json")
        .read_text(encoding="utf-8")
    )
    assert [row["repeat_index"] for row in rows] == [1]


def test_round_seed_is_shared_across_solver_params(tmp_path: Path) -> None:
    experiment, problem_root, solver_root = _project(
        tmp_path,
        collects=1,
        repeat=1,
        solvers="""
  - solver: stub_solver
    param_idx: [0, 1]
""",
        solver_params="  - {z: 0.1}\n  - {z: 0.2}",
    )
    seen_seeds: list[set[int]] = []

    def evaluator(input_data: RoundEvalInput) -> RoundEvalDecision:
        seen_seeds.append({row.task.task_seed for row in input_data.simulator_result.iter_rows()})
        return RoundEvalDecision(passed=True, verdict=PASS)

    register("custom", evaluator)
    experiment.run(
        problem_root=problem_root,
        solver_root=solver_root,
        output_root=tmp_path / "output",
    )

    assert len(seen_seeds) == 1
    assert len(seen_seeds[0]) == 1
    assert len(json.loads((tmp_path / "output" / "exp_search" / "exp1" / "p1" / "stub_solver" / "param_0" / "runs.json").read_text())) == 1
    assert len(json.loads((tmp_path / "output" / "exp_search" / "exp1" / "p1" / "stub_solver" / "param_1" / "runs.json").read_text())) == 1


def test_repeat_limit_fail_fast_when_problem_cannot_collect_enough_rounds(tmp_path: Path) -> None:
    experiment, problem_root, solver_root = _project(tmp_path, collects=2, repeat=2)
    register(
        "custom",
        lambda _input: RoundEvalDecision(passed=False, verdict=FAIL),
    )

    with pytest.raises(RuntimeError, match="collection failed"):
        experiment.run(
            problem_root=problem_root,
            solver_root=solver_root,
            output_root=tmp_path / "output",
        )

    assert not (tmp_path / "output" / "exp_search" / "summary.json").exists()
    assert not (tmp_path / "output" / "exp_search" / "exp1" / "p1").exists()


def test_run_fails_fast_on_unknown_problem_evaluator(tmp_path: Path) -> None:
    experiment, problem_root, solver_root = _project(tmp_path, collects=1, repeat=1)

    with pytest.raises(KeyError, match="unknown evaluator"):
        experiment.run(
            problem_root=problem_root,
            solver_root=solver_root,
            output_root=tmp_path / "output",
        )


def test_process_worker_path_collects_rounds(tmp_path: Path) -> None:
    experiment, problem_root, solver_root = _project(tmp_path, collects=1, repeat=1)
    register(
        "custom",
        lambda _input: RoundEvalDecision(passed=True, verdict=PASS),
    )

    report = experiment.run(
        problem_root=problem_root,
        solver_root=solver_root,
        output_root=tmp_path / "output",
    )

    assert len(report.problems) == 1
    assert report.problems[0].collected_count == 1
    assert (tmp_path / "output" / "exp_search" / "exp1" / "p1" / "stub_solver" / "param_0" / "summary.json").exists()


def test_experiment_prints_collection_status_lines(tmp_path: Path, capsys) -> None:
    datasets = """
  - experiment-id: exp1
    dataset: DATA
    type: mkp
    problems:
      - problem: p1
        evaluation: [custom]
      - problem: p2
        evaluation: [custom]
"""
    experiment, problem_root, solver_root = _project(tmp_path, datasets=datasets)
    register(
        "custom",
        lambda _input: RoundEvalDecision(passed=True, verdict=PASS),
    )

    experiment.run(
        problem_root=problem_root,
        solver_root=solver_root,
        output_root=tmp_path / "output",
    )

    captured = capsys.readouterr()
    assert captured.err.count("step1: collect") == 1
    assert "[exp1] p1: 0/1 p2: 0/1 | remaining: 2" in captured.err
    assert "[exp1] p1: 1/1 p2: 0/1 | remaining: 1" not in captured.err
    assert "[exp1] p1: 1/1 p2: 1/1 | remaining: 0" not in captured.err


def test_experiment_prints_collection_status_every_50_evaluations(tmp_path: Path, capsys) -> None:
    experiment, problem_root, solver_root = _project(tmp_path, collects=55, repeat=55)
    register(
        "custom",
        lambda _input: RoundEvalDecision(passed=True, verdict=PASS),
    )

    experiment.run(
        problem_root=problem_root,
        solver_root=solver_root,
        output_root=tmp_path / "output",
    )

    captured = capsys.readouterr()
    assert captured.err.count("step1: collect") == 1
    assert "[exp1] p1: 0/55 | remaining: 55" in captured.err
    assert "[exp1] p1: 50/55 | remaining: 5" in captured.err
    assert "[exp1] p1: 55/55 | remaining: 0" not in captured.err
