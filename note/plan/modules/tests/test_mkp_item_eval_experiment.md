# `tests/test_mkp_item_eval_experiment.py`

## 模組責任

`test_mkp_item_eval_experiment.py` 驗證 `mkp_item_eval_experiment` 研究輔助工具的抽樣、variant 定義與 summary 輸出。

## 公開入口/主要類型

- pytest 自動發現測試
- 主要測試群：sample/problem reproducibility、smoke run、variant definition、explicit problem list

## 主要資料結構與資料契約

同樣的輸入參數應產生可重播的 sample/problem 選擇；variant 定義必須包含要求的方法，smoke run 必須寫出 summary。

## 資料流與控制流

測試以小型參數集合呼叫工具函式，檢查 sample 重現性、summary 寫出與 explicit problem list 支援。

## 失敗路徑與例外條件

若工具無法穩定產生樣本、缺少方法定義或不寫 summary，研究實驗腳手架就不可依賴。

## 副作用與資源生命週期

會在暫時目錄寫出 summary 類輸出。

## 與其他模組的關係

目標模組是 `mkp.tools.mkp_item_eval_experiment`。

## 對應函式索引與閱讀順序

1. `test_item_eval_experiment_samples_or_problems_reproducibly`
2. `test_item_eval_experiment_smoke_runs_and_writes_summary`
3. `test_item_eval_experiment_variant_definitions_include_requested_methods`
4. `test_item_eval_experiment_accepts_explicit_problem_list`

## 核心函式與 helper 說明

### `test_item_eval_experiment_samples_or_problems_reproducibly`

這個測試保護 `sample_or_problems(...)` 的 deterministic 抽樣規則，確保研究腳本在同 seed 下會選到同一批 OR 問題。

### `test_item_eval_experiment_smoke_runs_and_writes_summary`

這是 item-eval experiment 的 smoke test。它驗證少量 variant 與問題集能跑完、寫出 `runs.jsonl` / `summary.json`，並在 payload 中回報正確的 completed / expected runs。

### `test_item_eval_experiment_variant_definitions_include_requested_methods`

這個案例把 `ITEM_EVAL_VARIANTS` 當成正式資料契約來驗證，避免研究用 variant 名稱或 item-eval method 對應在重構時漂移。

### `test_item_eval_experiment_accepts_explicit_problem_list`

這個測試補上另一條入口：明確指定 problem list 時，實驗應該跳過抽樣，並保留 ranking 與統計欄位。
