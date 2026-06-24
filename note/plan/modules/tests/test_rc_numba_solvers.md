# `tests/test_rc_numba_solvers.py`

## 模組責任

`test_rc_numba_solvers.py` 聚焦 `BSMA_rc_numba` 與 `BSCA_rc_numba` 兩個 repair/restart 家族，確保 registry、配置載入與 RC helper 行為穩定。

## 公開入口/主要類型

- pytest 自動發現測試
- 主要 helper：`_build_problem`、`_config`
- 主要測試群：registry create、config param selection、solve、same-seed、cp list、mixed init、restart、invalid repair params

## 主要資料結構與資料契約

solver config loader 必須能載入 param `0` 與最後一組設定；RC solver 回傳要保持 feasibility、metadata 與 same-seed determinism，且 `cp_list`/mixed init/restart 契約不能漂移。

## 資料流與控制流

helpers 建 problem 與 config，先走 registry create，再驗證 config 載入、solve、same-seed、核心 helper 與 invalid param guard。

## 失敗路徑與例外條件

非法 repair/restart 參數未被擋下，或 RC helper 破壞排列完整性/可行性，都會直接影響 solver 主線。

## 副作用與資源生命週期

少量 repository/config load，無正式 output。

## 與其他模組的關係

目標模組是 `mkp.solver.BSMA_rc_numba`、`mkp.solver.BSCA_rc_numba`、`mkp.engine.builders`、`mkp.solver.registry` 與 `mkp.tools.solver_config_loader`。

## 對應函式索引與閱讀順序

1. `_build_problem`
2. `_config`
3. `test_rc_numba_solvers_can_be_created_by_registry`
4. `test_rc_numba_solver_configs_load_param_0_and_last`
5. `test_rc_numba_solvers_return_valid_solve_result_and_metadata`
6. `test_rc_numba_solvers_are_reproducible_with_same_seed`
7. `test_rc_numba_core_cp_list_is_complete_permutation`
8. `test_rc_numba_mixed_init_is_feasible_binary_and_reproducible`
9. `test_rc_numba_restart_triggers_after_stagnation_and_keeps_best_feasible`
10. `test_rc_numba_solvers_reject_invalid_repair_restart_params`

## 核心函式與 helper 說明

### `_build_problem` / `_config`

這兩個 helper 專門為 RC Numba solver regression 建立最小可比對的 problem 與 config。與 `test_bscasma_solver.py` 相比，這裡更聚焦在 solver registry 與共通 RC 功能旗標，而不是單一家族的所有支線。

### registry 與 config 載入測試群

`test_rc_numba_solvers_can_be_created_by_registry`、`test_rc_numba_solver_configs_load_param_0_and_last` 保護 RC solver 的註冊與高低索引 param set 都能被正確建立。

### metadata / reproducibility / cp-list 測試群

`test_rc_numba_solvers_return_valid_solve_result_and_metadata`、`test_rc_numba_solvers_are_reproducible_with_same_seed`、`test_rc_numba_core_cp_list_is_complete_permutation` 描述 RC solver 的輸出 metadata、determinism 與 candidate permutation 契約。

### mixed-init / restart / invalid params 測試群

`test_rc_numba_mixed_init_is_feasible_binary_and_reproducible`、`test_rc_numba_restart_triggers_after_stagnation_and_keeps_best_feasible`、`test_rc_numba_solvers_reject_invalid_repair_restart_params` 聚焦在較高風險的初始化、重啟與參數防呆支線。
