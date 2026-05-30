from __future__ import annotations

import json

from mkp.tools.mkp_item_eval_experiment import ITEM_EVAL_VARIANTS, run_experiment, sample_or_problems


def test_item_eval_experiment_samples_or_problems_reproducibly():
    selected_a = sample_or_problems(sample_seed=20260530, sample_per_dataset=2, datasets=("OR5x100", "OR10x100"))
    selected_b = sample_or_problems(sample_seed=20260530, sample_per_dataset=2, datasets=("OR5x100", "OR10x100"))

    assert selected_a == selected_b
    assert len(selected_a) == 4
    assert all(dataset in {"OR5x100", "OR10x100"} for dataset, _ in selected_a)


def test_item_eval_experiment_smoke_runs_and_writes_summary(tmp_path):
    payload = run_experiment(
        output_root=tmp_path,
        sample_seed=20260530,
        sample_per_dataset=1,
        max_iterations=2,
        repeat=1,
        seed_start=1000,
        variants=("BASE", "CORE_SCORE_CP"),
        datasets=("OR5x100",),
        max_runs=None,
    )

    assert payload["completed_runs"] == 2
    assert payload["expected_runs"] == 2
    assert (tmp_path / "runs.jsonl").exists()
    assert (tmp_path / "summary.json").exists()
    saved = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert saved["completed_runs"] == 2


def test_item_eval_experiment_variant_definitions_include_requested_methods():
    assert ITEM_EVAL_VARIANTS["CORE_SCORE_CP"]["item_eval_method"] == "core_score_cp"
    assert ITEM_EVAL_VARIANTS["FREQ_GATED_V2"]["item_eval_method"] == "freq_gated_v2"
    assert ITEM_EVAL_VARIANTS["FREQ_GATED_V2_GBC"]["item_eval_method"] == "freq_gated_v2_gbc"
    assert ITEM_EVAL_VARIANTS["FREQ_GATED_V2_GBC"]["guided_binary_enabled"] is True
