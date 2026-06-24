# `problem/validation.py`

## 模組責任

`problem/validation.py` 定義 objective/direction 的正規化規則，並把 solver 回傳結果轉成可統計、可輸出的 `ValidationReport`。它是 solver 結果與統計層之間的品質閘門。

## 公開入口/主要類型

- `normalize_scalar_objective(...)`
- `normalize_objective_value(...)`
- `normalize_direction_spec(...)`
- `is_scalar_objective(...)`
- `objective_values_equal(...)`
- `best_known_status_and_gap(...)`
- `build_validation_report(...)`
- `ValidationReport`

## 主要資料結構與資料契約

- `DirectionSpec` 可為單一 `max`/`min`，或 tuple 形式的多目標方向。
- `ObjectiveValue` 可為 scalar 或 tuple；`ObjectiveGap` 允許 `None`。
- `ValidationReport` 統一提供：
  - 可行性
  - objective 是否與 problem 回算值一致
  - recomputed objective
  - best-known 是否達成與 gap
  - 問題型別、編碼、方向、best known
  - 額外 metadata

## 資料流與控制流

1. solver 先回傳 `SolveResult`。
2. 具體 problem 的 `validate(...)` 呼叫 `build_validation_report(...)`。
3. `build_validation_report(...)` 先檢查 constraint violation，再視情況重算 objective。
4. 若解可行，就用 `objective_values_equal(...)` 比對 solver 宣告值與 problem 回算值。
5. 接著用 `best_known_status_and_gap(...)` 計算 best-known 達成狀態與 gap。
6. 結果包成 `ValidationReport`，交給 `machine.core`、`tools.stat`、`tools.show`。

## 失敗路徑與例外條件

- direction 非 `max`/`min` 或維度不一致時，正規化階段會失敗。
- objective 型別不是數值或空 tuple 時，會丟 `ValueError`。
- 多目標時，`best_known` 維度與 objective 維度不一致會失敗。
- `ValidationReport.__post_init__` 也會再次正規化欄位，避免上游塞入不一致資料。

## 副作用與資源生命週期

- 無 I/O 或 shared memory 副作用。
- 本模組的核心副作用是「重新計算」objective 與 gap，這會影響下游統計時哪些 run 被視為有效。

## 與其他模組的關係

- 上游：`problem.interface.Problem.validate(...)` 與具體 problem 類別依賴這裡。
- 中游：`machine.core` 將 `ValidationReport` 與 `SolveResult` 綁成 `SimulatorRunRow`。
- 下游：`tools.stat` 依 `objective_valid`、`best_known_gap`、`direction` 等欄位決定摘要指標。

## 核心函式與 helper 說明

### `normalize_scalar_objective(value, name)`

- 目的：把單一 objective 值正規化成可比較的數值標量。
- 失敗路徑：非數值輸入直接丟 `ValueError`。
- 角色：它是所有 objective 正規化的最小單位，後面的 tuple/multi-objective 邏輯都建在它上面。

### `normalize_objective_value(value, name)`

- 目的：接受 scalar 或 tuple，統一轉成合法的 objective 表示。
- 控制流：scalar 走 `normalize_scalar_objective(...)`；tuple/list 逐項正規化，並拒絕空 tuple。
- 修改風險：若放寬 tuple 規則，`ValidationReport` 與 best-known gap 的維度對齊邏輯要一起調整。

### `normalize_direction_spec(value)`

- 目的：把 `max` / `min` 或其 tuple/list 表示收斂成正式 `DirectionSpec`。
- 在流程中的角色：problem metadata、solver capability、validation gap 計算都依賴這個共同方向語意。

### `objective_values_equal(left, right)`

- 目的：比較 solver 回報 objective 與 problem 回算 objective 是否一致。
- 控制流：先正規化左右值，再逐維比較；浮點標量會透過 `_scalar_objectives_equal(...)` 做容忍誤差處理。
- 角色：這是 `objective_valid` 的核心判定器。

### `best_known_status_and_gap(best_known, objective, direction)`

- 目的：根據方向規格計算是否達到 best known，以及差距 `gap`。
- 資料契約：支援 scalar 與 tuple objective，但維度必須完全對齊。
- 在流程中的角色：`tools.stat` 與 evaluator 之後會用它的輸出做成功率與相對差距統計。

### `build_validation_report(problem, solve_result, solution, metadata=None)`

- 目的：把 solver 的原始輸出重算成可統計的 `ValidationReport`。
- 控制流：先判 infeasible；若可行再用 `problem.fitness(...)` 重算 objective，然後比較 solver 宣告值、best known 與 gap，最後包成 dataclass。
- 失敗路徑：本函式不隱藏 `problem.fitness(...)` 或 direction/objective 正規化錯誤，因為這些都是上游契約錯誤。
- 副作用：無 I/O，但它會重寫「這個 run 是否有效」的最終判定。

### `ValidationReport.__post_init__()`

- 目的：在 dataclass 建立後再次正規化 `recomputed_objective`、`best_known`、`best_known_gap`、`direction` 與 `metadata`。
- 角色：它保證任何來源建立的 report 都維持統一欄位型別。

### `_best_known_gap(best_known, objective, direction)`

- 目的：計算單一維度的 direction-aware 差距。
- 在演算法中的角色：這是 multi-objective gap 向量計算的最底層 helper，決定 `max` 與 `min` 問題的正負號語意。

## 對應函式索引與閱讀順序

1. `normalize_scalar_objective`
2. `normalize_objective_value`
3. `normalize_direction_spec`
4. `is_scalar_objective`
5. `objective_values_equal`
6. `best_known_status_and_gap`
7. `build_validation_report`
8. `ValidationReport`
9. `_objective_tuple`
10. `_direction_tuple`
11. `_scalar_objectives_equal`
12. `_best_known_gap`
