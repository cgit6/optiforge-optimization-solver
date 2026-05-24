from __future__ import annotations

import importlib
from pathlib import Path


def test_cli_exp_main_registers_bundled_evaluators_builds_and_runs(monkeypatch, tmp_path: Path) -> None:
    exp_main = importlib.import_module("mkp.cli.exp.main")
    calls: dict[str, object] = {"register": []}

    class FakeExperiment:
        def run(self, *, problem_root, solver_root, output_root):
            calls["run"] = (problem_root, solver_root, output_root)
            return "report"

    def fake_register(name, evaluator):
        calls["register"].append((name, evaluator))

    def fake_build(exp_path, *, problem_root, solver_root):
        calls["build"] = (exp_path, problem_root, solver_root)
        return FakeExperiment()

    monkeypatch.setattr(exp_main, "register", fake_register)
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
    assert [name for name, _ in calls["register"]] == ["mkp_base", "mkp_base2"]
    assert calls["run"] == (
        tmp_path / "problems",
        tmp_path / "solvers",
        tmp_path / "output",
    )
