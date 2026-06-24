# `cli/exp/mkp_base.py`

## 模組責任

`cli/exp/mkp_base.py` 定義以 baseline `Pdev` 為門檻的 MKP collect evaluator。它把 `exp_cfg.yaml` 中人工提供的 baseline 統計值，轉成對 projected variant summaries 的接受條件，主要用在「至少不差於既有基線」的 round 篩選。

## 公開入口/主要類型

- `BASELINE_TARGET_SOLVER_IDS`
- `BSCA_SOLVER_ID`
- `BSCA_BASELINE_MARGIN`
- `mkp_base_evaluator(...)`
- `mkp_bsca_base_margin_2_evaluator(...)`

## 主要資料結構與資料契約

- 輸入固定是 `RoundEvalInput`，真正消費的欄位是：
  - `evaluation.base_line`：必須至少有一筆含 `pdev` 的 baseline。
  - `variant_summaries`：每個 solver variant 的 projected summary。
- projected summary 必須滿足：
  - `total_runs > 0`
  - `valid_run_count == total_runs`
  - `feasible_rate == 1.0`
  - `overall.pdev is not None`
  - `excluded_counts.{infeasible, objective_mismatch, runtime_error} == 0`
- variant 會被正規化成 `"{solver_id}/param_{param_set_index}"` 字串鍵，後續比較都以這個鍵進行。
- `mkp_base_evaluator(...)` 只關注 `bsma_numba` 與 `brlsmasca_rl_numba`。
- `mkp_bsca_base_margin_2_evaluator(...)` 只關注 `bsca_numba`，允許比最佳 baseline 多 `2.0` `Pdev`。

## 資料流與控制流

1. 從 `evaluation.base_line` 擷取所有可用 `pdev`，取最小值作為 baseline 最佳門檻。
2. `_summary_failures(...)` 先檢查 projected summaries 是否可比較；這一層先把 infeasible、objective mismatch、runtime error 的 round 排除掉。
3. `_variant_pdevs(...)` 產生 `variant -> pdev` 對照表。
4. `_target_pdevs(...)` 依 solver family 篩出本模組關心的 target variants。
5. `mkp_base_evaluator(...)` 驗證所有 target variant 的 `pdev` 都必須 `<=` baseline 最佳值。
6. `mkp_bsca_base_margin_2_evaluator(...)` 改用 `baseline_best + 2.0` 當門檻，檢查 `bsca_numba` 是否落在容忍範圍內。
7. `_lte(...)` 以 `1e-12` 級距容忍浮點比較，避免等值誤判。

## 失敗路徑與例外條件

- baseline 沒有任何可用 `pdev` 時，直接回傳 `FAIL`。
- 任一 projected summary 不可比較時，直接回傳 `FAIL`，並在 `details.failures` 列出具體 variant。
- target solver 缺席時，回傳 `FAIL`；這通常表示 solver selection 與 evaluator 假設不一致。
- target solver 的 `pdev` 高於允許門檻時，回傳 `FAIL`，並附上 threshold 與 offending variants。
- 本模組不拋例外給 caller；它用 `RoundEvalDecision` 表達邏輯失敗，真正的例外只會來自上游傳入不符合型別契約的物件。

## 副作用與資源生命週期

- 純函式模組，無檔案 I/O、無 shared memory、無 process pool 狀態。
- evaluator 唯一輸出是 `RoundEvalDecision`，因此能被 `Experiment._evaluate_candidate_round(...)` 重複呼叫而不留下狀態。

## 與其他模組的關係

- 上游：`experiment.experiment` 在 candidate round 階段建立 `RoundEvalInput` 並呼叫本模組。
- 契約來源：`experiment.evaluation` 定義 `RoundEvalInput`、`VariantSummary`、`RoundEvalDecision`。
- 註冊入口：`cli/exp/main.py` 把本模組 evaluator 掛到 `_EVALUATORS` registry。
- 指標來源：`tools.stat` 產生 `summary.overall.pdev` 與 excluded counts，本模組只消費，不重新計算。
- 同家族模組：`cli/exp/mkp_base2.py` 也是 Pdev 型 evaluator，但基準改成 projected peers 而不是外部 baseline。

## 核心函式與 helper 說明

### `mkp_base_evaluator(input_data)`

- 目的：驗證 `bsma_numba` 與 `brlsmasca_rl_numba` 是否都不差於外部 baseline 最佳 `Pdev`。
- 控制流：先抽 baseline `pdev`，再檢查 projected summaries 是否可比較，最後對 target solver family 做 `<= baseline_best` 判定。
- 失敗路徑：baseline 缺失、target solver 缺席、projected summary 無效、target `pdev` 超標都會回 `FAIL`。

### `mkp_bsca_base_margin_2_evaluator(input_data)`

- 目的：對 `bsca_numba` 套較寬鬆的 baseline 規則，允許比最佳 baseline 多 `2.0` `Pdev`。
- 角色：它反映研究上對 BSCA family 的不同接受標準，而不是單純重複 `mkp_base_evaluator(...)`。

### `_summary_failures(variant_summaries)`

- 目的：先排除 infeasible、objective mismatch、runtime error 或缺 `pdev` 的 projected summary。
- 在流程中的角色：這是所有 `Pdev` 比較前的共同品質閘門，避免拿不完整 summary 做比較。

### `_variant_pdevs(...)` / `_variant_key(...)`

- 目的：把 `VariantSummary` 穩定映射成 `solver_id/param_index -> pdev`。
- 維護意義：各 evaluator 其實都依賴相同的 key naming 規則；若 key 規則改了，失敗 detail 與測試基線也要同步更新。

### `_target_pdevs(...)` / `_has_solver_pdev(...)` / `_lte(...)`

- 角色：這組 helper 把「挑出特定 solver family」與「浮點容忍比較」獨立出來。
- 注意事項：`_lte(...)` 的 `1e-12` 容忍是研究判則的一部分，不只是程式實作細節。

## 對應函式索引與閱讀順序

1. `BASELINE_TARGET_SOLVER_IDS`
2. `BSCA_SOLVER_ID`
3. `BSCA_BASELINE_MARGIN`
4. `mkp_base_evaluator`
5. `mkp_bsca_base_margin_2_evaluator`
6. `_summary_failures`
7. `_variant_pdevs`
8. `_variant_key`
9. `_target_pdevs`
10. `_has_solver_pdev`
11. `_lte`
