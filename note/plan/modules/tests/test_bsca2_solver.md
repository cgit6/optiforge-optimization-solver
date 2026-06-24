# `tests/test_bsca2_solver.py`

## 模組責任

`test_bsca2_solver.py` 驗證 `BSCA` 與 `BSCA_numba` solver family 的基本契約，包括 registry 建立、求解結果有效性、同 seed 可重現、參數合法性與 repair 路徑。

## 公開入口/主要類型

- pytest 自動發現測試
- 主要 helper：`_build_problem`、`_build_config`、`_build_numba_config`
- 主要測試群：registry 建立、solve、reproducibility、stop condition、param validation、numba repair

## 主要資料結構與資料契約

合成的 MKP toy problem 用來覆蓋 `pop_size`、`max_iterations`、`a` 等關鍵參數；solver 回傳的 `SolveResult` 必須維持 binary solution、合法 objective 與 evaluation count 契約。

## 資料流與控制流

helpers 建 problem 與 Python/Numba config，測試依序走 registry create、solve、reproducibility、stop condition、param validation 與 numba repair regression。

## 失敗路徑與例外條件

非法參數必須在建 solver 或 solve 前被拒絕；不同 seed 可以產生不同解，但相同 seed 不可漂移。

## 副作用與資源生命週期

純計算型測試，沒有檔案 I/O，也不依賴 multiprocessing。

## 與其他模組的關係

目標模組是 `mkp.solver.BSCA`、`mkp.solver.BSCA_numba`、`mkp.solver.registry` 與 `mkp.problem`。

## 對應函式索引與閱讀順序

1. `_build_problem`
2. `_build_config`
3. `_build_numba_config`
4. `test_bsca2_solver_can_be_created_by_registry`
5. `test_bsca2_solver_returns_valid_solve_result`
6. `test_bsca2_reproducibility_same_seed_same_result`
7. `test_bsca2_reproducibility_different_seed_can_differ`
8. `test_bsca2_stop_condition_max_iterations_reached_or_best_known`
9. `test_bsca2_params_pop_size_from_config_affects_evaluation_count`
10. `test_bsca2_rejects_invalid_params`
11. `test_bsca_numba_reproducibility_same_seed_same_result`
12. `test_bsca_numba_repair_computes_expected_solution_and_fitness`

## 核心函式與 helper 說明

### `_build_problem` / `_build_config` / `_build_numba_config`

這組 helper 提供 `BSCA` / `BSCA_numba` regression 的最小可比對輸入。`_build_problem` 用小型 MKP 題目把 solver 行為壓到可預期範圍，`_build_numba_config` 則專門支援 cache 與 repair 路徑測試。

### registry、基本求解與 reproducibility 測試群

`test_bsca2_solver_can_be_created_by_registry`、`test_bsca2_solver_returns_valid_solve_result`、`test_bsca2_reproducibility_same_seed_same_result`、`test_bsca2_reproducibility_different_seed_can_differ` 描述 BSCA 作為正式 solver 的最低契約。

### stop condition / pop size / invalid params 測試群

`test_bsca2_stop_condition_max_iterations_reached_or_best_known`、`test_bsca2_params_pop_size_from_config_affects_evaluation_count`、`test_bsca2_rejects_invalid_params` 保護停止條件、evaluation count 與參數驗證。

### `test_bsca_numba_reproducibility_same_seed_same_result` / `test_bsca_numba_repair_computes_expected_solution_and_fitness`

這兩個案例是 Numba 分支的關鍵回歸。前者同時檢查 `cp_list` cache hit/miss 語意，後者直接鎖定 `_repair_bsca_row_inplace` 的修復結果與 fitness 計算。
