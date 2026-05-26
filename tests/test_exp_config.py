from __future__ import annotations

from pathlib import Path

import pytest

from mkp.cli.exp import main as exp_cli_main
from mkp.experiment import (
    DEFAULT_WORKER_COUNT,
    EvaluationBaseline,
    Experiment,
    ExperimentReport,
    PASS,
    RoundEvalDecision,
    build,
    load_config,
    register,
)
from mkp.tools.solver_config_loader import SolverConfigLoader


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
    params: str = "  - {}\n  - {z: 0.2}",
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
{params}
""".strip(),
        encoding="utf-8",
    )


def _valid_config_text(
    *,
    experiment_name: str = "exp_search",
    collects: str = "1",
    solvers: str | None = None,
    repeat: str = "2",
    dataset_key: str = "dataset_settings",
    extra_top_level: str = "",
    evaluation: str = "[custom]",
    experiment_id: str = "exp1",
    problem_key: str = "problem",
    problem_id: str = "p1",
    problem_extra: str = "",
    dataset_extra: str = "",
) -> str:
    solver_block = solvers or """
  - solver: stub_solver
    param_idx: [0]
"""
    return f"""
experiment_name: {experiment_name}
collects: {collects}
solvers:
{solver_block.rstrip()}
repeat: {repeat}
{extra_top_level}{dataset_key}:
  - experiment-id: {experiment_id}
    dataset: DATA
    type: mkp
    problems:
      - {problem_key}: {problem_id}
        evaluation: {evaluation}
{problem_extra}
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
    assert experiment.cfg.experiment_name == "mkp_transfer_param"
    assert experiment.cfg.collects == 20
    assert experiment.cfg.repeat == 300000000000
    assert experiment.cfg.worker_count == DEFAULT_WORKER_COUNT
    assert experiment.cfg.solver_ids == (
        "bsma_numba",
        "bsca_numba",
        "brlsmasca_rl_numba",
    )
    assert len(experiment.cfg.solver_variants) == 45
    assert experiment.cfg.solver_variants[:3] == (
        ("bsma_numba", 0),
        ("bsma_numba", 1),
        ("bsma_numba", 2),
    )
    assert experiment.cfg.solver_variants[-3:] == (
        ("brlsmasca_rl_numba", 24),
        ("brlsmasca_rl_numba", 25),
        ("brlsmasca_rl_numba", 26),
    )
    assert len(experiment.cfg.dataset_settings) == 3
    assert sum(len(setting.problem_settings) for setting in experiment.cfg.dataset_settings) == 4
    first = experiment.cfg.dataset_settings[0]
    assert first.experiment_id == "param_cb3"
    assert first.dataset == "OR5x500"
    assert first.problem_type == "mkp"
    assert len(first.problem_settings) == 1
    assert first.problem_ids == ("OR5x500-0.25_3",)
    assert first.problem_settings[0].evaluation_names == (
        "mkp_transfer_paired_strict",
        "mkp_target_combo_bsma_strict",
        "mkp_target_combo_bsca_margin_005",
        "mkp_target_combo_brlsmasca_margin_004",
    )
    assert tuple(
        problem.problem_id
        for setting in experiment.cfg.dataset_settings
        for problem in setting.problem_settings
    ) == (
        "OR5x500-0.25_3",
        "OR10x500-0.25_2",
        "mk_gk04",
        "mk_gk09",
    )
    evaluation_by_problem = {
        problem.problem_id: problem.evaluation_names
        for setting in experiment.cfg.dataset_settings
        for problem in setting.problem_settings
    }
    assert evaluation_by_problem["OR5x500-0.25_3"] == (
        "mkp_transfer_paired_strict",
        "mkp_target_combo_bsma_strict",
        "mkp_target_combo_bsca_margin_005",
        "mkp_target_combo_brlsmasca_margin_004",
    )
    assert all(
        evaluation_names == ("mkp_transfer_paired_strict", "mkp_target_combo_best")
        for problem_id, evaluation_names in evaluation_by_problem.items()
        if problem_id != "OR5x500-0.25_3"
    )

    loader = SolverConfigLoader()
    bsma_cfg = loader.load("bsma_numba", param_set_index=1)
    assert bsma_cfg["params"] == {
        "pop_size": 20,
        "z": 0.08,
        "ctf": "tanh_abs",
    }
    assert bsma_cfg["stop_condition"]["max_iterations"] == 5000

    bsca_cfg = loader.load("bsca_numba", param_set_index=0)
    assert bsca_cfg["params"] == {
        "pop_size": 20,
        "a": 1.5,
        "ctf": "tanh_abs",
    }
    assert bsca_cfg["stop_condition"]["max_iterations"] == 5000

    rl_cfg = loader.load("brlsmasca_rl_numba", param_set_index=5)
    assert rl_cfg["params"] == {
        "pop_size": 20,
        "z": 0.08,
        "a": 2.5,
        "alpha": 0.1,
        "gamma": 0.9,
        "ctf": "tanh_abs",
    }
    assert rl_cfg["stop_condition"]["max_iterations"] == 5000


def test_cli_exp_main_runs_experiment(tmp_path: Path) -> None:
    exp_path, problem_root, solver_root = _write_valid_project(
        tmp_path,
        config_text=_valid_config_text(
            evaluation="[always_pass]",
            problem_extra="""
        base_line:
          - name: Easy
            Pdev: 200
""",
        ),
    )
    register("always_pass", lambda _input: RoundEvalDecision(passed=True, verdict=PASS))

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


def test_load_config_rejects_removed_worker_key(tmp_path: Path) -> None:
    exp_path, problem_root, solver_root = _write_valid_project(
        tmp_path,
        config_text=_valid_config_text(extra_top_level="worker: 1\n"),
    )

    with pytest.raises(ValueError, match="unknown key"):
        load_config(exp_path, problem_root=problem_root, solver_root=solver_root)


def test_load_config_rejects_old_dataset_level_evaluation(tmp_path: Path) -> None:
    exp_path, problem_root, solver_root = _write_valid_project(
        tmp_path,
        config_text=_valid_config_text(
            dataset_extra="""
    evaluation:
      name: custom
""",
        ),
    )

    with pytest.raises(ValueError, match="unknown key"):
        load_config(exp_path, problem_root=problem_root, solver_root=solver_root)


def test_load_config_rejects_old_problem_string_list(tmp_path: Path) -> None:
    config_text = """
experiment_name: exp_search
collects: 1
solvers:
  - solver: stub_solver
    param_idx: [0]
repeat: 2
dataset_settings:
  - experiment-id: exp1
    dataset: DATA
    type: mkp
    problems: [p1]
""".strip()
    exp_path, problem_root, solver_root = _write_valid_project(tmp_path, config_text=config_text)

    with pytest.raises(ValueError, match="must be a mapping"):
        load_config(exp_path, problem_root=problem_root, solver_root=solver_root)


def test_load_config_parses_solver_param_idx_list(tmp_path: Path) -> None:
    exp_path, problem_root, solver_root = _write_valid_project(
        tmp_path,
        config_text=_valid_config_text(
            solvers="""
  - solver: stub_solver
    param_idx: [0, 1]
""",
        ),
    )

    cfg = load_config(exp_path, problem_root=problem_root, solver_root=solver_root)

    assert cfg.solver_ids == ("stub_solver",)
    assert cfg.solver_variants == (("stub_solver", 0), ("stub_solver", 1))


def test_load_config_rejects_solver_param_idx_out_of_range(tmp_path: Path) -> None:
    exp_path, problem_root, solver_root = _write_valid_project(
        tmp_path,
        config_text=_valid_config_text(
            solvers="""
  - solver: stub_solver
    param_idx: [2]
""",
        ),
    )

    with pytest.raises(ValueError, match="param_idx out of range"):
        load_config(exp_path, problem_root=problem_root, solver_root=solver_root)


@pytest.mark.parametrize(
    ("config_text", "error_match"),
    [
        (_valid_config_text(collects="0"), "collects"),
        (_valid_config_text(repeat="0"), "repeat"),
        (
            _valid_config_text(
                solvers="""
  - solver: stub_solver
    param_idx: []
"""
            ),
            "param_idx",
        ),
        (_valid_config_text(evaluation="[]"), "evaluation"),
        (
            _valid_config_text(
                extra_top_level="seed: [1, 3]\n",
            ),
            "unknown key",
        ),
        (
            _valid_config_text(
                solvers="""
  - solver: stub_solver
    param_idx: [0]
  - solver: stub_solver
    param_idx: [0]
"""
            ),
            "duplicate",
        ),
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


def test_load_config_parses_problem_baselines(tmp_path: Path) -> None:
    exp_path, problem_root, solver_root = _write_valid_project(
        tmp_path,
        config_text=_valid_config_text(
            problem_extra="""
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

    assert cfg.dataset_settings[0].problem_settings[0].evaluations[0].base_line == (
        EvaluationBaseline(name="PdevOnly", pdev=0.154),
        EvaluationBaseline(name="MeanOnly", mean=123.5),
        EvaluationBaseline(name="Both", mean=456.0, pdev=1.25),
    )


def test_load_config_rejects_missing_problem_yaml(tmp_path: Path) -> None:
    problem_root = tmp_path / "problems"
    solver_root = tmp_path / "solvers"
    exp_path = tmp_path / "exp_cfg.yaml"
    _write_solver_yaml(solver_root / "stub_solver.yaml")
    exp_path.write_text(_valid_config_text(problem_id="missing"), encoding="utf-8")

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
