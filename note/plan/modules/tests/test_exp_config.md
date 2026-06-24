# `tests/test_exp_config.py`

## 模組責任

`test_exp_config.py` 驗證 `cli/exp/exp_cfg.yaml` 解析器與 `ExperimentConfig` schema，並補一個 `cli.exp.main` smoke path。

## 公開入口/主要類型

- pytest 自動發現測試
- 主要 helper：`_write_problem_yaml`、`_write_solver_yaml`、`_valid_config_text`、`_write_valid_project`
- 主要測試群：build success、main smoke、schema 遷移拒絕、param index 邊界、baseline parse、capability mismatch

## 主要資料結構與資料契約

新 schema 必須接受 `solver -> param_idx[]`、problem-level evaluation 與 baseline 欄位；舊欄位名稱與舊結構必須被拒絕。

## 資料流與控制流

helpers 建最小 project、寫 config text，再測 build success、main smoke、欄位遷移拒絕、param index 邊界、baseline parse 與 capability mismatch。

## 失敗路徑與例外條件

缺 problem YAML、solver/problem capability 不符、無效整數欄位、舊版 worker/dataset 評估 schema 未被拒絕，都會破壞 collect 前置驗證。

## 副作用與資源生命週期

會在 `tmp_path` 寫出 exp/problem/solver YAML。

## 與其他模組的關係

目標模組是 `mkp.experiment`、`mkp.cli.exp` 與 `mkp.tools.solver_config_loader`。

## 對應函式索引與閱讀順序

1. `_write_problem_yaml`
2. `_write_solver_yaml`
3. `_valid_config_text`
4. `_write_valid_project`
5. `test_build_sample_exp_cfg_success`
6. `test_cli_exp_main_runs_experiment`
7. `test_load_config_rejects_removed_worker_key`
8. `test_load_config_rejects_old_dataset_level_evaluation`
9. `test_load_config_rejects_old_problem_string_list`
10. `test_load_config_parses_solver_param_idx_list`
11. `test_load_config_rejects_solver_param_idx_out_of_range`
12. `test_load_config_rejects_invalid_core_fields`
13. `test_load_config_allows_empty_problem_evaluation_list`
14. `test_load_config_rejects_null_problem_evaluation`
15. `test_load_config_parses_problem_baselines`
16. `test_load_config_rejects_missing_problem_yaml`
17. `test_load_config_rejects_solver_problem_capability_mismatch`

## 核心函式與 helper 說明

### project 建構 helper 群

`_write_problem_yaml`、`_write_solver_yaml`、`_valid_config_text`、`_write_valid_project` 共同建立 experiment config 測試治具。它們讓每個案例可以精準操控 YAML schema、solver variants、baseline 與 problem 清單。

### `test_build_sample_exp_cfg_success` / `test_cli_exp_main_runs_experiment`

前者直接驗證 repo 內建 `cli/exp/exp_cfg.yaml` 能被載入成完整 `Experiment`，並檢查實際 solver param set 內容；後者則補上 `cli.exp` 入口真的能 build 並產出 `summary.json`。

### `load_config(...)` schema / backward-compat fail-fast 測試群

`test_load_config_rejects_removed_worker_key`、`test_load_config_rejects_old_dataset_level_evaluation`、`test_load_config_rejects_old_problem_string_list`、`test_load_config_rejects_invalid_core_fields` 固定 config loader 對舊 schema 與非法欄位的拒絕行為。

### solver variant / baseline / capability 測試群

`test_load_config_parses_solver_param_idx_list`、`test_load_config_rejects_solver_param_idx_out_of_range`、`test_load_config_allows_empty_problem_evaluation_list`、`test_load_config_rejects_null_problem_evaluation`、`test_load_config_parses_problem_baselines`、`test_load_config_rejects_missing_problem_yaml`、`test_load_config_rejects_solver_problem_capability_mismatch` 共同描述 experiment config 在 solver 變體、evaluation 與 problem/solver 相容性上的資料契約。
