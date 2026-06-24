# `tests/test_stage1_validation.py`

## 模組責任

`test_stage1_validation.py` 是 `valid.stage1_validation` 的 smoke/unit bridge，確保 stage1 refactor 驗證腳本的最小輔助函式行為穩定。

## 公開入口/主要類型

- pytest 自動發現測試
- 主要測試群：smoke scenarios、reproducible stub app、diff classification、ensure problem YAML

## 主要資料結構與資料契約

`build_smoke_scenarios()` 必須產生最小可跑案例；`check_refactor_reproducible(...)` 對穩定 stub app 必須回傳 true；`classify_diff(...)` 與 `ensure_problem_yaml(...)` 必須維持預期分類與檔案建立語意。

## 資料流與控制流

測試直接呼叫 validation helper，而不執行整個舊版腳本與新 CLI 比對流程。

## 失敗路徑與例外條件

若 stage1 validation 的基本 helper 漂移，較重的人工/批次 refactor 驗證就會失去可信度。

## 副作用與資源生命週期

可能在暫時目錄建立 problem YAML。

## 與其他模組的關係

目標模組是 `mkp.valid.stage1_validation`。

## 對應函式索引與閱讀順序

1. `test_build_smoke_scenarios_has_expected_minimum_shape`
2. `test_check_refactor_reproducible_true_for_stable_app_stub`
3. `test_classify_diff_behaviors`
4. `test_ensure_problem_yaml_creates_yaml_when_missing`

## 核心函式與 helper 說明

### `test_build_smoke_scenarios_has_expected_minimum_shape`

這個測試固定 `valid.stage1_validation.build_smoke_scenarios()` 的最小輸出形狀，避免 smoke scenario 被改到空集合或缺少必要欄位。

### `test_check_refactor_reproducible_true_for_stable_app_stub`

這個案例用穩定的 app stub 驗證 `check_refactor_reproducible(...)` 的判斷語意，確保 stage1 validation 的「同 seed 連跑兩次要一致」不是只靠外部腳本偶然成立。

### `test_classify_diff_behaviors`

這個測試鎖定 `classify_diff(...)` 的分類規則，特別是 `baseline_missing` 與 `objective_mismatch` 的區分。它保護的是報表語意，而不是求解本身。

### `test_ensure_problem_yaml_creates_yaml_when_missing`

這個案例確保 stage1 validation 在跑 legacy/refactor 對照前，能先補齊標準 problem YAML。沒有這個保證，後續 CLI 路徑就無法和舊腳本共用同一題目來源。
