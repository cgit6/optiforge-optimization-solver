# `tests/test_solver_registry.py`

## 模組責任

`test_solver_registry.py` 驗證 solver registry 的基本行為與 stub solver 契約。

## 公開入口/主要類型

- pytest 自動發現測試
- 主要 helper：`_build_problem`
- 主要測試群：registry register/create、unregistered error、stub solver result fields、max_iterations

## 主要資料結構與資料契約

registry 必須能註冊/建立 solver、拒絕未註冊 id；stub solver 回傳結果必須包含 solve path 所需欄位，且遵守 `max_iterations` stop condition。

## 資料流與控制流

以最小 toy problem 測 registry register/create/unregistered error，再驗證 stub solver 輸出。

## 失敗路徑與例外條件

registry 找不到 solver、或 stub solver 缺必要欄位，會讓大量上層整合測試失去基準。

## 副作用與資源生命週期

純計算測試，無 I/O。

## 與其他模組的關係

目標模組是 `mkp.solver.registry` 與 `mkp.problem`。

## 對應函式索引與閱讀順序

1. `_build_problem`
2. `test_registry_can_register_and_create_solver`
3. `test_registry_rejects_unregistered_solver`
4. `test_stub_solver_returns_run_result_required_fields`
5. `test_stub_solver_honors_max_iterations_stop_condition`

## 核心函式與 helper 說明

### `_build_problem`

這個 helper 建立最小 `ProblemModel`，讓 solver registry 測試可以直接檢查 stub solver 的回傳契約，而不依賴 repository 或 YAML。

### registry 基本行為測試群

`test_registry_can_register_and_create_solver`、`test_registry_rejects_unregistered_solver` 描述 `SolverRegistry` 的最低行為：已註冊 solver 可建立，未知 solver 必須明確報錯。

### `test_stub_solver_returns_run_result_required_fields` / `test_stub_solver_honors_max_iterations_stop_condition`

這兩個案例把 `StubMaxIterationsSolver` 當作 loader / experiment 測試共用的最小 solver 契約。它保護的不是演算法品質，而是「永遠能產生合法 `SolveResult` 且遵守 stop condition」。
