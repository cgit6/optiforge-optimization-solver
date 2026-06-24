# `tests/test_stat.py`

## 模組責任

`test_stat.py` 覆蓋 `tools.stat` / `tools.show` 的結果整理與輸出規則，是 runtime 驗證報告如何變成正式 summary 的主要測試檔。

## 公開入口/主要類型

- pytest 自動發現測試
- 主要 helper：`_build_problem`、`_build_tsp_problem`、`_build_solve_result`、`_summary_meta`、`_simulator_result`、`_make_row`
- 主要測試群：runs output、索引、summary aggregation、mixed solver/param guard、meta、invalid rows、Pdev、multi-objective

## 主要資料結構與資料契約

只有 feasible 且 objective-valid 的 run 能進 objective 統計；infeasible、objective mismatch、runtime error 必須分開進 excluded counts，但仍保留在原始輸出。

## 資料流與控制流

helpers 建 problem、solve result、simulator result 與 row，接著驗證 runs 輸出欄位、索引、summary aggregation、mixed solver/param guard、meta、Pdev、direction 與 multi-objective 處理。

## 失敗路徑與例外條件

若 summary 誤納入 invalid run、錯算 worst/Pdev、或丟失 invalid rows，所有 evaluator 與研究報表都會失真。

## 副作用與資源生命週期

會在暫時目錄寫出 runs/summary JSON/CSV。

## 與其他模組的關係

目標模組是 `mkp.tools.stat`、`mkp.tools.show`，並間接依賴 `mkp.machine`、`mkp.simulator`、`mkp.problem` 與 `mkp.engine.models`。

## 對應函式索引與閱讀順序

1. `_build_problem`
2. `_build_tsp_problem`
3. `_build_solve_result`
4. `_summary_meta`
5. `_simulator_result`
6. `_make_row`
7. `test_write_simulator_result_writes_single_run_with_standard_fields`
8. `test_simulator_result_indexes_by_variant_and_run`
9. `test_summary_aggregation_and_exclusion_rules`
10. `test_summarize_rejects_mixed_param_sets`
11. `test_summarize_rejects_mixed_solvers`
12. `test_write_splits_param_sets_and_writes_each_variant_meta`
13. `test_write_summary_meta_includes_experiment_metadata`
14. `test_write_keeps_invalid_runs_in_outputs`
15. `test_runtime_error_is_excluded_separately`
16. `test_summary_adds_std_worst_and_pdev_for_multiple_valid_mkp_runs`
17. `test_summary_uses_min_direction_for_worst_and_pdev`
18. `test_multi_objective_runs_are_saved_without_scalar_summary_stats`

## 核心函式與 helper 說明

### `_build_problem` / `_build_tsp_problem` / `_build_solve_result` / `_summary_meta` / `_simulator_result` / `_make_row`

這些 helper 直接組裝 `tools.stat` 所需的輸入物件，而不是走完整 runtime。它們的角色是把統計規則與 solver 執行脫鉤，讓失敗案例與 edge case 可以精準重建。

### 寫檔與列索引測試群

`test_write_simulator_result_writes_single_run_with_standard_fields`、`test_simulator_result_indexes_by_variant_and_run`、`test_write_splits_param_sets_and_writes_each_variant_meta`、`test_write_summary_meta_includes_experiment_metadata` 驗證 row 與 summary 的輸出格式、variant 分拆與 metadata 內容。

### `summarize(...)` 規則測試群

`test_summary_aggregation_and_exclusion_rules`、`test_summarize_rejects_mixed_param_sets`、`test_summarize_rejects_mixed_solvers`、`test_runtime_error_is_excluded_separately` 固定了統計聚合邊界：只有同 solver/同 param set 可聚合，且 invalid run 與 runtime error 必須被分類排除而不是靜默丟棄。

### 方向性、多目標與擴展統計測試群

`test_summary_adds_std_worst_and_pdev_for_multiple_valid_mkp_runs`、`test_summary_uses_min_direction_for_worst_and_pdev`、`test_multi_objective_runs_are_saved_without_scalar_summary_stats` 保護 summary 在 max/min 問題與多目標輸出上的分支邏輯。
