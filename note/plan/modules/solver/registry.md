# `solver/registry.py`

## 模組責任

`solver/registry.py` 定義 solver protocol 與 builder registry。它是 `Machine` 建立 solver instance 的唯一正式入口。

## 公開入口/主要類型

- `Solver` protocol
- `SolverBuilder`
- `SolverRegistry`
- `StubMaxIterationsSolver`

## 主要資料結構與資料契約

- `Solver.solve(problem, config, rng) -> SolveResult` 是所有 solver 的最低契約。
- `SolverBuilder` 是零參數 callable，回傳一個 solver instance。
- `SolverRegistry` 內部以 `solver_id -> builder` 映射保存可用 solver。
- `StubMaxIterationsSolver` 是契約測試用 stub，不是正式最佳化演算法。

## 資料流與控制流

1. `engine.builders.solverBuilders()` 建立各 solver builder 映射。
2. `SimulationBundle._new_solver_registry()` 把 builder 註冊進 `SolverRegistry`。
3. `Machine.run_task(...)` 依 `RunTask.solver_id` 呼叫 `registry.create(...)` 建 solver。
4. solver 執行後回傳 `SolveResult`。

## 失敗路徑與例外條件

- 空 `solver_id` 或重複註冊會失敗。
- `get(...)` / `create(...)` 查詢未註冊 solver 時會丟 `KeyError`。
- `StubMaxIterationsSolver` 只支援 MKP problem 與 `max_iterations` stop condition。

## 副作用與資源生命週期

- 主要副作用是改寫 registry 內部 builder 表。
- registry 通常是短生命週期物件，由 bundle 或 worker initializer 建立後供該流程使用。

## 與其他模組的關係

- 上游：`engine.assembly` 與 `machine.core._configure_process_worker(...)`。
- 下游：所有具體 solver adapter 都必須實作 `Solver` protocol。

## 核心函式與 helper 說明

### `SolverRegistry.register(solver_id, builder)`

- 目的：把 `solver_id -> builder` 正式放進 runtime solver registry。
- 失敗路徑：空 `solver_id` 與重複註冊都會直接丟 `ValueError`。
- 角色：這是 solver family 是否真的能被 `Machine` 建立的中心閘門。

### `SolverRegistry.get(solver_id)` / `create(solver_id)`

- 目的：先取 builder，再建立 solver instance。
- 注意事項：`create(...)` 不做額外 caching，每次都回傳新 solver；這對持有內部可變狀態的 solver 很重要。

### `StubMaxIterationsSolver.solve(...)`

- 目的：提供最小可執行 solver 契約，供 registry、machine 與 integration test 驗證。
- 資料契約：只支援 `MKPProblem` 與 `stop_condition.type=max_iterations`。
- 維護意義：這個 stub 把「solver 介面對 engine 的最低要求」固定下來。

## 對應函式索引與閱讀順序

1. `Solver`
2. `SolverBuilder`
3. `SolverRegistry.register`
4. `SolverRegistry.get`
5. `SolverRegistry.create`
6. `StubMaxIterationsSolver.solve`
