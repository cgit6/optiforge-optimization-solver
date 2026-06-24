# `tests/test_machine.py`

## 模組責任

`test_machine.py` 驗證 `Machine`、`MachinePool` 與 process worker builder path，確保 task 展開、variant 篩選、shared seed 與 worker limit 都符合設計。

## 公開入口/主要類型

- pytest 自動發現測試
- 類型/測試 double：`RecordingSolver`
- 主要 helper：`_write_problem_yaml`、`_write_solver_yaml`、`_build_machine_context`、`_machine`

## 主要資料結構與資料契約

`Machine` 只能處理自己的 solver variant；pool 執行時必須保留同一 repeat 跨 param set 的 shared seed，且 worker limit 取決於 task 總數而非 machine 數。

## 資料流與控制流

透過 `RecordingSolver` 與最小 repository/bank/config 建立 machine context，再依序測 variant 展開、selected task、rows 分桶、pool run、shared seed 與 process builder 註冊需求。

## 失敗路徑與例外條件

若 machine 越界執行其他 variant、shared seed 漂移或 worker 缺 builder 仍被啟動，都會破壞 batch/replay 契約。

## 副作用與資源生命週期

會建臨時 YAML 與少量 in-memory machine context；不寫正式 output。

## 與其他模組的關係

目標模組是 `mkp.machine`、`mkp.engine.bank`、`mkp.engine.configs`、`mkp.engine.repository`、`mkp.rng` 與 `mkp.solver.registry`。

## 對應函式索引與閱讀順序

1. `RecordingSolver`
2. `_write_problem_yaml`
3. `_write_solver_yaml`
4. `_build_machine_context`
5. `_machine`
6. `test_machine_expands_only_one_solver_param_variant`
7. `test_machine_expands_single_selected_task`
8. `test_machine_result_contains_only_own_variant_rows`
9. `test_machine_pool_run_tasks_executes_only_selected_round`
10. `test_machine_pool_worker_limit_uses_total_tasks_not_machine_count`
11. `test_machine_pool_preserves_shared_run_seed_across_param_variants`
12. `test_machine_pool_process_requires_builder_registered_solver`

## 核心函式與 helper 說明

### `RecordingSolver`

這個 stub solver 把 machine 測試從演算法本身解耦，只保留 `SolveResult` 契約與 `run_seed` 回填行為。它的價值在於讓測試專注於 task 展開、variant 隔離與 pool 調度。

### `_build_machine_context` / `_machine`

這兩個 helper 組裝最小 `ProblemBank`、`SolverRegistry`、`SolverConfigsSnapshot` 與 `Machine`。前者建立共享測試環境，後者再固定單一 `param_set_index`，讓每個案例都能直接指向某一個 variant。

### 單機 task 展開與結果隔離測試群

`test_machine_expands_only_one_solver_param_variant`、`test_machine_expands_single_selected_task`、`test_machine_result_contains_only_own_variant_rows` 描述 `Machine` 的本體契約：單一 machine 只能對應一個 solver 變體，且輸出列不得混入其他 param set 的結果。

### `MachinePool` 調度、worker 與 seed 契約測試群

`test_machine_pool_run_tasks_executes_only_selected_round`、`test_machine_pool_worker_limit_uses_total_tasks_not_machine_count`、`test_machine_pool_preserves_shared_run_seed_across_param_variants`、`test_machine_pool_process_requires_builder_registered_solver` 鎖定 pool 層語意。這些測試保護的是跨變體同 round 共 seed、process worker 建構路徑、以及 worker 上限以 task 數而非 machine 數為準。
