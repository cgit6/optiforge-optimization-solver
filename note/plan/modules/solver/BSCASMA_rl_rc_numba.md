# `solver/BSCASMA_rl_rc_numba.py`

## 模組責任

`solver/BSCASMA_rl_rc_numba.py` 是目前最複雜的 solver 模組。它在 RL 混合 SMA/SCA 的基礎上，再整合 LP reduced-cost item evaluation、named score family、guided binary、dynamic repair、local search、archive/path relinking 與 restart。

## 公開入口/主要類型

- item evaluation / score payload helper
- guided binary helper
- repair family helper
- local search helper
- archive / path relinking helper
- RL state / action helper
- `_bscasma_rl_main_loop_numba(...)`
- `BRLSMASCARLRCNumbaCore`
- `BRLSMASCARLRCNumbaSolver`

## 主要資料結構與資料契約

- item evaluation 相關欄位：
  - `requested_item_eval_method`
  - `item_eval_method`
  - `item_eval_payload`
  - `lp_fractional_count`
  - `eff_group_count`
  - `item_eval_fallback`
- repair / guidance / intensification 相關欄位：
  - `repair_passes`
  - `repair_swap_limit`
  - `repair_drop_mode`
  - `repair_drop_score_mode`
  - `guided_binary_enabled`
  - `guided_lambda_*`
  - `local_search_enabled`
  - `archive_pr_enabled`
  - `restart_enabled`
- RL 狀態仍沿用 `9-state` 密度/距離設計，`q_table` 與 `action_counts` 仍存在。

## 資料流與控制流

1. adapter 從 solver YAML 讀入大量參數，先做型別與範圍驗證。
2. `pseudo_utility()` 會依 `item_eval_method` 建立或重用 payload：
   - `lp_rc_ordered / lp_rc_groups`
   - `core_score_cp`
   - `score_{cnd|dual|rc|hyb|lag}_{rank|weight}`
   - `freq_cp / elite_freq_cp / elite_freq_gated / freq_gated / freq_gated_v2`
   - `sbl_lite_cp`
3. `initial_pop()` 可混合 deterministic / LP rounding / RCL / random greedy 初始化。
4. `_bscasma_rl_main_loop_numba(...)` 主循環依序做：
   - RL 動作選擇
   - guided 或非 guided row update
   - `repair_v2` 或 dynamic-weight repair
   - 可選 local search
   - density 與 Q-table 更新
   - 可選 archive/path relinking
   - stagnation restart
5. adapter 最終把大量診斷資訊寫進 `SolveResult.metadata`。

## 失敗路徑與例外條件

- `item_eval_method` 不支援、權重超界、repair/restart/local-search/archive 參數不合法，都會在 adapter 或 core 初始化階段失敗。
- 某些 item evaluation 方法若 LP 失敗，會落入 fallback payload，而不是直接中止；是否可接受需看下游實驗目的。
- 這個檔案高度依賴 `numba`、`linprog`、MKP contiguous tensors 與大量 helper 契約，任一層失配都可能造成錯誤或語意偏移。

## 副作用與資源生命週期

- 使用類別層級 `_cp_list_cache`，快取的不只是 `cp_list`，而是完整 item-eval payload。
- metadata 是本模組的重要副作用輸出，通常包含：
  - 實際使用的 `item_eval_method`
  - requested method
  - fallback 與頻率統計
  - guided/local-search/archive/restart 是否啟用
  - swap、LS、PR、restart 計數
  - `q_table_nonzero`、`action_counts`
- 因參數與狀態很多，任何小改動都可能改變搜索路徑與可重現性。

## 與其他模組的關係

- 上游：`engine.builders`、`solver.registry`、實驗配置 YAML。
- 下游：`BSMA_rc_numba.py`、`BSCA_rc_numba.py` 直接重用這裡的 RC/repair helper。
- 參考基準：`BSCASMA_rl_numba.py` 提供較純的 RL 架構；本檔是其增強版。

## 核心函式與 helper 說明

### `_build_lp_rc_item_eval_payload(...)` / `_build_core_score_cp_payload(...)` / `_build_frequency_cp_payload(...)` / `_build_freq_gated_v2_payload(...)` / `_build_sbl_lite_cp_payload(...)`

- 目的：建立不同 item-evaluation / score family 的 payload 與 `cp_list` 來源。
- 在演算法中的角色：這些 helper 決定 solver 初始化、repair、guided binary、local search 看到的物品排序與分數訊號。
- 維護意義：這一層不是邊角輔助，而是 RC 版搜索偏好的核心來源。

### `_parse_named_score_item_eval_method(...)` / `_is_supported_item_eval_method(...)`

- 目的：把字串型 `item_eval_method` 正規化成受支援的 score family。
- 角色：這是 solver YAML 與 payload builder 之間的 schema gate。

### guided / repair / local search / archive helper 家族

- 代表函式：`_guided_probability(...)`、`_repair_bscasma_row_v2_inplace(...)`、`_local_search_bscasma_row_inplace(...)`、`_archive_add_row(...)`、`_path_relink_bscasma_inplace(...)`。
- 角色：這一整族 helper 決定 intensification 與 diversification 如何進入 RL 主循環。
- 修改風險：這些 helper 多數直接在 hot-loop 內被呼叫，小改動就可能改變可重現性與路徑品質。

### `BRLSMASCARLRCNumbaCore.pseudo_utility()`

- 目的：建立或命中完整 item-eval payload cache，而不只是單純的 `cp_list` cache。
- 副作用：會回填 `item_eval_method`、`guided_mode`、`freq_*`、`fallback` 等診斷欄位。

### `BRLSMASCARLRCNumbaCore.initial_pop()`

- 目的：依設定混合 deterministic greedy、LP rounding、RCL greedy、random greedy 初始化策略。
- 角色：這是 RC 版比純 RL 版更早導入 domain bias 的第一個入口。

### `BRLSMASCARLRCNumbaCore.run()`

- 目的：準備所有 RL、guided、repair、LS、archive、restart 所需工作陣列，然後呼叫 `_bscasma_rl_main_loop_numba(...)`。
- 副作用：會累積 repair / restart / local-search / path-relinking 統計，並在 run 後回填 core state。

### `BRLSMASCARLRCNumbaSolver.solve(...)`

- 角色：這是整個 solver family 最厚的 adapter，負責解析大量 YAML 參數、布林 coercion、score family 選擇與 metadata 輸出。
- 維護建議：新增新策略時，先判斷它屬於 payload、guided、repair、LS、archive 還是 restart 家族，再掛到對應區塊，不要直接把新邏輯塞進 `solve(...)`。

## 對應函式索引與閱讀順序

1. `_item_eval_cache_key`
2. `_coerce_bool_param`
3. `_build_lp_rc_item_eval_payload`
4. `_build_core_score_cp_payload`
5. `_build_frequency_cp_payload`
6. `_build_freq_gated_v2_payload`
7. `_build_sbl_lite_cp_payload`
8. `_parse_named_score_item_eval_method`
9. `_is_supported_item_eval_method`
10. `_guided_probability` 與 guided binary helpers
11. `_repair_bscasma_row_inplace`
12. `_repair_bscasma_row_dynamic_drop_inplace`
13. `_repair_bscasma_row_v2_inplace`
14. `_local_search_bscasma_row_inplace`
15. `_archive_*` / `_path_relink_bscasma_inplace`
16. `_state_bin` / density helpers
17. `_select_q_action_non_global`
18. `_update_q_value`
19. `_sma_global_row`
20. `_sma_local_row`
21. `_sca_sin_row`
22. `_sca_cos_row`
23. `_bscasma_rl_main_loop_numba`
24. `BRLSMASCARLRCNumbaCore`
25. `BRLSMASCARLRCNumbaCore.pseudo_utility`
26. `BRLSMASCARLRCNumbaCore.initial_pop`
27. `BRLSMASCARLRCNumbaCore.run`
28. `BRLSMASCARLRCNumbaSolver.solve`
