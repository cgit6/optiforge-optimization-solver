# `tests/test_solver_config_loader.py`

## 模組責任

`test_solver_config_loader.py` 驗證 solver YAML schema 與 param-set 載入器，這是 solver 建置前最重要的靜態防線。

## 公開入口/主要類型

- pytest 自動發現測試
- 主要 helper：`_write_solver_yaml`
- 主要測試群：load/select/all、schema validation、solver id vs file name、default config regression、concurrent loads

## 主要資料結構與資料契約

solver id 必須與檔名一致；`stop_condition`、capabilities、params schema 與 param index 邊界都必須被嚴格檢查。

## 資料流與控制流

helpers 先寫最小 solver YAML，再測 load、select all、schema validation、預設 config 中特定 param set 載入與 concurrent loads。

## 失敗路徑與例外條件

非法 schema 若未被攔下，會一路延伸到 machine/solver runtime；因此這個模組的 fail-fast 要求很高。

## 副作用與資源生命週期

會在 `tmp_path` 寫 solver YAML。

## 與其他模組的關係

目標模組是 `mkp.tools.solver_config_loader`。

## 對應函式索引與閱讀順序

1. `_write_solver_yaml`
2. `test_load_valid_solver_config`
3. `test_load_selects_requested_param_set`
4. `test_load_all_returns_each_param_set`
5. `test_solver_id_must_match_file_name`
6. `test_stop_condition_type_validation`
7. `test_missing_capabilities_rejected`
8. `test_stop_condition_value_validation`
9. `test_params_schema_validation`
10. `test_param_set_index_range_validation`
11. `test_load_bscasma_rl_rc_numba_param_20_from_default_configs`
12. `test_concurrent_solver_config_loads`

## 核心函式與 helper 說明

### `_write_solver_yaml`

這個 helper 產生 solver config 測試的最小 YAML。它的存在讓測試可以直接操控欄位缺漏、schema 錯誤與多 param set 佈局，而不受真實 solver 檔案內容牽動。

### 載入與 param-set 選擇測試群

`test_load_valid_solver_config`、`test_load_selects_requested_param_set`、`test_load_all_returns_each_param_set` 描述 loader 的基本責任：檔名與 `solver_id` 對齊、單一 param set 取用正確、全量模式不漏項。

### schema 驗證與 fail-fast 測試群

`test_solver_id_must_match_file_name`、`test_stop_condition_type_validation`、`test_missing_capabilities_rejected`、`test_stop_condition_value_validation`、`test_params_schema_validation`、`test_param_set_index_range_validation` 固定 loader 的資料契約。這些測試是 solver config 在進入 engine 前的第一道關卡。

### repo 內建設定回歸與併發測試

`test_load_bscasma_rl_rc_numba_param_20_from_default_configs` 保證現有預設 solver YAML 的高索引 param set 仍可正確載入；`test_concurrent_solver_config_loads` 則補上併發路徑的穩定性檢查。
