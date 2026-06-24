# `solver/BSCASMA_rl_numba.py`

## 模組責任

`solver/BSCASMA_rl_numba.py` 在混合 SMA/SCA 架構上加入 Q-learning。它以「距離 global best + 族群密度」形成狀態，再為非 global 動作學習 `sma_local / sca_sin / sca_cos` 的選擇。

## 公開入口/主要類型

- 排序與 repair helper
- 密度/狀態 helper：`_state_bin(...)`、`_init_density_state(...)`、`_state_for_row(...)`
- RL helper：`_select_q_action_non_global(...)`、`_update_q_value(...)`
- row update helper：`_sma_global_row(...)`、`_sma_local_row(...)`、`_sca_sin_row(...)`、`_sca_cos_row(...)`
- `_bscasma_rl_main_loop_numba(...)`
- `BRLSMASCARLNumbaCore`
- `BRLSMASCARLNumbaSolver`

## 主要資料結構與資料契約

- RL 狀態由 3 x 3 離散格組成，共 `9` 個 state。
- `q_table` shape 為 `[pop_size, 9, 4]`，動作 0..3 對應 global/local/sin/cos。
- `action_counts` 保存每個個體的動作統計。
- `row_hamming`、`ones_count`、`avg_bits` 用來追蹤族群密度。

## 資料流與控制流

1. adapter 解析 `pop_size`、`a`、`z`、`alpha`、`gamma`。
2. core 初始化 `cp_list`、初始族群、`q_table` 與 `action_counts`。
3. `_bscasma_rl_main_loop_numba(...)` 每輪：
   - 更新 SMA 權重與 SCA 退火參數
   - 由 `row -> state` 推導 RL state
   - 以 `z` 決定是否走 global 動作，否則依 Q-table 選動作
   - 執行 row update + repair
   - 更新 density state
   - 用 `reward in {-1, +1}` 更新 Q 值
   - 更新 global best 與決定性排序
4. adapter 把 `q_table_nonzero`、`action_counts` 等資料寫進 metadata。

## 失敗路徑與例外條件

- `pop_size < 3`、`a <= 0`、`z`、`alpha`、`gamma` 超界都會失敗。
- 若 problem tensors 不符合 MKP + contiguous 契約，core 初始化會中止。

## 副作用與資源生命週期

- 使用 `_cp_list_cache`。
- Q-table 與 action counts 會在整次 run 內持續更新；這是 RL 路徑最核心的狀態副作用。
- metadata 會輸出 `q_table_nonzero` 與彙總 action counts，便於比較學習行為。

## 與其他模組的關係

- 上游：`engine.builders`、`solver.registry`。
- 參考基準：`BSCASMA_test_numba.py`。
- 下游：`BSCASMA_rl_rc_numba.py` 延續這個 RL 框架，再加入 RC/guided/local search 等增強。

## 核心函式與 helper 說明

### `_init_density_state(...)` / `_update_density_state_for_row(...)` / `_state_for_row(...)`

- 目的：用「與族群平均 bit 的距離」和「與 global best 的距離」建出 RL state。
- 在演算法中的角色：這一組 helper 決定 RL policy 觀察到的是什麼狀態空間，也是 `9-state` 設計的核心。

### `_select_q_action_non_global(...)` / `_update_q_value(...)`

- 目的：在非 global 分支內選動作並做 Q-learning 更新。
- 注意事項：動作 0 保留給 `z` gate 的 global branch；Q-table 真正學的是 local / sin / cos 三類非 global 行為。

### `_sma_global_row(...)` / `_sma_local_row(...)` / `_sca_sin_row(...)` / `_sca_cos_row(...)`

- 角色：這些是 RL 版的 row-level action primitives。
- 維護意義：任何對動作語意的修改，都會直接改變 RL 學到的 state-action value 分布。

### `_bscasma_rl_main_loop_numba(...)`

- 目的：整合 density 狀態、Q-table、四種 row action、repair 與排序，形成單一 `@njit` 主循環。
- 副作用：持續更新 `q_table`、`action_counts`、`individual_best_*` 與 global best。

### `BRLSMASCARLNumbaCore.run()` / `BRLSMASCARLNumbaSolver.solve(...)`

- 角色：`run()` 負責準備 contiguous RL 工作陣列，`solve(...)` 則負責驗參、`ctf_id` 解析與 metadata 輸出。
- 注意事項：`q_table_nonzero` 與聚合 `action_counts` 是評估學習行為的重要觀測點。

## 對應函式索引與閱讀順序

1. `_cp_list_cache_key`
2. `_sort_bscasma_rl_desc_deterministic_inplace`
3. `_update_sma_weight_inplace`
4. `_repair_bscasma_row_inplace`
5. `_state_bin`
6. `_init_density_state`
7. `_update_density_state_for_row`
8. `_population_density_from_counts`
9. `_state_for_row`
10. `_select_q_action_non_global`
11. `_update_q_value`
12. `_sma_global_row`
13. `_sma_local_row`
14. `_sca_sin_row`
15. `_sca_cos_row`
16. `_bscasma_rl_main_loop_numba`
17. `BRLSMASCARLNumbaCore`
18. `BRLSMASCARLNumbaCore.run`
19. `BRLSMASCARLNumbaSolver.solve`
