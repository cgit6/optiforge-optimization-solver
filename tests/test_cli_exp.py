from __future__ import annotations

import importlib
from pathlib import Path


def test_cli_exp_main_builds_and_runs_experiment(monkeypatch, tmp_path: Path) -> None:
    exp_main = importlib.import_module("mkp.cli.exp.main")
    calls: dict[str, object] = {}

    class FakeExperiment:
        def register(self, name, evaluator):
            calls["register"] = (name, evaluator)

        def run(self, *, problem_root, solver_root, output_root):
            calls["run"] = (problem_root, solver_root, output_root)
            return "report"

    def fake_build(exp_path, *, problem_root, solver_root):
        calls["build"] = (exp_path, problem_root, solver_root)
        return FakeExperiment()

    monkeypatch.setattr(exp_main, "build", fake_build)
    monkeypatch.setattr(exp_main, "DEFAULT_CONFIG_PATH", tmp_path / "exp.yaml")
    monkeypatch.setattr(exp_main, "DEFAULT_PROBLEM_ROOT", tmp_path / "problems")
    monkeypatch.setattr(exp_main, "DEFAULT_SOLVER_ROOT", tmp_path / "solvers")
    monkeypatch.setattr(exp_main, "DEFAULT_OUTPUT_ROOT", tmp_path / "output")

    result = exp_main.main()

    assert result == "report"
    assert calls["build"] == (
        tmp_path / "exp.yaml",
        tmp_path / "problems",
        tmp_path / "solvers",
    )
    assert calls["register"][0] == "literature_mkp"
    assert calls["run"] == (
        tmp_path / "problems",
        tmp_path / "solvers",
        tmp_path / "output",
    )
