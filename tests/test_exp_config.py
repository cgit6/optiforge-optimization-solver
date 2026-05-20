from __future__ import annotations

from pathlib import Path

import pytest

from mkp.cli.exp import main as exp_cli_main
from mkp.experiment import EvaluationBaseline, Experiment, ExperimentReport, build, load_config


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
    extra_top_level: str = "",
    evaluation_name: str = "literature_mkp",
    evaluation_extra: str = "",
    experiment_id: str = "exp1",
    problems: str = "[p1]",
    dataset_extra: str = "",
) -> str:
    return f"""
experiment_name: {experiment_name}
seed: {seed}
collects: {collects}
solvers: {solvers}
worker: {worker}
repeat: {repeat}
{extra_top_level}{dataset_key}:
  - experiment-id: {experiment_id}
    dataset: DATA
    problems: {problems}
    type: mkp
    evaluation:
      name: {evaluation_name}
{evaluation_extra}
{dataset_extra}
""".strip()


def _write_valid_project(tmp_path: Path, *, config_text: str | None = None) -> tuple[Path, Path, Path]:
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    exp_path = tmp_path / "exp_cfg.yaml"
    _write_problem_yaml(problem_root / "mkp" / "DATA" / "p1.yaml")
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
    assert experiment.cfg.worker_count == 10
    assert experiment.cfg.solver_ids == ("bsma_numba", "bsca_numba", "brlsmasca_numba")
    assert len(experiment.cfg.dataset_settings) == 8
    first = experiment.cfg.dataset_settings[0]
    assert first.experiment_id == "weish-expTest"
    assert first.dataset == "WEISH"
    assert first.problem_type == "mkp"
    assert len(first.problem_ids) == 30
    assert first.evaluation.name == "literature_mkp"
    assert first.evaluation.base_line == (
        EvaluationBaseline(name="HLMS", pdev=0.154),
        EvaluationBaseline(name="BIWOA", pdev=0.472),
        EvaluationBaseline(name="BMMVO", pdev=0.861),
        EvaluationBaseline(name="BSCA", pdev=0.314),
        EvaluationBaseline(name="IBSMA_U1", pdev=0.105),
    )
    pet = experiment.cfg.dataset_settings[3]
    assert pet.dataset == "PET"
    assert pet.evaluation.base_line == ()
    gk = experiment.cfg.dataset_settings[-1]
    assert gk.evaluation.base_line[-1] == EvaluationBaseline(
        name="IBSMA_U1",
        mean=14428.233,
        pdev=0.624,
    )


def test_cli_exp_main_runs_experiment(tmp_path: Path) -> None:
    exp_path, problem_root, solver_root = _write_valid_project(tmp_path)

    exp_main_module = __import__("mkp.cli.exp.main", fromlist=["main"])
    original_config = exp_main_module.DEFAULT_CONFIG_PATH
    original_problem_root = exp_main_module.DEFAULT_PROBLEM_ROOT
    original_solver_root = exp_main_module.DEFAULT_SOLVER_ROOT
    original_output_root = exp_main_module.DEFAULT_OUTPUT_ROOT
    exp_main_module.DEFAULT_CONFIG_PATH = exp_path
    exp_main_module.DEFAULT_PROBLEM_ROOT = problem_root
    exp_main_module.DEFAULT_SOLVER_ROOT = solver_root
    exp_main_module.DEFAULT_OUTPUT_ROOT = tmp_path / "output"
    try:
        report = exp_cli_main()
    finally:
        exp_main_module.DEFAULT_CONFIG_PATH = original_config
        exp_main_module.DEFAULT_PROBLEM_ROOT = original_problem_root
        exp_main_module.DEFAULT_SOLVER_ROOT = original_solver_root
        exp_main_module.DEFAULT_OUTPUT_ROOT = original_output_root

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
        config_text=_valid_config_text(extra_top_level="output: x\n"),
    )

    with pytest.raises(ValueError, match="unknown key"):
        load_config(exp_path, problem_root=problem_root, solver_root=solver_root)


def test_load_config_rejects_old_stages_key(tmp_path: Path) -> None:
    exp_path, problem_root, solver_root = _write_valid_project(
        tmp_path,
        config_text=_valid_config_text(extra_top_level="stages: {}\n"),
    )

    with pytest.raises(ValueError, match="unknown key"):
        load_config(exp_path, problem_root=problem_root, solver_root=solver_root)


def test_load_config_rejects_old_base_line_key(tmp_path: Path) -> None:
    exp_path, problem_root, solver_root = _write_valid_project(
        tmp_path,
        config_text=_valid_config_text(
            dataset_extra="""
    base_line:
      - problem: p1
        avg: 10
        best: 20
        PDev: 0
""",
        ),
    )

    with pytest.raises(ValueError, match="unknown key"):
        load_config(exp_path, problem_root=problem_root, solver_root=solver_root)


def test_load_config_rejects_missing_solver_yaml(tmp_path: Path) -> None:
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    exp_path = tmp_path / "exp_cfg.yaml"
    _write_problem_yaml(problem_root / "mkp" / "DATA" / "p1.yaml")
    exp_path.write_text(_valid_config_text(solvers="[missing_solver]"), encoding="utf-8")

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


def test_load_config_rejects_missing_evaluation_name(tmp_path: Path) -> None:
    exp_path, problem_root, solver_root = _write_valid_project(
        tmp_path,
        config_text=_valid_config_text().replace("      name: literature_mkp", ""),
    )

    with pytest.raises(ValueError, match="evaluation"):
        load_config(exp_path, problem_root=problem_root, solver_root=solver_root)


def test_load_config_rejects_missing_dataset_evaluation_block(tmp_path: Path) -> None:
    exp_path, problem_root, solver_root = _write_valid_project(
        tmp_path,
        config_text="""
experiment_name: exp_search
seed: [1, 3]
collects: 1
solvers: [stub_solver]
worker: 1
repeat: 2
dataset_settings:
  - experiment-id: exp1
    dataset: DATA
    problems: [p1]
    type: mkp
""".strip(),
    )

    with pytest.raises(ValueError, match="missing required key"):
        load_config(exp_path, problem_root=problem_root, solver_root=solver_root)


def test_load_config_rejects_removed_top_level_evaluation_block(tmp_path: Path) -> None:
    exp_path, problem_root, solver_root = _write_valid_project(
        tmp_path,
        config_text="evaluation:\n  name: literature_mkp\n" + _valid_config_text(),
    )

    with pytest.raises(ValueError, match="unknown key"):
        load_config(exp_path, problem_root=problem_root, solver_root=solver_root)


def test_load_config_rejects_evaluation_config_key(tmp_path: Path) -> None:
    exp_path, problem_root, solver_root = _write_valid_project(
        tmp_path,
        config_text=_valid_config_text().replace(
            "      name: literature_mkp",
            "      name: literature_mkp\n      config: {}",
        ),
    )

    with pytest.raises(ValueError, match="unknown key"):
        load_config(exp_path, problem_root=problem_root, solver_root=solver_root)


def test_load_config_parses_evaluation_base_line_variants(tmp_path: Path) -> None:
    exp_path, problem_root, solver_root = _write_valid_project(
        tmp_path,
        config_text=_valid_config_text(
            evaluation_extra="""
      base_line:
        - name: PdevOnly
          Pdev: 0.154
        - name: MeanOnly
          Mean: 123.5
        - name: Both
          Mean: 456
          Pdev: 1.25
""",
        ),
    )

    cfg = load_config(exp_path, problem_root=problem_root, solver_root=solver_root)

    assert cfg.dataset_settings[0].evaluation.base_line == (
        EvaluationBaseline(name="PdevOnly", pdev=0.154),
        EvaluationBaseline(name="MeanOnly", mean=123.5),
        EvaluationBaseline(name="Both", mean=456.0, pdev=1.25),
    )


@pytest.mark.parametrize(
    ("evaluation_extra", "error_match"),
    [
        (
            """
      base_line:
        - name: EmptyMean
          Mean:
""",
            "Mean",
        ),
        (
            """
      base_line:
        - name: EmptyPdev
          Pdev:
""",
            "Pdev",
        ),
        (
            """
      base_line:
        - name: BoolMean
          Mean: true
""",
            "numeric",
        ),
        (
            """
      base_line:
        - name: BoolPdev
          Pdev: false
""",
            "numeric",
        ),
        (
            """
      base_line:
        - Pdev: 0.1
""",
            "missing required key",
        ),
        (
            """
      base_line:
        - name: NoMetrics
""",
            "Mean or Pdev",
        ),
        (
            """
      base_line: {}
""",
            "must be a list",
        ),
        (
            """
      base_line:
        - broken
""",
            "must be a mapping",
        ),
        (
            """
      base_line:
        - name: Unknown
          Pdev: 0.1
          Rank: 1
""",
            "unknown key",
        ),
    ],
)
def test_load_config_rejects_invalid_evaluation_base_line(
    tmp_path: Path,
    evaluation_extra: str,
    error_match: str,
) -> None:
    exp_path, problem_root, solver_root = _write_valid_project(
        tmp_path,
        config_text=_valid_config_text(evaluation_extra=evaluation_extra),
    )

    with pytest.raises(ValueError, match=error_match):
        load_config(exp_path, problem_root=problem_root, solver_root=solver_root)


def test_load_config_rejects_duplicate_experiment_id(tmp_path: Path) -> None:
    settings = _valid_config_text() + """
  - experiment-id: exp1
    dataset: DATA
    problems: [p1]
    type: mkp
    evaluation:
      name: literature_mkp
"""
    exp_path, problem_root, solver_root = _write_valid_project(tmp_path, config_text=settings)

    with pytest.raises(ValueError, match="experiment-id is duplicated"):
        load_config(exp_path, problem_root=problem_root, solver_root=solver_root)


def test_load_config_rejects_dataset_specific_evaluation_config(tmp_path: Path) -> None:
    config_text = _valid_config_text(
        dataset_extra="""
  - experiment-id: exp2
    dataset: DATA
    problems: [p2]
    type: mkp
    evaluation:
      name: literature_mkp
      config:
        unused: true
""",
    )
    exp_path, problem_root, solver_root = _write_valid_project(tmp_path, config_text=config_text)
    _write_problem_yaml(problem_root / "mkp" / "DATA" / "p2.yaml", problem_id="p2")

    with pytest.raises(ValueError, match="unknown key"):
        load_config(exp_path, problem_root=problem_root, solver_root=solver_root)


def test_load_config_rejects_missing_problem_yaml(tmp_path: Path) -> None:
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    exp_path = tmp_path / "exp_cfg.yaml"
    _write_solver_yaml(solver_root / "stub_solver.yaml")
    exp_path.write_text(_valid_config_text(problems="[missing]"), encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="Problem YAML not found"):
        load_config(exp_path, problem_root=problem_root, solver_root=solver_root)


def test_load_config_rejects_solver_problem_capability_mismatch(tmp_path: Path) -> None:
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    exp_path = tmp_path / "exp_cfg.yaml"
    _write_problem_yaml(problem_root / "mkp" / "DATA" / "p1.yaml")
    _write_solver_yaml(solver_root / "stub_solver.yaml", problem_types=("tsp",))
    exp_path.write_text(_valid_config_text(), encoding="utf-8")

    with pytest.raises(ValueError, match="is incompatible"):
        load_config(exp_path, problem_root=problem_root, solver_root=solver_root)
