# `solver/BSCASMA_test_numba.py`

## 模組責任

`solver/BSCASMA_test_numba.py` 是混合 SMA/SCA 測試策略的 Numba 版。它故意與 RL 版維持檔案獨立，讓 test-policy 與 RL 路徑可以分開演進。

## 公開入口/主要類型

- `_sort_bscasma_desc_deterministic_inplace(...)`
- `_update_sma_weight_inplace(...)`
- `_repair_bscasma_row_inplace(...)`
- `_policy_action(...)`
- `_sma_global_row(...)`
- `_sma_local_row(...)`
- `_sca_sin_row(...)`
- `_sca_cos_row(...)`
- `_bscasma_test_main_loop_numba(...)`
- `BRLSMASCATestNumbaCore`
- `BRLSMASCATestNumbaSolver`

## 主要資料結構與資料契約

- 每個個體有固定 `individual_id`，排序後仍透過 `individual_ids` 維持與個體最佳狀態的對應。
- `best_method` 保存各個體目前偏好的動作。
- `exe_time` 統計四種動作被執行的次數。
- `prob_arr` 仍是四元素的初始 policy 分布。

## 資料流與控制流

1. adapter 解析 `pop_size`、`a`、`prob_arr`、`ctf_id`。
2. core 初始化 `cp_list`、初始族群、`best_method`、`individual_ids`。
3. `_bscasma_test_main_loop_numba(...)` 每代：
   - 更新 SMA 權重
   - 依 `best_method` 與少量隨機擾動選動作
   - 執行四種 row update 之一
   - repair
   - 更新 individual best / global best
   - 依 fitness + 原列索引做決定性排序
4. adapter 回傳 `SolveResult`，metadata 標示 `rl=False`。

## 失敗路徑與例外條件

- `prob_arr` 格式不正確、總和不為 1、`a <= 0`、`pop_size <= 0` 都會失敗。
- 需要 `numba` 與 MKP problem tensor 契約。

## 副作用與資源生命週期

- 使用 `_cp_list_cache` 加速重複問題。
- 會把 `best_method`、`exe_time` 等 instrumentation 狀態留在 core 內，供除錯或後續觀察。

## 與其他模組的關係

- 上游：`engine.builders`、`solver.registry`。
- 參考基準：`BSCASMA.py`。
- 與 `BSCASMA_rl_numba.py` 共享高層結構，但 helper 是複製而非共用。

## 對應函式索引與閱讀順序

1. `_cp_list_cache_key`
2. `_sort_bscasma_desc_deterministic_inplace`
3. `_update_sma_weight_inplace`
4. `_ctf_flip_probability_fast`
5. `_repair_bscasma_row_inplace`
6. `_policy_action`
7. `_sma_global_row`
8. `_sma_local_row`
9. `_sca_sin_row`
10. `_sca_cos_row`
11. `_bscasma_test_main_loop_numba`
12. `BRLSMASCATestNumbaCore`
13. `BRLSMASCATestNumbaCore.run`
14. `BRLSMASCATestNumbaSolver.solve`
