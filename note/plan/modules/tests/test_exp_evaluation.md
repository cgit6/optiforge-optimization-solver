# `tests/test_exp_evaluation.py`

## 模組責任

`test_exp_evaluation.py` 是 `cli.exp` evaluator 家族的單元測試主檔，使用合成 `VariantSummary` 與 `RoundEvalInput` 驗證 baseline、QPSO、calibration、deterministic sampling 等決策規則。

## 公開入口/主要類型

- pytest 自動發現測試
- 主要 helper：`_variant_summary`、`_input`、`_calibration_variants`、`_replace_calibration_variant`
- 主要測試群：random collect、QPSO mean、baseline Pdev、base2 margin、calibration transfer、target combo、alias/combo completeness

## 主要資料結構與資料契約

所有 evaluator 都必須只依 `RoundEvalInput` 與 summary/baseline 決策；summary invalid、baseline 缺失、combo 缺漏、margin 超標等情境都必須有穩定 verdict 與 details。

## 資料流與控制流

`_variant_summary(...)` 與 `_input(...)` 先產生最小 summary 契約，再按 evaluator 家族逐一驗證 pass/fail、strict best、margin、label completeness 與 alias 組合規則。

## 失敗路徑與例外條件

這個檔案保護的是 collect 規則本身；任何 evaluator 漏抓 invalid summary、誤判 margin 或 calibration combo 不完整，都會直接改變 experiment 收樣結果。

## 副作用與資源生命週期

純摘要層測試，無實際 solver 執行與 I/O。

## 與其他模組的關係

目標模組是 `mkp.cli.exp.mkp_*` evaluator、`mkp.experiment`、`mkp.simulator` 與 `mkp.tools.stat`。

## 對應函式索引與閱讀順序

1. `_variant_summary`
2. `_input`
3. `test_random_collect_every_n_5_20_accepts_one_repeat_per_problem_block`
4. `test_random_collect_every_n_5_20_is_deterministic_and_problem_specific`
5. `test_mkp_qpso_mean_gte_passes_when_target_mean_equals_qpso`
6. `test_mkp_qpso_mean_gte_passes_when_target_mean_exceeds_qpso`
7. `test_mkp_qpso_mean_gte_fails_when_target_mean_is_below_qpso`
8. `test_mkp_qpso_mean_gte_fails_when_qpso_mean_is_missing`
9. `test_mkp_qpso_mean_gte_fails_when_target_summary_is_invalid`
10. `test_mkp_base_passes_when_bsma_and_brlsmasca_beat_best_baseline`
11. `test_mkp_base_fails_when_bsma_or_brlsmasca_is_worse_than_best_baseline`
12. `test_mkp_base_zero_pdev_baseline_is_strict`
13. `test_mkp_base_fails_on_invalid_summary`
14. `test_mkp_bsca_base_margin_2_passes_when_bsca_is_within_margin`
15. `test_mkp_bsca_base_margin_2_fails_when_bsca_exceeds_margin`
16. `test_mkp_base2_passes_when_brlsmasca_is_best_or_tied`
17. `test_mkp_base2_fails_when_brlsmasca_is_not_best`
18. `test_mkp_base2_margin_005_passes_when_brlsmasca_is_within_margin`
19. `test_mkp_base2_margin_005_fails_when_brlsmasca_exceeds_margin`
20. `_calibration_variants`
21. `_replace_calibration_variant`
22. `test_mkp_transfer_paired_strict_passes_when_abs_pow_16_is_best_by_paired_average`
23. `test_mkp_transfer_paired_strict_fails_when_non_expected_transfer_has_better_paired_average`
24. `test_mkp_transfer_core_strict_passes_when_core_algorithms_pass_even_if_bsca_lags`
25. `test_mkp_transfer_bsca_margin_005_passes_when_bsca_is_slightly_worse`
26. `test_mkp_transfer_bsca_margin_005_fails_when_bsca_exceeds_margin`
27. `test_mkp_transfer_core_strict_fails_when_core_algorithm_fails`
28. `test_mkp_target_combo_best_passes_when_target_combos_are_algorithm_best`
29. `test_mkp_target_combo_best_uses_parameter_average_not_single_ctf_cell`
30. `test_mkp_target_combo_best_fails_when_target_combo_is_not_best`
31. `test_mkp_target_combo_bsma_strict_passes_when_bsma_target_is_best`
32. `test_mkp_target_combo_bsma_strict_fails_when_bsma_target_is_not_best`
33. `test_mkp_target_combo_core_strict_passes_when_core_targets_pass_even_if_bsca_lags`
34. `test_mkp_target_combo_bsca_margin_005_passes_when_bsca_target_is_within_margin`
35. `test_mkp_target_combo_bsca_margin_005_fails_when_bsca_target_exceeds_margin`
36. `test_mkp_target_combo_brlsmasca_margin_004_passes_when_brlsmasca_target_is_within_margin`
37. `test_mkp_target_combo_brlsmasca_margin_004_fails_when_brlsmasca_target_exceeds_margin`
38. `test_mkp_target_combo_front6_lead_requires_problem_threshold`
39. `test_mkp_target_combo_gk_lag_allows_configured_lag`
40. `test_mkp_target_combo_core_strict_fails_when_core_target_fails`
41. `test_calibration_labels_fail_when_combo_pair_is_missing`
42. `test_mkp_calibration_alias_requires_both_new_labels_to_pass`

## 核心函式與 helper 說明

### `_variant_summary` / `_input` / `_calibration_variants` / `_replace_calibration_variant`

這組 helper 是 evaluator 測試的資料工廠。它們把 `SummaryReport`、`VariantSummary`、`RoundEvalInput` 與 calibration 變體組合成最小可測 payload，讓每個 evaluator 測試只需關注判斷規則本身。

### random collect 與 QPSO 基線測試群

`test_random_collect_every_n_5_20_*` 描述 repeat 採樣是否 deterministic 且與 problem 綁定；`test_mkp_qpso_mean_gte_*` 則固定 QPSO 基線比較規則，特別是缺少 baseline、target summary 無效時的 failure message。

### `mkp_base` / `mkp_base2` 家族測試群

`test_mkp_base_*`、`test_mkp_bsca_base_margin_2_*`、`test_mkp_base2_*`、`test_mkp_base2_margin_005_*` 對應兩條主要 MKP baseline 規則。這些測試保護的是 pdev 比較、margin 容忍，以及 zero-pdev baseline 的嚴格模式。

### calibration / target-combo 家族測試群

後半段從 `test_mkp_transfer_paired_strict_*` 到 `test_mkp_calibration_alias_requires_both_new_labels_to_pass`，完整覆蓋 transfer、target combo、problem threshold、lag 容忍與 label alias 規則。這批測試是 `cli.exp` evaluator 鏈的核心回歸防線。
