from __future__ import annotations

from pathlib import Path

import pytest

from mkp.cli.exp import main as exp_cli_main
from mkp.experiment import Experiment, ExperimentReport, build, load_config


def _write_problem_yaml(path: Path, *, problem_id: str = "p1", dataset: str = "DATA") -> None:
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


def _write_solver_yaml(
    path: Path,
    *,
    solver_id: str = "stub_solver",
    problem_types: tuple[str, ...] = ("mkp",),
    encodings: tuple[str, ...] = ("binary",),
    directions: tuple[str, ...] = ("max",),
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""
solver_id: {solver_id}
solver_class: StubMaxIterationsSolver
capabilities:
  problem_types: [{", ".join(problem_types)}]
  encodings: [{", ".join(encodings)}]
  directions: [{", ".join(directions)}]
stop_condition:
  type: max_iterations
  max_iterations: 10
params:
  - {{}}
""".strip(),
        encoding="utf-8",
    )


def _valid_config_text(
    *,
    experiment_name: str = "exp_search",
    seed: str = "[1, 3]",
    collects: str = "1",
    solvers: str = "[stub_solver]",
    worker: str = "1",
    repeat: str = "2",
    dataset_key: str = "dataset_settings",
    output_line: str = "",
    stages: str | None = None,
    static_baselines: str = "static_baselines: []",
    experiment_id: str = "exp1",
    problems: str = "[p1]",
    base_line: str | None = """
    base_line:
      - problem: p1
        avg: 10
        best: 20
        PDev: 0
""",
) -> str:
    stage_text = stages or """
stages:
  transfer:
    variants:
      - combo_id: transfer_stub_v
        solver: stub_solver
        param_set_index: 0
        algorithm: HSMSCA
        transfer_type: V
  param:
    variants:
      - combo_id: param_stub
        solver: stub_solver
        param_set_index: 0
        algorithm: HSMSCA
  final:
    variants:
      - combo_id: final_stub
        solver: stub_solver
        param_set_index: 0
        algorithm: HSMSCA
"""
    return f"""
experiment_name: {experiment_name}
seed: {seed}
collects: {collects}
solvers: {solvers}
worker: {worker}
{output_line}repeat: {repeat}
evaluation:
  pdev_tolerance: 0.005
  alpha: 0.05
  target_algorithm: HSMSCA
{stage_text}
{static_baselines}
{dataset_key}:
  - experiment-id: {experiment_id}
    dataset: DATA
    problems: {problems}
    type: mkp
{base_line or ""}
""".strip()


def _write_valid_project(tmp_path: Path, *, config_text: str | None = None) -> tuple[Path, Path, Path]:
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    exp_path = tmp_path / "exp_cfg.yaml"
    _write_problem_yaml(problem_root / "DATA" / "p1.yaml")
    _write_solver_yaml(solver_root / "stub_solver.yaml")
    exp_path.write_text(config_text or _valid_config_text(), encoding="utf-8")
    return exp_path, problem_root, solver_root


def test_build_sample_exp_cfg_success() -> None:
    experiment = build(Path("cli/exp/exp_cfg.yaml"))

    assert isinstance(experiment, Experiment)
    assert experiment.cfg.experiment_name == "literature_mkp_seed_search"
    assert experiment.cfg.seed_range == (1, 1000000)
    assert experiment.cfg.collects == 20
    assert experiment.cfg.repeat == 20
    assert experiment.cfg.worker_count == 1
    assert experiment.cfg.solver_ids == ("bsma_numba", "bsca_numba", "brlsmasca_numba")
    assert {stage.name for stage in experiment.cfg.stages} == {"transfer", "param", "final"}
    assert len(experiment.cfg.dataset_settings) == 8
    first = experiment.cfg.dataset_settings[0]
    assert first.experiment_id == "weish-expTest"
    assert first.dataset == "WEISH"
    assert first.problem_type == "mkp"
    assert len(first.problem_ids) == 30
    assert first.base_line[0].problem == "weish01"
    assert first.base_line[0].pdev == 0.0


def test_cli_exp_main_runs_experiment(tmp_path: Path) -> None:
    exp_path, problem_root, solver_root = _write_valid_project(tmp_path)

    report = exp_cli_main(
        [
            "--config",
            str(exp_path),
            "--problem-root",
            str(problem_root),
            "--solver-root",
            str(solver_root),
            "--output-root",
            str(tmp_path / "output"),
        ]
    )

    assert isinstance(report, ExperimentReport)
    assert report.experiment_name == "exp_search"
    assert (tmp_path / "output" / "exp_search" / "summary.json").exists()


def test_load_config_rejects_old_dataset_settings_key(tmp_path: Path) -> None:
    exp_path, problem_root, solver_root = _write_valid_project(
        tmp_path,
        config_text=_valid_config_text(dataset_key="dataset-settings"),
    )

    with pytest.raises(ValueError, match="missing required key"):
        load_config(exp_path, problem_root=problem_root, solver_root=solver_root)


def test_load_config_rejects_removed_output_key(tmp_path: Path) -> None:
    exp_path, problem_root, solver_root = _write_valid_project(
        tmp_path,
        config_text=_valid_config_text(output_line="output: [stub_solver]\n"),
    )

    with pytest.raises(ValueError, match="unknown key"):
        load_config(exp_path, problem_root=problem_root, solver_root=solver_root)


def test_load_config_rejects_missing_solver_yaml(tmp_path: Path) -> None:
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    exp_path = tmp_path / "exp_cfg.yaml"
    _write_problem_yaml(problem_root / "DATA" / "p1.yaml")
    exp_path.write_text(_valid_config_text(solvers="[bscasma_numba]"), encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="Solver config YAML not found"):
        load_config(exp_path, problem_root=problem_root, solver_root=solver_root)


@pytest.mark.parametrize(
    ("config_text", "error_match"),
    [
        (_valid_config_text(seed="[3, 1]"), "seed start"),
        (_valid_config_text(seed="[true, 3]"), "seed\\[0\\]"),
        (_valid_config_text(collects="0"), "collects"),
        (_valid_config_text(worker="0"), "worker"),
        (_valid_config_text(repeat="0"), "repeat"),
        (_valid_config_text(solvers="[]"), "solvers"),
        (_valid_config_text(solvers="[stub_solver, stub_solver]"), "duplicate"),
        (_valid_config_text(problems="[p1, p1]"), "duplicate"),
    ],
)
def test_load_config_rejects_invalid_core_fields(
    tmp_path: Path,
    config_text: str,
    error_match: str,
) -> None:
    exp_path, problem_root, solver_root = _write_valid_project(tmp_path, config_text=config_text)

    with pytest.raises(ValueError, match=error_match):
        load_config(exp_path, problem_root=problem_root, solver_root=solver_root)


def test_load_config_rejects_missing_experiment_name(tmp_path: Path) -> None:
    exp_path, problem_root, solver_root = _write_valid_project(
        tmp_path,
        config_text=_valid_config_text().replace("experiment_name: exp_search\n", ""),
    )

    with pytest.raises(ValueError, match="experiment_name"):
        load_config(exp_path, problem_root=problem_root, solver_root=solver_root)


def test_load_config_rejects_missing_required_stage(tmp_path: Path) -> None:
    stages = """
stages:
  transfer:
    variants:
      - combo_id: transfer_stub_v
        solver: stub_solver
        param_set_index: 0
        algorithm: HSMSCA
        transfer_type: V
  final:
    variants:
      - combo_id: final_stub
        solver: stub_solver
        param_set_index: 0
        algorithm: HSMSCA
"""
    exp_path, problem_root, solver_root = _write_valid_project(
        tmp_path,
        config_text=_valid_config_text(stages=stages),
    )

    with pytest.raises(ValueError, match="missing required stage"):
        load_config(exp_path, problem_root=problem_root, solver_root=solver_root)


def test_load_config_rejects_variant_param_out_of_range(tmp_path: Path) -> None:
    stages = """
stages:
  transfer:
    variants:
      - combo_id: transfer_stub_v
        solver: stub_solver
        param_set_index: 9
        algorithm: HSMSCA
        transfer_type: V
  param:
    variants:
      - combo_id: param_stub
        solver: stub_solver
        param_set_index: 0
        algorithm: HSMSCA
  final:
    variants:
      - combo_id: final_stub
        solver: stub_solver
        param_set_index: 0
        algorithm: HSMSCA
"""
    exp_path, problem_root, solver_root = _write_valid_project(
        tmp_path,
        config_text=_valid_config_text(stages=stages),
    )

    with pytest.raises(ValueError, match="out of range"):
        load_config(exp_path, problem_root=problem_root, solver_root=solver_root)


def test_load_config_rejects_duplicate_combo_id(tmp_path: Path) -> None:
    stages = """
stages:
  transfer:
    variants:
      - combo_id: duplicate_combo
        solver: stub_solver
        param_set_index: 0
        algorithm: HSMSCA
        transfer_type: V
  param:
    variants:
      - combo_id: duplicate_combo
        solver: stub_solver
        param_set_index: 0
        algorithm: HSMSCA
  final:
    variants:
      - combo_id: final_stub
        solver: stub_solver
        param_set_index: 0
        algorithm: HSMSCA
"""
    exp_path, problem_root, solver_root = _write_valid_project(
        tmp_path,
        config_text=_valid_config_text(stages=stages),
    )

    with pytest.raises(ValueError, match="duplicated"):
        load_config(exp_path, problem_root=problem_root, solver_root=solver_root)


def test_load_config_rejects_static_baseline_problem_not_in_dataset_settings(tmp_path: Path) -> None:
    static_baselines = """
static_baselines:
  - combo_id: literature_hlms
    algorithm: HLMS
    results:
      - dataset: DATA
        problem: missing
        avg: 49
        best: 50
        PDev: 2
"""
    exp_path, problem_root, solver_root = _write_valid_project(
        tmp_path,
        config_text=_valid_config_text(static_baselines=static_baselines),
    )

    with pytest.raises(ValueError, match="not listed in dataset_settings"):
        load_config(exp_path, problem_root=problem_root, solver_root=solver_root)


def test_load_config_accepts_static_baseline_problem_without_dataset_when_unambiguous(tmp_path: Path) -> None:
    static_baselines = """
static_baselines:
  - combo_id: literature_hlms
    algorithm: HLMS
    results:
      - problem: p1
        avg: 49
        best: 50
        PDev: 2
"""
    exp_path, problem_root, solver_root = _write_valid_project(
        tmp_path,
        config_text=_valid_config_text(static_baselines=static_baselines),
    )

    cfg = load_config(exp_path, problem_root=problem_root, solver_root=solver_root)

    assert cfg.static_baselines[0].results[0].dataset == "DATA"


def test_load_config_rejects_duplicate_experiment_id(tmp_path: Path) -> None:
    settings = _valid_config_text(base_line=None) + """
  - experiment-id: exp1
    dataset: DATA
    problems: [p1]
    type: mkp
"""
    exp_path, problem_root, solver_root = _write_valid_project(tmp_path, config_text=settings)

    with pytest.raises(ValueError, match="experiment-id is duplicated"):
        load_config(exp_path, problem_root=problem_root, solver_root=solver_root)


def test_load_config_rejects_missing_problem_yaml(tmp_path: Path) -> None:
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    exp_path = tmp_path / "exp_cfg.yaml"
    _write_solver_yaml(solver_root / "stub_solver.yaml")
    exp_path.write_text(_valid_config_text(problems="[missing]"), encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="Problem YAML not found"):
        load_config(exp_path, problem_root=problem_root, solver_root=solver_root)


def test_load_config_rejects_base_line_problem_not_in_problems(tmp_path: Path) -> None:
    config_text = _valid_config_text(
        base_line="""
    base_line:
      - problem: missing
        avg: 10
        best: 20
        PDev: 0
"""
    )
    exp_path, problem_root, solver_root = _write_valid_project(tmp_path, config_text=config_text)

    with pytest.raises(ValueError, match="not listed in problems"):
        load_config(exp_path, problem_root=problem_root, solver_root=solver_root)


def test_load_config_rejects_duplicate_base_line_problem(tmp_path: Path) -> None:
    config_text = _valid_config_text(
        base_line="""
    base_line:
      - problem: p1
        avg: 10
        best: 20
        PDev: 0
      - problem: p1
        avg: 11
        best: 20
        PDev: 1
"""
    )
    exp_path, problem_root, solver_root = _write_valid_project(tmp_path, config_text=config_text)

    with pytest.raises(ValueError, match="duplicated"):
        load_config(exp_path, problem_root=problem_root, solver_root=solver_root)


@pytest.mark.parametrize(
    ("base_line", "error_match"),
    [
        (
            """
    base_line:
      - problem: p1
        avg: bad
        best: 20
        PDev: 0
""",
            "avg",
        ),
        (
            """
    base_line:
      - problem: p1
        avg: 10
        best: 20
        PDev: -1
""",
            "PDev",
        ),
    ],
)
def test_load_config_rejects_invalid_base_line_numbers(
    tmp_path: Path,
    base_line: str,
    error_match: str,
) -> None:
    exp_path, problem_root, solver_root = _write_valid_project(
        tmp_path,
        config_text=_valid_config_text(base_line=base_line),
    )

    with pytest.raises(ValueError, match=error_match):
        load_config(exp_path, problem_root=problem_root, solver_root=solver_root)


def test_load_config_rejects_solver_problem_capability_mismatch(tmp_path: Path) -> None:
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    exp_path = tmp_path / "exp_cfg.yaml"
    _write_problem_yaml(problem_root / "DATA" / "p1.yaml")
    _write_solver_yaml(solver_root / "stub_solver.yaml", problem_types=("tsp",))
    exp_path.write_text(_valid_config_text(), encoding="utf-8")

    with pytest.raises(ValueError, match="is incompatible"):
        load_config(exp_path, problem_root=problem_root, solver_root=solver_root)
