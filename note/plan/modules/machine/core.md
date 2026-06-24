# `machine/core.py`

## 模組責任

`machine/core.py` 是真正執行 solver 的地方。它負責把 `ExperimentSpec` 展開成 `RunTask`，建立 RNG，呼叫 solver，做 problem validation，並在需要時用 process pool 把 task 分派到 worker。

## 公開入口/主要類型

- `SimulatorRunRow`
- `MachineResult`
- `Machine`
- `MachinePool`
- `MachinePoolSession`

## 主要資料結構與資料契約

- `SimulatorRunRow` = `RunTask + SolveResult + ValidationReport`。
- `MachineResult` 代表單一 `(solver_id, param_set_index)` 的完整 run bucket。
- `Machine` 永遠只綁定一個 solver variant；它不能執行其他 variant 的 task。
- `MachinePool` 以 `RunTask` 為平行化單位，不是以 problem 或 machine 為單位。
- `MachinePoolSession` 是 experiment collect/replay 流程使用的可重用 worker pool。
- process worker 端有三個全域資源：
  - `_worker_solver_configs`
  - `_worker_rng_factory`
  - `_worker_solver_registry`

## 資料流與控制流

1. `Machine.expand_tasks(...)` 依 `ExperimentSpec`、seed strategy 與 base seed 展開全量 task。
2. `Machine.expand_task(...)` 提供單一 round 的 lazy task 建立，給 `cli.exp` 的 window scheduler 用。
3. `Machine.run_task(...)` 取出 problem、solver config、RNG、solver instance，呼叫 `solver.solve(...)`。
4. 解完後立刻用 `problem.validate(...)` 產生 `ValidationReport`，包成 `SimulatorRunRow`。
5. `MachinePool.run(...)` 或 `run_tasks(...)` 決定是 serial 還是 process pool。
6. process 模式下，initializer `_configure_process_worker(...)` 會 attach `ProblemBank`、複製 solver config、註冊 solver builders。
7. worker 執行 `_run_task_process(...)` 只回傳 `SolveResult`；主行程再重新做 validation 並重建 `SimulatorRunRow`。

## 失敗路徑與例外條件

- `Machine` 建立時會驗證 solver id 屬於 spec，param index 非負。
- `Machine.run_task(...)` 收到不是自己 variant 的 task 會直接拒絕。
- `base_seed` 沒有在 spec 或參數中提供時，`_resolve_base_seed(...)` 會失敗。
- process 模式若 task 要求的 solver 不在 `solverBuilders()` 註冊表，`_assert_process_solvers_registered(...)` 會中止。
- worker 若未先初始化 bank/config/registry，`_run_task_process(...)` 會丟 `RuntimeError`。
- `MachinePoolSession.run_tasks(...)` 中，任何一個 future 失敗都會取消 pending future 並把例外往上拋。

## 副作用與資源生命週期

- `Machine.run_task(...)` 會把 `run_seed` 注入 solver config 副本，這是 solver 執行前的最後一層設定裝配。
- process 模式會建立 `ProcessPoolExecutor(spawn)`；shared memory 是由主行程提供 pack、worker attach。
- `MachinePoolSession` 讓多輪 collect 共用同一個 pool；`close()` 或 context manager `__exit__` 才真正 shutdown。
- validation 在主行程重做，代表 shared memory 中的 problem model 仍是單一真實來源，不依賴 worker 回傳驗證結果。

## 與其他模組的關係

- 上游：`simulator.core` 建立 machine 與 pool；`experiment.experiment` 直接使用 `MachinePoolSession` 做 streaming collect。
- 依賴：`engine.bank`、`engine.configs`、`engine.models`、`problem.validation`、`rng`、`solver.registry`。
- 下游：`tools.stat` 只吃 `MachineResult` / `SimulatorRunRow`，不介入 solver 執行。

## 核心函式與 helper 說明

### `Machine.expand_tasks(...)` / `Machine.expand_task(...)`

- `expand_tasks(...)`：
  - 目的：展開該 solver variant 全量 `(problem_id, repeat_index)` 工單
  - 關鍵步驟：`_resolve_base_seed(...)` -> `_seed_context()` -> `SeedStrategy.build_task_seeds(...)` -> `_make_task(...)`
  - 資料契約：同一台 `Machine` 只會產出自己的 `(solver_id, param_set_index)` 任務
- `expand_task(...)`：
  - 目的：只建立單一 repeat 工單，供 `cli.exp` 的 sliding window scheduler 使用
  - 重要性：避免 collect 流程一次展開所有未來 repeat，讓 evaluator 能邊跑邊決策

### `_seed_context()` / `_make_task()` / `_resolve_base_seed(...)`

- `_seed_context()`：把 spec 收斂成 seed 派生所需的最小上下文。
- `_make_task()`：唯一的 `RunTask` 建立點，保證 task identity 一致。
- `_resolve_base_seed(...)`：統一「呼叫參數優先，否則退回 `ExperimentSpec.base_seed`」的規則；若兩邊都沒有，直接 fail-fast。

### `Machine.run_task(...)`

- 目的：執行單一工單，產出 `SimulatorRunRow`。
- 控制流：
  1. 驗證 task 是否屬於本 variant
  2. 從 `ProblemBank` 取題
  3. 從 `SolverConfigsSnapshot` 取 config 副本並注入 `run_seed`
  4. 建 RNG、建 solver
  5. `solver.solve(...)`
  6. `problem.validate(...)`
  7. 包成 `SimulatorRunRow`
- 副作用：只改本地 config 副本，不改快照原件。
- 修改風險：如果把 validation 移出這裡，serial path 與 process path 的行為就會分叉。

### `Machine.run(...)`

- 目的：serial 執行本 variant 的全量工單。
- 角色：是 `worker_count == 1` 時最直接的執行路徑，也是很多測試的 baseline。

### `MachinePool.run(...)` / `run_tasks(...)`

- `run(...)`：吃整台 machine 的全量 tasks。
- `run_tasks(...)`：吃呼叫端挑好的 selected tasks。
- 兩者共同邏輯：
  - serial 模式直接回落到 `Machine.run(...)` 或 `_run_grouped_tasks_serial(...)`
  - process 模式先驗證 solver 是否都在 `solverBuilders()` registry 中，再走 pool
- 修改風險：這裡的 worker 數計算與 task flattening 決定平行度；調錯會直接改變 collect 視窗與測試行為。

### `MachinePool._run_tasks_in_process_pool(...)`

- 目的：建立一次性 process pool，把 `RunTask` 分發給 worker。
- 主要輸入來源：第一台 machine 的 `ProblemBank` packs、problem specs、solver config snapshot、rng factory。
- 重要設計：worker 只回傳 `SolveResult`；主行程保留 validation，確保唯一真實的 validation 邏輯與 problem model 來源仍在主行程。

### `MachinePoolSession`

- 角色：可重用 pool 的 streaming scheduler，供 `Experiment._run_problem(...)` 在多個 window 之間重用 worker。
- `run_tasks(...)`：與 `MachinePool.run_tasks(...)` 語意相同，但底下 pool 可跨多輪保留。
- `_ensure_pool()`：第一次使用才 spawn；若沒有 machines 則拒絕建立。
- `close()` / `__exit__()`：是 collect 流程釋放 worker 的正式收尾點。

### `_group_tasks_by_machine(...)` / `_run_grouped_tasks_serial(...)`

- `_group_tasks_by_machine(...)`：把 selected tasks 依 `(solver_id, param_set_index)` 分桶，並驗證每個 task 都能對應到現有 machine。
- `_run_grouped_tasks_serial(...)`：selected-task 路徑的 serial fallback；保證即使不開 process，也能沿同一分桶語意執行。

### `_build_machine_results(...)`

- 目的：把 process worker 回傳的 `SolveResult` 重新包回 `MachineResult`。
- 關鍵責任：在主行程重新取 problem、重新做 `problem.validate(...)`，使 serial 與 process 兩路在輸出前重新匯合。

### `_configure_process_worker(...)` / `_assert_process_solvers_registered(...)` / `_run_task_process(...)` / `_task_key(...)`

- `_configure_process_worker(...)`：
  - worker initializer
  - attach `ProblemBank`
  - 深複製 solver configs
  - 建立 worker-local `SolverRegistry`
- `_assert_process_solvers_registered(...)`：
  - 防止 process worker 收到無法由 `solverBuilders()` 建出的 solver
  - 這是 process path 專屬的 capability gate
- `_run_task_process(...)`：
  - worker 端真正執行 `solver.solve(...)`
  - 不做 validation
- `_task_key(...)`：
  - 定義 process 回傳結果的 join key
  - key 若改變，`_build_machine_results(...)` 與 replay 行為都要一起改

## 對應函式索引與閱讀順序

1. `SimulatorRunRow`
2. `MachineResult`
3. `Machine`
4. `Machine.task_count`
5. `Machine.params`
6. `Machine.expand_tasks`
7. `Machine.expand_task`
8. `Machine.run_task`
9. `Machine.run`
10. `MachinePool`
11. `MachinePool.run`
12. `MachinePool.run_tasks`
13. `MachinePool.session`
14. `MachinePool._run_tasks_in_process_pool`
15. `MachinePoolSession`
16. `MachinePoolSession.run_tasks`
17. `MachinePoolSession._ensure_pool`
18. `_group_tasks_by_machine`
19. `_run_grouped_tasks_serial`
20. `_build_machine_results`
21. `_configure_process_worker`
22. `_assert_process_solvers_registered`
23. `_run_task_process`
24. `_task_key`
