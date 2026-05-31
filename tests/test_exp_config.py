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
    assert experiment.cfg.experiment_name == "mkp_cb_qpso_rc"
    assert experiment.cfg.collects == 20
    assert experiment.cfg.repeat == 300000000000
    assert experiment.cfg.worker_count == DEFAULT_WORKER_COUNT
    assert experiment.cfg.solver_ids == ("brlsmasca_rl_rc_numba",)
    assert experiment.cfg.solver_variants == (("brlsmasca_rl_rc_numba", 20),)
    assert len(experiment.cfg.dataset_settings) == 2
    assert sum(len(setting.problem_settings) for setting in experiment.cfg.dataset_settings) == 10
    first = experiment.cfg.dataset_settings[0]
    assert first.experiment_id == "set3_cb5"
    assert first.dataset == "OR10x250"
    assert first.problem_type == "mkp"
    assert first.problem_ids == (
        "OR10x250-0.25_1",
        "OR10x250-0.25_2",
        "OR10x250-0.25_3",
        "OR10x250-0.25_4",
        "OR10x250-0.25_5",
    )
    last = experiment.cfg.dataset_settings[-1]
    assert last.experiment_id == "set3_cb6"
    assert last.dataset == "OR10x500"
    assert last.problem_ids == (
        "OR10x500-0.25_1",
        "OR10x500-0.25_2",
        "OR10x500-0.25_3",
        "OR10x500-0.25_4",
        "OR10x500-0.25_5",
    )
    for setting in experiment.cfg.dataset_settings:
        assert setting.experiment_id.startswith("set3_cb")
        for problem in setting.problem_settings:
            assert problem.evaluation_names == ("mkp_qpso_mean_gte",)
            qpsos = [
                baseline
                for baseline in problem.evaluations[0].base_line
                if baseline.name == "QPSO"
            ]
            assert len(qpsos) == 1
            assert qpsos[0].mean is not None

    loader = SolverConfigLoader()
    rl_cfg = loader.load("brlsmasca_rl_rc_numba", param_set_index=20)
    assert rl_cfg["params"] == {
        "pop_size": 20,
        "z": 0.01,
        "a": 2.5,
        "alpha": 0.1,
        "gamma": 0.9,
        "ctf": "abs_pow_16",
        "eval_group_decimals": 1,
        "eval_group_shuffle": False,
        "eval_rc_eps": 1.0e-9,
        "eval_x_eps": 1.0e-9,
        "repair_passes": 2,
        "repair_swap_limit": 4,
        "mixed_init_enabled": True,
        "restart_enabled": True,
        "restart_window": 40,
        "restart_ratio": 0.25,
        "restart_strong_p": 0.85,
        "restart_core_p": 0.50,
        "restart_weak_p": 0.15,
        "guided_binary_enabled": True,
        "guided_lambda_lp": 0.30,
        "guided_lambda_bucket": 0.08,
        "guided_lambda_slack": 0.10,
        "local_search_enabled": True,
        "ls_budget_per_run": 1500,
        "ls_max_passes": 2,
        "ls_cooldown": 10,
        "ls_add_cap": 80,
        "ls_drop_cap": 80,
        "archive_pr_enabled": True,
        "archive_size": 8,
        "pr_interval": 15,
        "pr_max_steps": 15,
        "pr_core_only": True,
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
        (_valid_config_text(evaluation=""), "evaluation"),
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


def test_load_config_allows_empty_problem_evaluation_list(tmp_path: Path) -> None:
    exp_path, problem_root, solver_root = _write_valid_project(
        tmp_path,
        config_text=_valid_config_text(evaluation="[]"),
    )

    cfg = load_config(exp_path, problem_root=problem_root, solver_root=solver_root)

    assert cfg.dataset_settings[0].problem_settings[0].evaluations == ()
    assert cfg.dataset_settings[0].problem_settings[0].evaluation_names == ()


def test_load_config_rejects_null_problem_evaluation(tmp_path: Path) -> None:
    exp_path, problem_root, solver_root = _write_valid_project(
        tmp_path,
        config_text=_valid_config_text(evaluation=""),
    )

    with pytest.raises(ValueError, match="evaluation"):
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
