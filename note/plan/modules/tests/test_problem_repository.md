# `tests/test_problem_repository.py`

## 模組責任

`test_problem_repository.py` 驗證 YAML repository 載入、快取與並行安全性，確保問題資料源在主流程前就被正確守住。

## 公開入口/主要類型

- pytest 自動發現測試
- 主要 helper：`_write_problem_yaml`、`_repo`
- 主要測試群：合法載入、legacy path 拒絕、欄位/維度/best_known fail-fast、cache 命中、concurrent load

## 主要資料結構與資料契約

problem YAML 必須包含必要欄位、維度一致、`best_known` 合法，且 repository 第二次載入應走 cache，不可退回舊資料路徑。

## 資料流與控制流

helpers 建暫時 YAML 與 repository，再依序測合法載入、legacy path 拒絕、欄位/維度/best_known fail-fast、cache 命中與 concurrent load 安全。

## 失敗路徑與例外條件

缺欄位、dim mismatch、無效 `best_known`、cache 汙染或多執行緒載入破壞 YAML parser 都屬高風險回歸。

## 副作用與資源生命週期

會在 `tmp_path` 產生暫時 problem YAML。

## 與其他模組的關係

目標模組是 `mkp.engine.repository` 與 `mkp.problem`。

## 對應函式索引與閱讀順序

1. `_write_problem_yaml`
2. `_repo`
3. `test_load_valid_problem_yaml`
4. `test_load_does_not_fallback_to_legacy_dataset_path`
5. `test_load_missing_required_fields`
6. `test_load_dimension_mismatch`
7. `test_load_best_known_null_fails_fast`
8. `test_load_best_known_zero_fails_fast`
9. `test_load_best_known_negative_fail_fast`
10. `test_load_hits_cache_on_second_call`
11. `test_concurrent_loads_do_not_corrupt_yaml_parser`

## 核心函式與 helper 說明

### `_write_problem_yaml` / `_repo`

`_write_problem_yaml` 建立 repository 測試所需的最小 YAML，`_repo` 則集中組裝 registry 與 `ProblemRepository`。它們讓每個案例可以精準控制壞檔內容與載入路徑。

### happy path 與 legacy fallback 測試群

`test_load_valid_problem_yaml` 驗證標準 YAML 能被正確解析成 `ProblemModel`；`test_load_does_not_fallback_to_legacy_dataset_path` 則保護新 repository 不再偷偷回退到舊資料目錄。

### schema / best-known fail-fast 測試群

`test_load_missing_required_fields`、`test_load_dimension_mismatch`、`test_load_best_known_null_fails_fast`、`test_load_best_known_zero_fails_fast`、`test_load_best_known_negative_fail_fast` 共同描述 repository 的資料衛生要求。這裡的 fail-fast 決定了壞 problem 會在哪一層被阻擋。

### cache 與併發測試群

`test_load_hits_cache_on_second_call` 與 `test_concurrent_loads_do_not_corrupt_yaml_parser` 保護 repository 在重複載入與併發載入時的穩定性，避免 parser 共享狀態或 cache 邏輯出現 race condition。
