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
        problems=None,
    )

    assert payload["completed_runs"] == 2
    assert payload["expected_runs"] == 2
    assert (tmp_path / "runs.jsonl").exists()
    assert (tmp_path / "summary.json").exists()
    saved = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert saved["completed_runs"] == 2


def test_item_eval_experiment_variant_definitions_include_requested_methods():
    assert "LP_RC_GROUPS" in ITEM_EVAL_VARIANTS
    assert "DYNAMIC_WEIGHT_DROP" in ITEM_EVAL_VARIANTS
    assert "GBC" in ITEM_EVAL_VARIANTS
    assert "FULL" in ITEM_EVAL_VARIANTS
    assert ITEM_EVAL_VARIANTS["CORE_SCORE_CP"]["item_eval_method"] == "core_score_cp"
    assert ITEM_EVAL_VARIANTS["CORE_SCORE_CP_GBC"]["guided_binary_enabled"] is True
    assert ITEM_EVAL_VARIANTS["FREQ_CP"]["item_eval_method"] == "freq_cp"
    assert ITEM_EVAL_VARIANTS["FREQ_CP_GBC"]["item_eval_method"] == "freq_cp_gbc"
    assert ITEM_EVAL_VARIANTS["ELITE_FREQ_CP"]["item_eval_method"] == "elite_freq_cp"
    assert ITEM_EVAL_VARIANTS["ELITE_FREQ_GATED"]["item_eval_method"] == "elite_freq_gated"
    assert ITEM_EVAL_VARIANTS["FREQ_GATED"]["item_eval_method"] == "freq_gated"
    assert ITEM_EVAL_VARIANTS["FREQ_GATED_V2"]["item_eval_method"] == "freq_gated_v2"
    assert ITEM_EVAL_VARIANTS["FREQ_GATED_V2_GBC"]["item_eval_method"] == "freq_gated_v2_gbc"
    assert ITEM_EVAL_VARIANTS["FREQ_GATED_V2_GBC"]["guided_binary_enabled"] is True
    assert ITEM_EVAL_VARIANTS["SBL_LITE_CP"]["item_eval_method"] == "sbl_lite_cp"
    assert ITEM_EVAL_VARIANTS["HYB_WEIGHT"]["item_eval_method"] == "score_hyb_weight"


def test_item_eval_experiment_accepts_explicit_problem_list(tmp_path):
    payload = run_experiment(
        output_root=tmp_path,
        sample_seed=20260530,
        sample_per_dataset=2,
        max_iterations=2,
        repeat=1,
        seed_start=1000,
        variants=("BASE", "CORE_SCORE_CP"),
        datasets=None,
        max_runs=None,
        problems=("OR5x100:OR5x100-0.25_1",),
    )

    assert payload["selected_problems"] == [{"dataset": "OR5x100", "problem_id": "OR5x100-0.25_1"}]
    assert payload["completed_runs"] == 2
    assert payload["expected_runs"] == 2
    ranking = payload["ranking"][0]
    assert ranking["variant"] == "CORE_SCORE_CP"
    assert "wilcoxon_less_p" in ranking
