# `cli/exp/mkp_base2.py`

## 模組責任

`cli/exp/mkp_base2.py` 定義另一組 MKP collect evaluator，但比較基準不再依賴外部 baseline，而是直接拿 projected variants 彼此互相比較。它的核心問題是：`brlsmasca_rl_numba` 是否已經是當前候選 round 裡最好的 family，或至少落在可接受 margin 內。

## 公開入口/主要類型

- `TARGET_SOLVER_ID`
- `PDEV_MARGIN_005`
- `mkp_base2_evaluator(...)`
- `mkp_base2_margin_005_evaluator(...)`

## 主要資料結構與資料契約

- 輸入是 `RoundEvalInput`，重點欄位為 `variant_summaries`。
- 每個 projected summary 都必須滿足與 `mkp_base.py` 相同的可比較契約：
  - `total_runs > 0`
  - `valid_run_count == total_runs`
  - `feasible_rate == 1.0`
  - `overall.pdev is not None`
  - `excluded_total == 0`
- variant key 固定是 `"{solver_id}/param_{param_set_index}"`。
- target solver 固定是 `brlsmasca_rl_numba`；只要 `variant_key.startswith("brlsmasca_rl_numba/")` 就會被視為 target。
- `mkp_base2_margin_005_evaluator(...)` 允許 target 與最佳 projected variant 之間有 `0.05` 的 `Pdev` 落差。

## 資料流與控制流

1. `_summary_failures(...)` 先排除不可比較的 projected summaries。
2. `_variant_pdevs(...)` 建立全體 projected variants 的 `pdev` 映射。
3. evaluator 把 variants 分成 target variants 與 competitors。
4. `mkp_base2_evaluator(...)` 逐一比對 target 與每個 competitor，要求 target `pdev <= competitor_pdev`。
5. `mkp_base2_margin_005_evaluator(...)` 先取全體最小 `pdev`，再把容忍線設成 `best_pdev + 0.05`。
6. `_lte(...)` 用浮點容忍比較支撐 strict/tied 判斷。

## 失敗路徑與例外條件

- 任一 projected summary 不合格時，直接 `FAIL`。
- target solver 缺席時，回傳 `FAIL`，表示這個 evaluator 與當前 solver selection 不匹配。
- strict best 檢查中，只要任一 target 被任一 competitor 超過，就會失敗，並把所有失敗 pair 寫入 `details.worse_targets`。
- margin 檢查中，只要任一 target 超出 `best_pdev + 0.05`，就會失敗。
- 本模組不負責 baseline 驗證，也不處理 shared state；它假設 projected_result 已由 collect 主流程正確建立。

## 副作用與資源生命週期

- 無 I/O、無快取、無註冊表修改。
- 可重複、可平行執行；相同輸入必定得到相同輸出。

## 與其他模組的關係

- 上游：`experiment.experiment._evaluate_candidate_round(...)`。
- 契約層：`experiment.evaluation`。
- 家族關係：與 `cli/exp/mkp_base.py` 共用 summary validation 與 `Pdev` 比較模式，但一個依 baseline、一個依 projected peers。
- 指標來源：`tools.stat` 的 `SummaryReport.overall.pdev`。

## 核心函式與 helper 說明

### `mkp_base2_evaluator(input_data)`

- 目的：要求 `brlsmasca_rl_numba` 至少與同輪 projected peers 中最佳者持平。
- 控制流：summary 驗證後，先拆出 target variants 與 competitors，再逐一比較 target `pdev <= competitor_pdev`。
- 角色：這是 peer-to-peer acceptance rule，不依賴外部 baseline。

### `mkp_base2_margin_005_evaluator(input_data)`

- 目的：把 strict best 放寬成「距離最佳 projected variant 不超過 `0.05` `Pdev`」。
- 注意事項：門檻是 `best_pdev + margin`，不是針對單一 competitor 逐對比較。

### `_summary_failures(...)` / `_variant_pdevs(...)` / `_variant_key(...)` / `_lte(...)`

- 角色：與 `mkp_base.py` 同族，但這裡的 helper 完全服務 projected peer comparison。
- 修改風險：若 key 或浮點容忍規則改變，會直接影響 strict best / tie 的判決結果。

## 對應函式索引與閱讀順序

1. `TARGET_SOLVER_ID`
2. `PDEV_MARGIN_005`
3. `mkp_base2_evaluator`
4. `mkp_base2_margin_005_evaluator`
5. `_summary_failures`
6. `_variant_pdevs`
7. `_variant_key`
8. `_lte`
