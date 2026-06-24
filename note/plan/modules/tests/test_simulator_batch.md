# `tests/test_simulator_batch.py`

## 模組責任

`test_simulator_batch.py` 是 batch path 的核心測試檔，覆蓋 task 展開、seed 分派獨立性、snapshot 選擇、machine pool 整合與 summary 寫出。

## 公開入口/主要類型

- pytest 自動發現測試
- 類型/測試 double：`CountingSolver`
- 主要 helper：`_offset_rng_factory`、`_write_problem_yaml`、`_write_solver_yaml`、`_write_solver_yaml_with_params`、`_build_problem_bank`、`_build_spec`、`_build_simulator`

## 主要資料結構與資料契約

task seed 必須只取決於 base seed、dataset、problem、repeat 與 solver variant，本身不能受 solver 順序、param 順序或 problem 子集影響。

## 資料流與控制流

helpers 建多組 simulator/bank/spec，先驗證 `expand_tasks` 與 seed map，再驗證 `run_batch` 的 machine pool/process worker 行為、錯誤傳播與 output 寫出。

## 失敗路徑與例外條件

seed independence 若被破壞，replay 與多 solver collect 都會漂移；missing solver snapshot 或 problem load error 也必須立即中止。

## 副作用與資源生命週期

會在 `tmp_path` 建 problem/solver YAML 與 batch output。

## 與其他模組的關係

目標模組是 `mkp.simulator`、`mkp.engine.bank`、`mkp.engine.repository`、`mkp.engine.configs`、`mkp.problem`、`mkp.rng`、`mkp.solver.registry` 與 `mkp.tools.show`。

## 對應函式索引與閱讀順序

1. `CountingSolver`
2. `_offset_rng_factory`
3. `_write_problem_yaml`
4. `_write_solver_yaml`
5. `_write_solver_yaml_with_params`
6. `_build_problem_bank`
7. `_build_spec`
8. `_build_simulator`
9. `test_expand_tasks_count_and_fields`
10. `test_rng_seed_reproducibility_and_independence`
11. `test_solver_snapshot_selects_requested_param_set`
12. `_seed_map`
13. `_build_seed_simulators`
14. `_build_seed_simulator`
15. `_find_seed`
16. `test_expand_tasks_order_and_seed_keys_preserve_variants`
17. `test_task_seed_is_independent_of_other_solvers_and_solver_order`
18. `test_task_seed_is_independent_of_param_order_and_count`
19. `test_task_seed_changes_when_base_seed_or_repeat_changes`
20. `test_task_seed_changes_when_dataset_changes`
21. `test_task_seed_is_independent_of_problem_order_and_subset`
22. `test_run_batch_uses_machine_pool`
23. `test_run_batch_matches_sequential_seed_assignment`
24. `test_run_batch_process_worker_uses_snapshot_run_seed`
25. `test_run_batch_fail_fast_on_problem_load_error`
26. `test_solver_snapshot_raises_when_solver_yaml_missing`
27. `test_run_task_key_error_when_solver_not_in_snapshot`
28. `test_run_batch_writes_summary_files`

## 核心函式與 helper 說明

### `CountingSolver` 與建構 helper 群

`CountingSolver` 把 solver 執行次數、`run_seed` 與第一個亂數值暴露到 `SolveResult.metadata`，方便驗證 batch 路徑是否真的共用或隔離 seed。`_build_problem_bank`、`_build_spec`、`_build_simulator`、`_build_seed_simulators`、`_build_seed_simulator` 則建立多種 simulator 佈局，用來覆蓋單 solver、多 solver、多 param set 的種子情境。

### `_seed_map` / `_find_seed`

這兩個小 helper 是 seed 契約測試的支點。它們把 `RunTask` 清單轉成可比較的 key->seed 映射，讓測試能準確指出 seed 是否受 solver 順序、problem 順序或 param set 變動污染。

### task 展開與 seed 不變量測試群

`test_expand_tasks_count_and_fields`、`test_rng_seed_reproducibility_and_independence`、`test_expand_tasks_order_and_seed_keys_preserve_variants`，以及後面一整排 `test_task_seed_*` 案例，描述 batch simulator 最重要的資料契約：同一 spec 必須穩定展開、不同維度的排列變化不得改寫不相關 task 的 seed。

### batch 執行、snapshot 與輸出測試群

`test_run_batch_uses_machine_pool`、`test_run_batch_matches_sequential_seed_assignment`、`test_run_batch_process_worker_uses_snapshot_run_seed`、`test_run_batch_fail_fast_on_problem_load_error`、`test_solver_snapshot_raises_when_solver_yaml_missing`、`test_run_task_key_error_when_solver_not_in_snapshot`、`test_run_batch_writes_summary_files` 共同保護 batch 執行面。它們涵蓋 pool 調度、process worker、snapshot 對齊與結果輸出。
