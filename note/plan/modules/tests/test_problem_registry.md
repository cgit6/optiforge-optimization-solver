# `tests/test_problem_registry.py`

## 模組責任

`test_problem_registry.py` 覆蓋 problem builder/registry 基礎層，確保 MKP/TSP 題型註冊、方向契約與 builder 型別驗證正確。

## 公開入口/主要類型

- pytest 自動發現測試
- 主要測試群：registry 列表、duplicate guard、vector direction、builder 型別、MKP/TSP fitness/constraint 契約

## 主要資料結構與資料契約

registry 必須列出既有題型、拒絕重複 problem type、接受 vector direction 的 problem model，並強制 builder 回傳合法 `ProblemModel`。

## 資料流與控制流

測試先檢查 registry 列表與 duplicate guard，再直接驗證 MKP/TSP problem 的 fitness/constraints 契約。

## 失敗路徑與例外條件

若 registry 允許重複註冊、builder 回錯型別或 problem fitness/constraint 基本運算失真，整個 repository/engine 鏈路都會失效。

## 副作用與資源生命週期

純資料模型測試，無 I/O。

## 與其他模組的關係

目標模組是 `mkp.problem` 與 `mkp.problem.registry`。

## 對應函式索引與閱讀順序

1. `test_problem_builders_registry_lists_mkp_and_tsp`
2. `test_problem_registry_rejects_duplicate_problem_type`
3. `test_problem_registry_accepts_vector_direction`
4. `test_problem_registry_rejects_non_problem_model_type`
5. `test_mkp_problem_fitness_and_constraint_methods`
6. `test_tsp_problem_fitness_and_constraint_methods`

## 核心函式與 helper 說明

### registry 組裝與防呆測試群

`test_problem_builders_registry_lists_mkp_and_tsp`、`test_problem_registry_rejects_duplicate_problem_type`、`test_problem_registry_accepts_vector_direction`、`test_problem_registry_rejects_non_problem_model_type` 描述 `ProblemRegistry` 的註冊契約，包括 problem type 唯一性、方向欄位接受 tuple，以及 `model_type` 必須真的是 `Problem` 子類。

### `test_mkp_problem_fitness_and_constraint_methods` / `test_tsp_problem_fitness_and_constraint_methods`

這兩個案例把 `MKPProblem` 與 `TSPProblem` 當成 concrete model 檢查其 `fitness(...)` 與 `violates_constraints(...)` 是否符合預期。它們是 problem model 最底層的行為回歸。
