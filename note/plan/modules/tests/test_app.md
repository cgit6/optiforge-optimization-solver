# `tests/test_app.py`

## 模組責任

`test_app.py` 覆蓋 `cli.run` 的命令列入口與 `ExperimentSpec` 建構邏輯，重點是新 CLI 預設值、單 solver/單 param set 約束、worker 參數，以及 problem/solver YAML 缺失時的 fail-fast 行為。

## 公開入口/主要類型

- pytest 自動發現測試
- 主要 helper：`_write_problem_yaml`、`_write_solver_yaml`
- 主要測試群：`test_create_experiment_spec_*`、`test_app_cli_*`、`test_validate_execute_args_rejects_multiple_solvers_for_cli_run`

## 主要資料結構與資料契約

測試會在 `tmp_path` 下建立最小可跑的 problem/solver YAML；CLI 回傳結果必須對應到指定 solver 與 param set，且 `validate_execute_args(...)` 必須拒絕多 solver 或非法 `--set`。

## 資料流與控制流

helpers 先寫出最小 YAML，測試再呼叫 `mkp.cli.run` 的 parser 與 main path，最後檢查 `ExperimentSpec`、輸出 rows、錯誤訊息與 CLI exit 行為。

## 失敗路徑與例外條件

主失敗面包括缺 problem YAML、缺 solver YAML、未知 param set、必要參數缺漏與不被允許的多 solver `cli.run` 用法。

## 副作用與資源生命週期

會在 `tmp_path` 建立暫時 YAML 與 output 目錄；沒有跨測試共享狀態。

## 與其他模組的關係

目標模組是 `mkp.cli.run` 與 `mkp.engine.models`；它補 `engine`/`simulator` 測試之前的 CLI 輸入邊界。

## 對應函式索引與閱讀順序

1. `_write_problem_yaml`
2. `_write_solver_yaml`
3. `test_create_experiment_spec_uses_new_cli_defaults`
4. `test_create_experiment_spec_rejects_invalid_worker_count`
5. `test_app_cli_success_runs_selected_solver_param`
6. `test_app_cli_worker_runs_batch`
7. `test_app_cli_fail_fast_when_problem_yaml_missing`
8. `test_app_cli_fail_fast_when_solver_yaml_missing`
9. `test_app_cli_missing_required_arg_rejected`
10. `test_app_cli_missing_set_rejected`
11. `test_app_cli_rejects_unknown_param_set`
12. `test_validate_execute_args_rejects_multiple_solvers_for_cli_run`

## 核心函式與 helper 說明

### `_write_problem_yaml` / `_write_solver_yaml`

這兩個 helper 專門產生最小可執行的 problem / solver YAML，讓 CLI 測試不需要依賴 repo 既有設定檔。它們固定了 `test_app.py` 的輸入契約：如果後續 CLI 改成要求更多必要欄位，這兩個 helper 通常會先失效。

### `test_create_experiment_spec_*`

這組測試鎖定 CLI 參數轉 `ExperimentSpec` 的前置規則。`test_create_experiment_spec_uses_new_cli_defaults` 檢查新 CLI 預設值，`test_create_experiment_spec_rejects_invalid_worker_count` 則保證 worker 數量在進入 `Engine.build(...)` 前就被拒絕。

### `test_app_cli_success_runs_selected_solver_param` / `test_app_cli_worker_runs_batch`

這兩個案例是 `cli.run.main` 的 happy path。前者確認單一 solver param set 能被正確展開並執行，後者確認 worker 模式會走 batch 路徑而不是退回單步執行。

### fail-fast 與參數驗證測試群

`test_app_cli_fail_fast_when_problem_yaml_missing`、`test_app_cli_fail_fast_when_solver_yaml_missing`、`test_app_cli_missing_required_arg_rejected`、`test_app_cli_missing_set_rejected`、`test_app_cli_rejects_unknown_param_set`、`test_validate_execute_args_rejects_multiple_solvers_for_cli_run` 共同保護 CLI 邊界。它們的角色不是驗證求解品質，而是確保錯誤輸入不會進入 runtime 主鏈後段。
