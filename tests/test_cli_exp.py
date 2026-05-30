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
    assert [name for name, _ in calls["register"]] == [
        "mkp_base",
        "mkp_bsca_base_margin_2",
        "mkp_base2",
        "mkp_base2_margin_005",
        "mkp_calibration",
        "mkp_transfer_paired_strict",
        "mkp_target_combo_best",
        "mkp_transfer_core_strict",
        "mkp_transfer_bsca_margin_005",
        "mkp_target_combo_core_strict",
        "mkp_target_combo_bsma_strict",
        "mkp_target_combo_bsca_margin_005",
        "mkp_target_combo_front6_lead",
        "mkp_target_combo_gk_lag",
        "mkp_target_combo_brlsmasca_margin_004",
        "mkp_qpso_mean_gte",
        "mkp_random_collect_every_n_5_20",
    ]
    assert calls["run"] == (
        tmp_path / "problems",
        tmp_path / "solvers",
        tmp_path / "output",
    )
