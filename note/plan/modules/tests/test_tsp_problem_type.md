# `tests/test_tsp_problem_type.py`

## 模組責任

`test_tsp_problem_type.py` 驗證 TSP 題型的 repository 載入、`validate` 契約與 solver capability 相容性。

## 公開入口/主要類型

- pytest 自動發現測試
- 主要 helper：`_write_tsp`、`_write_solver`
- 主要測試群：canonical load、permutation/cost validation、MKP solver compatibility reject

## 主要資料結構與資料契約

TSP YAML 載入後必須形成合法 problem model；`validate` 必須檢查 permutation 與 cost；MKP solver 不得被允許跑在 TSP problem 上。

## 資料流與控制流

helpers 先寫 TSP problem/solver YAML，再測 canonical load、validation 與 CLI 相容性檢查。

## 失敗路徑與例外條件

若 TSP validate 或 capability guard 失效，多題型架構就只剩表面支援。

## 副作用與資源生命週期

會在 `tmp_path` 寫出 TSP 與 solver YAML。

## 與其他模組的關係

目標模組是 `mkp.problem`、`mkp.engine.repository`、`mkp.engine.models` 與 `mkp.cli.run`。

## 對應函式索引與閱讀順序

1. `_write_tsp`
2. `_write_solver`
3. `test_tsp_canonical_repository_loads_problem`
4. `test_tsp_problem_validate_checks_permutation_and_cost`
5. `test_compatibility_check_rejects_mkp_solver_for_tsp`

## 核心函式與 helper 說明

### `_write_tsp` / `_write_solver`

這兩個 helper 建立最小 TSP YAML 與 solver capability YAML，讓測試能在隔離環境裡重建 canonical TSP 載入與相容性檢查流程。

### `test_tsp_canonical_repository_loads_problem`

這個案例保護 canonical TSP problem YAML 能被 `ProblemRepository` 正確載入為 `TSPProblem`，並帶出 `problem_type=tsp`、`encoding=permutation`、`direction=min` 的型別契約。

### `test_tsp_problem_validate_checks_permutation_and_cost`

這個測試直接鎖定 `TSPProblem.validate(...)` 的兩個核心面向：路徑是否為合法 permutation，以及 objective 是否和 distance matrix 計算一致。

### `test_compatibility_check_rejects_mkp_solver_for_tsp`

這個案例把 TSP 納入 CLI 相容性檢查主鏈，確保 MKP solver 不會被誤用在 permutation 問題上。
