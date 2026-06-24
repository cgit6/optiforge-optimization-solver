# `tools/stat.py`

## 模組責任

`tools/stat.py` 把 `SimulatorResult` / `MachineResult` 轉成標準化的 `ResultEntry` 清單，再彙整成 `SummaryReport`。它是執行層與輸出層之間的統計核心。

## 公開入口/主要類型

- `ResultEntry`
- `ResultMetadata`
- `ExcludedCounts`
- `SummaryMeta`
- `OverallSummary`
- `ProblemSolverSummary`
- `SummaryReport`
- `result_entries(...)`
- `machine_result_entries(...)`
- `summarize(...)`

## 主要資料結構與資料契約

- `ResultEntry` 是單筆 run 的正式輸出資料模型，整合 task、solve result、validation report 的重要欄位。
- `excluded_reason` 是統計層判斷 run 是否應排除於 objective 統計之外的正式旗標，可能值包括：
  - `infeasible`
  - `objective_mismatch`
  - `runtime_error`
- `SummaryMeta` 保存單一 solver variant 的識別資訊與實驗附加 metadata。
- `SummaryReport` 分成：
  - `overall`
  - `by_problem_solver`

## 資料流與控制流

1. `result_entries(...)` 或 `machine_result_entries(...)` 先把執行結果展平成 `ResultEntry`。
2. `_build_entry(...)` 決定 `excluded_reason`，並把 solve/validation metadata 一起保存。
3. `summarize(...)` 驗證 entries 只屬於單一 solver variant。
4. 先算 overall 指標：run 數、valid run 數、可行率、平均 runtime、平均 evaluation count、平均 objective、std、best/worst、PDev。
5. 再依 `(problem_type, dataset, problem_id)` 分桶，產生 `ProblemSolverSummary`。
6. helper 函式處理 scalar/multi-objective 差異、best/worst 選擇方向、PDev 計算與排除統計。

## 失敗路徑與例外條件

- `summarize(...)` 若收到混合多個 solver variant 的 entries，`_validate_single_variant(...)` 會丟 `ValueError`。
- objective 非 scalar 或 direction 不是單值時，best/worst/avg/std/PDev 某些欄位會退化成 `None`，這是資料契約上的明確保守行為。
- `SummaryMeta` 建立時若欄位不合法，也會 fail-fast。

## 副作用與資源生命週期

- 無檔案 I/O 或 shared memory 副作用。
- 核心副作用是統計排除規則：`objective_mismatch`、`infeasible`、`runtime_error` 會影響有效樣本數與摘要值。

## 與其他模組的關係

- 上游：`machine.core` 產出 `MachineResult` / `SimulatorRunRow`。
- 下游：`tools.show` 直接用 `summarize(...)` 的結果寫 CSV/JSON。
- 間接支援 `experiment.evaluation`，因為 `VariantSummary.summary` 是由這裡產生。

## 核心函式與 helper 說明

### `result_entries(...)` / `machine_result_entries(...)`

- `result_entries(...)`：
  - 目的：把整個 `SimulatorResult` 展平成單一 `ResultEntry` 清單
  - 角色：供 summary 檢查、測試或外部分析直接消費
- `machine_result_entries(...)`：
  - 目的：把單一 variant 的 `MachineResult` 轉成 `ResultEntry`
  - 主要被呼叫者：`_build_entry(...)`
- 重要界線：這一層不重新做 validation；它只吃 `Machine` 已經算好的 `ValidationReport`。

### `summarize(...)`

- 目的：把單一 variant 的 `ResultEntry` 清單收斂成 `SummaryReport`。
- 控制流：
  1. `_validate_single_variant(...)`
  2. 篩出 `objective` 統計有效樣本
  3. 建 overall summary
  4. 依 `(problem_type, dataset, problem_id)` 分桶
  5. 建 `ProblemSolverSummary`
- 重要保守規則：
  - mixed variant 直接拒絕
  - 非 scalar objective 或方向不單一時，best/worst/std/pdev 退回 `None`
- 修改風險：這裡定義了 `cli.run`、`cli.exp`、`replay` 的正式 summary 語意，任何統計口徑變動都會反映到 evaluator 與輸出檔。

### `_validate_single_variant(...)`

- 目的：保證 `SummaryReport` 真的是「一個 solver variant」的摘要。
- 為什麼重要：`SummaryMeta` 只容納一組 `(solver_id, param_set_index)`；如果把混合 entries 放進來，summary 會表面可算、實際語意錯誤。

### `_build_entry(...)`

- 目的：把 `SolveResult + ValidationReport + task context` 轉成標準輸出列。
- 關鍵責任：
  - 決定 `excluded_reason`
  - 用 `metadata.solve` / `metadata.validation` 保存原始附加資訊
  - 優先從 `solve_result.metadata["linprog_runtime"]` 取值，再回退到欄位 `linprog_runtime`
- 架構角色：這是執行層資料進入輸出層前的最後一層 schema 收斂。

### `_best_objective(...)` / `_worst_objective(...)` / `_avg_objective(...)` / `_objective_std(...)`

- 這一組 helper 共同定義 scalar objective 的統計口徑。
- 關鍵規則：
  - 只處理 scalar objective
  - `direction == "max"` 與 `direction == "min"` 的 best/worst 選擇不同
  - std 使用樣本標準差分母 `n - 1`

### `_percent_deviation(...)`

- 目的：根據 `best_known` 與 `direction` 算 PDev。
- 公式：
  - `max` 問題：`(best_known - avg) / best_known * 100`
  - `min` 問題：`(avg - best_known) / best_known * 100`
- 保守條件：任何非 scalar、缺 best known、direction 不明或 best known 為 `0` 都回傳 `None`。

### `_single_value(...)` / `_is_valid_for_objective_stats(...)` / `_has_scalar_objectives(...)` / `_excluded_counts(...)`

- `_single_value(...)`：從集合中抽取唯一值，否則回 `None`；用來檢查 direction / best_known 是否一致。
- `_is_valid_for_objective_stats(...)`：目前有效樣本定義是 `feasible and objective_valid`。
- `_has_scalar_objectives(...)`：best/worst/avg/std 的共同 gating 條件。
- `_excluded_counts(...)`：把排除原因壓成固定三類計數，供 overall 與 per-problem summary 共用。

## 對應函式索引與閱讀順序

1. `ResultEntry`
2. `ResultMetadata`
3. `ExcludedCounts`
4. `SummaryMeta`
5. `OverallSummary`
6. `ProblemSolverSummary`
7. `SummaryReport`
8. `result_entries`
9. `machine_result_entries`
10. `summarize`
11. `_validate_single_variant`
12. `_build_entry`
13. `_best_objective`
14. `_worst_objective`
15. `_avg_objective`
16. `_objective_std`
17. `_percent_deviation`
18. `_single_value`
19. `_is_valid_for_objective_stats`
20. `_has_scalar_objectives`
21. `_excluded_counts`
