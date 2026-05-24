from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import textwrap
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from ..cli.convert import getConverter
from ..converter import transformToYaml


def _resolve_app_entry(app_entry: Callable[..., list[tuple]] | None) -> Callable[..., list[tuple]]:
    if app_entry is not None:
        return app_entry
    from ..cli.run.main import main

    return main


@dataclass(frozen=True)
class ValidationScenario:
    dataset: str
    problem_id: str
    solver_id: str
    seeds: tuple[int, ...]


@dataclass(frozen=True)
class ComparableResult:
    best_objective: int | None
    feasible: bool | None
    stop_reason: str | None
    seed: int


def build_smoke_scenarios() -> list[ValidationScenario]:
    return [
        ValidationScenario(dataset="WEISH", problem_id="weish01", solver_id="bsma", seeds=(101, 202, 303)),
    ]


def ensure_problem_yaml(*, repo_root: Path, scenario: ValidationScenario) -> Path:
    return transformToYaml(
        repo_root=repo_root,
        dataset=scenario.dataset,
        problem_id=scenario.problem_id,
        parser=getConverter(scenario.dataset.lower()),
    )


def run_refactor_once(
    *,
    scenario: ValidationScenario,
    seed: int,
    output_root: Path,
    problem_root: Path,
    solver_root: Path,
    app_entry: Callable[..., list[tuple]] | None = None,
) -> ComparableResult:
    app_entry = _resolve_app_entry(app_entry)
    argv = [
        "--experiment-name",
        f"stage1_refactor_{scenario.dataset}_{scenario.problem_id}_{seed}",
        "--type",
        "mkp",
        "--dataset",
        scenario.dataset,
        "--problems",
        scenario.problem_id,
        "--solver",
        scenario.solver_id,
        "--repeat",
        "1",
        "--seed",
        str(seed),
    ]
    results = app_entry(argv, problem_root=problem_root, solver_root=solver_root, output_root=output_root)
    if hasattr(results, "iter_rows"):
        row = results.iter_rows()[0]
        run_result = row.solve_result
        validation_report = row.validation_report
    elif hasattr(results, "rows"):
        row = results.rows[0]
        run_result = row.solve_result
        validation_report = row.validation_report
    else:
        run_result, validation_report, _ = results[0]
    return ComparableResult(
        best_objective=int(run_result.best_objective),
        feasible=bool(validation_report.is_feasible),
        stop_reason=run_result.stop_reason,
        seed=seed,
    )


def check_refactor_reproducible(
    *,
    scenario: ValidationScenario,
    seed: int,
    output_root: Path,
    problem_root: Path,
    solver_root: Path,
    app_entry: Callable[..., list[tuple]] | None = None,
) -> bool:
    app_entry = _resolve_app_entry(app_entry)
    first = run_refactor_once(
        scenario=scenario,
        seed=seed,
        output_root=output_root,
        problem_root=problem_root,
        solver_root=solver_root,
        app_entry=app_entry,
    )
    second = run_refactor_once(
        scenario=scenario,
        seed=seed,
        output_root=output_root,
        problem_root=problem_root,
        solver_root=solver_root,
        app_entry=app_entry,
    )
    return first == second


def run_old_script(script_path: Path, *, working_directory: Path, timeout_seconds: int = 180) -> subprocess.CompletedProcess:
    wrapper = textwrap.dedent(
        """
        import importlib
        import importlib.util
        import os
        import pathlib
        import sys

        script_path = pathlib.Path(sys.argv[1]).resolve()
        repo_root = pathlib.Path(sys.argv[2]).resolve()
        old_dir = script_path.parent

        if str(old_dir) not in sys.path:
            sys.path.insert(0, str(old_dir))

        spec = importlib.util.spec_from_file_location("legacy_main_entry", str(script_path))
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        original_listdir = os.listdir
        def patched_listdir(path):
            if path == "data\\\\WEISH":
                return original_listdir(str(repo_root / "data" / "WEISH"))
            return original_listdir(path)
        os.listdir = patched_listdir
        try:
            runner = module.main()
        finally:
            os.listdir = original_listdir

        runner.batch_directory = str(repo_root / "data" / "WEISH")
        runner.batch_files = os.listdir(runner.batch_directory)
        runner.problem = ["01"]
        runner.run_time = 1
        if not runner.algorithm_select:
            runner.algorithm_select = [str(runner.algorithm_list[0])]
        runner.exe()
        """
    )

    return subprocess.run(
        [sys.executable, "-c", wrapper, str(script_path), str(working_directory)],
        cwd=str(working_directory),
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )


def collect_old_baseline_best_objective(*, repo_root: Path, dataset: str, problem_id: str) -> int | None:
    output_dir = repo_root / "output"
    if not output_dir.exists():
        return None

    # old scripts use filenames like runtime_<n>_prob_<id>_algo_<name>.csv
    pattern = re.compile(rf"runtime_\d+_prob_{re.escape(problem_id[-2:])}_algo_.*\.csv$")
    candidates = [p for p in output_dir.rglob("*.csv") if pattern.search(p.name)]
    if not candidates:
        return None

    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    raw = latest.read_text(encoding="utf-8", errors="ignore").strip()
    m = re.search(r"-?\d+", raw)
    if not m:
        return None
    return int(m.group(0))


def classify_diff(refactor: ComparableResult, baseline_best_objective: int | None) -> str:
    if baseline_best_objective is None:
        return "baseline_missing"
    if refactor.best_objective == baseline_best_objective:
        return "match"
    return "objective_mismatch"


def run_stage1_validation(
    *,
    repo_root: Path,
    output_root: Path = Path("output/stage1_validation"),
    scenarios: list[ValidationScenario] | None = None,
) -> Path:
    scenarios = scenarios or build_smoke_scenarios()
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = output_root / run_id
    baseline_dir = run_dir / "baseline"
    refactor_dir = run_dir / "refactor"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    refactor_dir.mkdir(parents=True, exist_ok=True)

    comparisons: list[dict] = []
    problem_root = repo_root / "configs/problems"
    solver_root = repo_root / "configs/solvers"

    old_script_map = {
        "WEISH": repo_root / "old/main1weish.py",
    }

    for scenario in scenarios:
        ensure_problem_yaml(repo_root=repo_root, scenario=scenario)
        old_script = old_script_map.get(scenario.dataset)
        old_stdout = ""
        old_stderr = ""
        if old_script is not None and old_script.exists():
            try:
                old_run = run_old_script(old_script, working_directory=repo_root)
                old_stdout = old_run.stdout
                old_stderr = old_run.stderr
            except subprocess.TimeoutExpired as exc:
                old_stdout = exc.stdout or ""
                old_stderr = (exc.stderr or "") + "\nTIMEOUT: old script exceeded timeout window."
            (baseline_dir / f"{scenario.dataset}_{scenario.problem_id}_stdout.log").write_text(old_stdout, encoding="utf-8")
            (baseline_dir / f"{scenario.dataset}_{scenario.problem_id}_stderr.log").write_text(old_stderr, encoding="utf-8")

        baseline_best = collect_old_baseline_best_objective(
            repo_root=repo_root, dataset=scenario.dataset, problem_id=scenario.problem_id
        )

        for seed in scenario.seeds:
            refactor = run_refactor_once(
                scenario=scenario,
                seed=seed,
                output_root=refactor_dir,
                problem_root=problem_root,
                solver_root=solver_root,
            )
            reproducible = check_refactor_reproducible(
                scenario=scenario,
                seed=seed,
                output_root=refactor_dir,
                problem_root=problem_root,
                solver_root=solver_root,
            )
            comparisons.append(
                {
                    "scenario": asdict(scenario),
                    "seed": seed,
                    "refactor": asdict(refactor),
                    "baseline_best_objective": baseline_best,
                    "comparison": classify_diff(refactor, baseline_best),
                    "refactor_reproducible": reproducible,
                }
            )

    comparison_path = run_dir / "comparison.json"
    comparison_path.write_text(json.dumps(comparisons, ensure_ascii=False, indent=2), encoding="utf-8")

    total = len(comparisons)
    reproducible_count = sum(1 for item in comparisons if item["refactor_reproducible"])
    match_count = sum(1 for item in comparisons if item["comparison"] == "match")
    summary = (
        f"total_cases={total}\n"
        f"refactor_reproducible={reproducible_count}\n"
        f"baseline_match={match_count}\n"
    )
    (run_dir / "summary.txt").write_text(summary, encoding="utf-8")
    return run_dir
