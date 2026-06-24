# `tests/test_contracts.py`

## 模組責任

`test_contracts.py` 驗證核心 dataclass / model 契約，包括 `ExperimentSpec`、`ProblemModel`、`RunTask`、`SolveResult` 與抽象 `Problem` 介面要求。

## 公開入口/主要類型

- pytest 自動發現測試
- 主要測試群：`ExperimentSpec`、`ProblemModel`、`RunTask`、`SolveResult` 合法/非法 payload 與抽象介面約束

## 主要資料結構與資料契約

重點是欄位型別、shape、一致性與 readonly array 約束；這些是 engine、simulator、solver 共同依賴的基礎契約。

## 資料流與控制流

測試以最小合法/非法 payload 建立各 dataclass，並檢查成功情境與 validation error。

## 失敗路徑與例外條件

shape 錯誤、未實作 `validate`、非法 objective/solution payload 若被放行，後續整個模擬鏈路都會受污染。

## 副作用與資源生命週期

無 I/O，純資料模型測試。

## 與其他模組的關係

目標模組是 `mkp.engine.models` 與 `mkp.problem`；這是整個 runtime 的最低層防線。

## 對應函式索引與閱讀順序

1. `test_experiment_spec_valid`
2. `test_experiment_spec_invalid`
3. `test_problem_model_valid_and_readonly_arrays`
4. `test_problem_model_invalid_shape`
5. `test_run_task_valid`
6. `test_run_task_invalid`
7. `test_run_result_valid_and_readonly_solution`
8. `test_run_result_accepts_vector_objective`
9. `test_problem_requires_validate_implementation`
10. `test_run_result_invalid`

## 核心函式與 helper 說明

### `test_experiment_spec_valid` / `test_experiment_spec_invalid`

這組測試保護 `ExperimentSpec` 的基本不變量，包括名稱、dataset、problem/solver 清單不得為空、不得重複，以及 repeat / worker / base seed 的合法範圍。

### `test_problem_model_*`

`test_problem_model_valid_and_readonly_arrays` 與 `test_problem_model_invalid_shape` 描述 `ProblemModel` 的形狀契約與不可變陣列語意。這是整個 runtime 資料層的底座。

### `test_run_task_*` / `test_run_result_*`

這兩組測試分別保護 `RunTask` 與 `SolveResult` 的資料契約。除了基本欄位合法性，它們也固定 `best_solution` 只讀、vector objective 可接受，以及 runtime / evaluation_count / stop_reason 的防呆規則。

### `test_problem_requires_validate_implementation`

這個案例鎖定 `Problem` 抽象基類的最低要求：只有 `fitness(...)` / `violates_constraints(...)` 不夠，必須提供完整 validation 實作才能被當成正式 problem 類型使用。
