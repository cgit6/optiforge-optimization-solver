# `cli/exp/mkp_qpso.py`

## 模組責任

`cli/exp/mkp_qpso.py` 把外部文獻或既有實驗中的 QPSO baseline `Mean` 納入 collect 條件。它不是比 `Pdev`，而是要求指定 solver variant 的 projected `avg_objective` 至少達到 QPSO baseline mean。

## 公開入口/主要類型

- `TARGET_SOLVER_ID`
- `TARGET_PARAM_SET_INDEX`
- `FLOAT_TOLERANCE`
- `mkp_qpso_mean_gte_evaluator(...)`

## 主要資料結構與資料契約

- evaluator 只接受一個 target variant：`brlsmasca_rl_rc_numba/param_20`。
- `evaluation.base_line` 中必須存在 `name == "qpso"` 且 `mean` 非空的 baseline 條目。
- target variant 的 projected summary 必須滿足：
  - `total_runs > 0`
  - `valid_run_count == total_runs`
  - `feasible_rate == 1.0`
  - `avg_objective is not None`
  - `excluded_total == 0`
- 這個模組完全不看其他 solver variant 的相對名次；只看 target 與 baseline mean 的單點比較。

## 資料流與控制流

1. `_qpso_mean(...)` 從 `evaluation.base_line` 中找到 `qpso` baseline 的 `mean`。
2. `_target_variant(...)` 在 `variant_summaries` 中找 `brlsmasca_rl_rc_numba/param_20`。
3. `_summary_failure(...)` 檢查 target summary 是否可作為平均目標值比較。
4. evaluator 取 `target.summary.overall.avg_objective`，與 QPSO mean 做 `>=` 比較。
5. `_gte(...)` 用 `FLOAT_TOLERANCE` 處理浮點相等情況，避免接近值因二進位誤差被錯判失敗。

## 失敗路徑與例外條件

- baseline 中找不到 `qpso` mean 時，直接 `FAIL`。
- target variant 不存在時，直接 `FAIL`；這通常表示 solver param selection 與 evaluator 假設脫節。
- target projected summary 無法比較時，直接 `FAIL`，並提供 `failure` 詳細欄位。
- 本模組不驗證 baseline 與 target 的量綱是否一致；這是 config 作者需要自己維持的研究契約。

## 副作用與資源生命週期

- 無檔案、無 shared memory、無全域狀態修改。
- 單次呼叫只建立少量 failure/detail dict，沒有長生命週期資源。

## 與其他模組的關係

- 上游：`experiment.experiment` collect loop。
- 契約來源：`experiment.evaluation`。
- 註冊入口：`cli/exp/main.py`。
- 指標來源：target 的 `avg_objective` 由 `tools.stat` 摘要階段提供，baseline mean 由 `exp_cfg.yaml` 提供。
- 對照模組：`mkp_base.py` / `mkp_base2.py` 比 `Pdev`，本模組改比 `Mean`。

## 核心函式與 helper 說明

### `mkp_qpso_mean_gte_evaluator(input_data)`

- 目的：要求 `brlsmasca_rl_rc_numba/param_20` 的 projected `avg_objective` 至少達到 QPSO baseline mean。
- 控制流：先取 baseline `qpso` mean，再找 target variant，確認 summary 有效後做 `>=` 比較。
- 角色：這是 `cli.exp` evaluator 中少數直接比 `Mean` 而不是 `Pdev` 的規則。

### `_qpso_mean(input_data)`

- 目的：從 `evaluation.base_line` 中抽出 `name == "qpso"` 的平均值。
- 注意事項：這裡只用名稱匹配，不做 schema 或量綱比對，因此 config 作者必須自行維持 baseline 的研究語意正確。

### `_target_variant(...)` / `_summary_failure(...)` / `_gte(...)`

- 角色：這組 helper 固定了 target variant 選擇規則、summary 可比較條件與浮點容忍比較。
- 修改風險：target solver id / param set index 若更動，這裡與 `exp_cfg.yaml` 必須同步。

## 對應函式索引與閱讀順序

1. `TARGET_SOLVER_ID`
2. `TARGET_PARAM_SET_INDEX`
3. `FLOAT_TOLERANCE`
4. `mkp_qpso_mean_gte_evaluator`
5. `_qpso_mean`
6. `_target_variant`
7. `_summary_failure`
8. `_gte`
