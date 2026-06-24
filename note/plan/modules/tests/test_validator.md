# `tests/test_validator.py`

## 模組責任

`test_validator.py` 直接覆蓋 `problem.validation` 的判定邏輯，確保 feasible/objective mismatch/best-known gap 等欄位計算正確。

## 公開入口/主要類型

- pytest 自動發現測試
- 主要 helper：`_build_problem`、`_build_run_result`
- 主要測試群：feasible/infeasible、objective mismatch、best-known gap、float tolerance、vector objective、scalar min

## 主要資料結構與資料契約

validation 必須同時處理 scalar max、scalar min 與 vector objective；`objective_values_equal(...)` 需尊重浮點容忍度。

## 資料流與控制流

helpers 建 toy problem 與 run result，再檢查可行/不可行、objective mismatch、best-known reached/gap 與向量 objective 比對。

## 失敗路徑與例外條件

這裡若錯，`tools.stat` 的 excluded counts 與 experiment evaluator 依賴的 summary 都會一起錯。

## 副作用與資源生命週期

純資料驗證測試，無 I/O。

## 與其他模組的關係

目標模組是 `mkp.problem.validation`、`mkp.problem` 與 `mkp.engine.models`。

## 對應函式索引與閱讀順序

1. `_build_problem`
2. `_build_run_result`
3. `test_problem_validate_feasible_solution_passes`
4. `test_problem_validate_detects_infeasible_solution_and_violated_dims`
5. `test_problem_validate_detects_objective_mismatch`
6. `test_problem_validate_best_known_status_and_gap`
7. `test_objective_values_equal_uses_float_tolerance`
8. `test_vector_objective_equality_and_best_known_gap`
9. `test_scalar_min_best_known_status_and_gap`

## 核心函式與 helper 說明

### `_build_problem` / `_build_run_result`

這兩個 helper 建出最小 problem 與 solve result，方便直接測 `problem.validate(...)` 與 objective 比對邏輯。它們刻意不經過 solver，避免測試焦點被演算法行為污染。

### feasibility 與 violated dimensions 測試群

`test_problem_validate_feasible_solution_passes`、`test_problem_validate_detects_infeasible_solution_and_violated_dims` 固定 validation report 的可行性欄位與 violated dimensions 回傳格式。

### objective mismatch 與浮點容忍測試群

`test_problem_validate_detects_objective_mismatch`、`test_objective_values_equal_uses_float_tolerance`、`test_vector_objective_equality_and_best_known_gap` 描述 validator 如何比較 scalar / vector objective，以及何時接受小誤差。

### best-known 狀態與 gap 測試群

`test_problem_validate_best_known_status_and_gap`、`test_scalar_min_best_known_status_and_gap` 保護 best-known 比較邏輯，特別是 max/min 方向不同時 gap 計算不可混淆。
