from __future__ import annotations

import importlib
from pathlib import Path


def test_cli_exp_main_builds_and_runs_experiment(monkeypatch, tmp_path: Path) -> None:
    exp_main = importlib.import_module("mkp.cli.exp.main")
    calls: dict[str, object] = {}

    class FakeExperiment:
        def run(self, *, eval_name, problem_root, solver_root, output_root):
            calls["run"] = (eval_name, problem_root, solver_root, output_root)
            return "report"

    def fake_build(exp_path, *, problem_root, solver_root):
        calls["build"] = (exp_path, problem_root, solver_root)
        return FakeExperiment()

    monkeypatch.setattr(exp_main, "build", fake_build)

    result = exp_main.main(
        [
            "--config",
            str(tmp_path / "exp.yaml"),
            "--problem-root",
            str(tmp_path / "problems"),
            "--solver-root",
            str(tmp_path / "solvers"),
            "--output-root",
            str(tmp_path / "output"),
            "--eval",
            "custom",
        ]
    )

    assert result == "report"
    assert calls["build"] == (
        tmp_path / "exp.yaml",
        tmp_path / "problems",
        tmp_path / "solvers",
    )
    assert calls["run"] == (
        "custom",
        tmp_path / "problems",
        tmp_path / "solvers",
        tmp_path / "output",
    )
