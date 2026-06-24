# `tests/test_bsma_solver.py`

## 模組責任

`test_bsma_solver.py` 驗證 `BSMA` 與 `BSMA_numba` 的核心契約，確保基線 solver、Numba 版本與 best-known 相關 guard 都維持一致。

## 公開入口/主要類型

- pytest 自動發現測試
- 主要 helper：`_build_problem`、`_build_config`、`_build_numba_config`
- 主要測試群：registry 建立、solve、same-seed、stop condition、`best_known` guard、numba repair regression

## 主要資料結構與資料契約

合成 MKP problem 必須提供合法 `best_known`；solver 回傳需包含可行解、合理 objective、evaluation count 與 stop reason，且 `pop_size` 需能反映到 evaluation count。

## 資料流與控制流

先測 registry 建立與 solve happy path，再測 same-seed determinism、不同 seed 差異、stop condition、`best_known` guard 與 Numba repair regression。

## 失敗路徑與例外條件

非法 problem metadata 或 solver params 必須 fail-fast；`BSMA_numba` repair 不可改變既有 add-failure break 語意。

## 副作用與資源生命週期

純計算測試，沒有檔案副作用。

## 與其他模組的關係

目標模組是 `mkp.solver.BSMA`、`mkp.solver.BSMA_numba`、`mkp.solver.registry` 與 `mkp.problem`。

## 對應函式索引與閱讀順序

1. `_build_problem`
2. `_build_config`
3. `_build_numba_config`
4. `test_bsma_solver_can_be_created_by_registry`
5. `test_bsma_solver_returns_valid_run_result`
6. `test_bsma_reproducibility_same_seed_same_result`
7. `test_bsma_reproducibility_different_seed_can_differ`
8. `test_bsma_stop_condition_max_iterations_reached`
9. `test_bsma_params_pop_size_from_config_affects_evaluation_count`
10. `test_problem_model_rejects_unknown_best_known_before_bsma_runs`
11. `test_bsma_numba_reproducibility_same_seed_same_result`
12. `test_bsma_numba_repair_preserves_add_failure_break_semantics`

## 核心函式與 helper 說明

### `_build_problem` / `_build_config` / `_build_numba_config`

這組 helper 用真實 WEISH 題目載入 `ProblemModel`，再組出標準與 numba 版 solver config。它們讓 BSMA regression 測試可以直接對齊實際題型，而不是只跑玩具資料。

### registry / 基本求解 / reproducibility 測試群

`test_bsma_solver_can_be_created_by_registry`、`test_bsma_solver_returns_valid_run_result`、`test_bsma_reproducibility_same_seed_same_result`、`test_bsma_reproducibility_different_seed_can_differ` 描述 BSMA 作為註冊 solver 的最低契約：可建立、可求解、同 seed deterministic、不同 seed 可以漂移。

### stop condition 與 problem guard 測試群

`test_bsma_stop_condition_max_iterations_reached`、`test_bsma_params_pop_size_from_config_affects_evaluation_count`、`test_problem_model_rejects_unknown_best_known_before_bsma_runs` 保護 solver 停止條件、evaluation count 與 problem 載入前置條件。

### Numba parity 與 repair 語意測試群

`test_bsma_numba_reproducibility_same_seed_same_result` 與 `test_bsma_numba_repair_preserves_add_failure_break_semantics` 是 BSMA Python/Numba 分支的重要回歸檢查，特別是 repair 的 add-pass break 行為不能在優化後漂移。
