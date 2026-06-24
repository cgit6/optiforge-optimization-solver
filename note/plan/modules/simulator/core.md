# `simulator/core.py`

## 模組責任

`simulator/core.py` 是單一 solver 的調度層。它不直接做輸出，也不直接管 YAML，而是把某個 solver 的所有 param set 封裝成多台 `Machine`，再以順序或 batch 方式執行。

## 公開入口/主要類型

- `SimulatorResult`
- `Simulator`
- `_progress_bar(...)`

## 主要資料結構與資料契約

- `SimulatorResult.machine_results` 以 `(solver_id, param_set_index)` 分桶保存結果。
- `Simulator` 只接受單一 solver 的 `ExperimentSpec`；多 solver 需要由 `SimulationBundle.new_simulators()` 拆開。
- `Simulator.machines` 是本 solver 的所有 param set 執行單位。

## 資料流與控制流

1. `SimulationBundle.new_simulator()` 建立 `Simulator`。
2. `Simulator.__init__()` 會依 `SolverConfigsSnapshot.param_set_indices(...)` 建立多台 `Machine`。
3. `run_sequential()` 用 `MachinePool(worker_count=1)` 順序執行。
4. `run_batch()` 則用 `ExperimentSpec.worker_count` 建立 `MachinePool` 做全域 task 併發。
5. `MachinePool.run(...)` 回傳各 variant 的 `MachineResult`，再包成 `SimulatorResult`。
6. `tools.stat` 與 `tools.show` 從 `SimulatorResult` 開始做統計與輸出。

## 失敗路徑與例外條件

- `spec.solver_ids` 長度不是 1 時，`Simulator` 建立就會失敗。
- `run_task(...)` 收到不屬於本 simulator solver 的 task，會丟 `ValueError`。
- `_machine_for_task(...)` 找不到對應 param set 時會丟 `KeyError`。
- 真正 solver 執行錯誤多半在 `Machine` 或 process worker 層浮出。

## 副作用與資源生命週期

- `_progress_bar(...)` 會向 stderr 建立 tqdm 進度列。
- `close()` 會直接關閉底層 `ProblemBank` shared memory；因此同一份 bank 被多個 simulator 共用時，只應在最外層流程關一次。
- `run_batch()` 會間接建立 process pool，但 pool 生命週期由 `MachinePool` 管理。

## 與其他模組的關係

- 上游：`engine.assembly.SimulationBundle` 建出 simulator。
- 下游：`machine.core` 真的負責 task 展開與 solver 執行。
- 輸出層：`tools.stat`、`tools.show` 只吃 `SimulatorResult`，不回頭碰 solver 或 problem bank。

## 核心函式與 helper 說明

### `SimulatorResult.__post_init__()`

- 目的：檢查 `machine_results` 內不可出現重複的 `(solver_id, param_set_index)` variant。
- 資料契約：同一個 `SimulatorResult` 必須是單一 solver family 的去重結果集合，否則 `by_variant` 與 `by_run` 都會失去穩定索引語意。
- 失敗路徑：一旦掃到重複 variant，直接丟 `ValueError`，避免下游統計靜默覆蓋結果。
- 修改風險：若未來允許同一 variant 出現多個 `MachineResult`，`tools.stat` 與 `cli.replay` 的聚合假設都必須一起改。

### `SimulatorResult.by_variant`

- 目的：把 tuple 型結果轉成以 `(solver_id, param_set_index)` 為 key 的查表介面。
- 主要輸出：`dict[tuple[str, int], MachineResult]`，供 replay、測試與手動診斷快速定位某一個 solver variant。
- 注意事項：它假設 `__post_init__()` 已保證 key 唯一，因此不再做衝突處理。

### `SimulatorResult.by_run(problem_id, repeat_index)`

- 目的：把不同 param set 的 `SimulatorRunRow` 按「同一題、同一 repeat」收斂成一組可比較列。
- 控制流：逐台 `MachineResult` 收集符合條件的 row，最後依 `(solver_id, param_set_index)` 排序。
- 主要呼叫者：`experiment.experiment` 的 evaluator 路徑與統計測試。
- 修改風險：排序鍵一旦變動，summary 與 replay 的輸出順序也會跟著變。

### `SimulatorResult.iter_rows()`

- 目的：把所有 `MachineResult.rows` 展平成單一 tuple，供 `tools.stat`、`tools.show`、測試直接掃描。
- 資料契約：保留 `machine_results` 原本順序，不再重排 row。
- 角色：這是 runtime 鏈與輸出/統計鏈最常見的接點之一。

### `Simulator._build_machines()`

- 目的：依 `SolverConfigsSnapshot.param_set_indices(solver_id)` 建立本 simulator 內的所有 `Machine`。
- 控制流：對單一 `solver_id` 的每個 `param_set_index` 建一台 `Machine`，並注入同一份 `ProblemBank`、`SeedStrategy`、`RngFactory`。
- 資料契約：`Simulator` 僅接受單一 solver；多 solver 分流責任在 `SimulationBundle.new_simulators()`。
- 修改風險：若把 machine 建構邏輯搬到別處，base seed 與 task ordering 的一致性要重新驗證。

### `Simulator.expand_tasks(base_seed=None)`

- 目的：把所有 machine 的任務展開成一份全域 `RunTask` 清單。
- 主要輸入：可選 `base_seed`；若未提供，沿用 `ExperimentSpec.base_seed` 的共享種子語意。
- 在流程中的角色：`MachinePool.run(...)` 會先吃這份全域 task 清單，再依 task key 交回各 machine 執行。
- 修改風險：task 展開順序會直接影響 batch 模式下的 seed 分配與測試基線。

### `Simulator._run_with_pool(worker_count)`

- 目的：統一順序執行與 batch 執行的共同框架。
- 控制流：先計算 `total_tasks`，再建立 `_progress_bar(...)` 與 `MachinePool`，最後把 pool 回傳的 `MachineResult` 包成 `SimulatorResult`。
- 副作用：建立 tqdm 進度列、建立 `MachinePool`，並間接觸發 worker attach `ProblemBank`。
- 失敗路徑：任何 worker/solver 例外都會在這裡往上浮；本函式不吞錯，只保證 pool context 結束。

### `Simulator._machine_for_task(task)`

- 目的：根據 `task.solver_id` 與 `task.param_set_index` 找到對應 `Machine`。
- 失敗路徑：solver id 不屬於本 simulator 時丟 `ValueError`；param set 缺失時丟 `KeyError`。
- 角色：它是 `run_task(...)` 與 pool worker dispatch 的邊界檢查點。

### `_progress_bar(total, desc, enabled=True)`

- 目的：建立適合 CLI 執行環境的 tqdm progress bar。
- 控制條件：只有 `enabled` 且 stderr 是 TTY 時才顯示進度列，避免測試與非互動環境產生噪音。
- 副作用：向 stderr 輸出進度資訊。

## 對應函式索引與閱讀順序

1. `SimulatorResult`
2. `SimulatorResult.by_variant`
3. `SimulatorResult.by_run`
4. `SimulatorResult.iter_rows`
5. `Simulator`
6. `Simulator.run_task`
7. `Simulator.expand_tasks`
8. `Simulator.run_sequential`
9. `Simulator.run_batch`
10. `Simulator._run_with_pool`
11. `Simulator._build_machines`
12. `Simulator._machine_for_task`
13. `_progress_bar`
