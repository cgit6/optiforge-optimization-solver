# `solver/BSMA_rc_numba.py`

## 模組責任

`solver/BSMA_rc_numba.py` 在 BSMA Numba 主線上加入 LP reduced-cost item evaluation、Repair 2.0、mixed initialization 與 restart 機制。

## 公開入口/主要類型

- `_bsma_rc_global_row(...)`
- `_bsma_rc_main_loop_numba(...)`
- `BSMARCNumbaCore`
- `BSMARCNumbaSolver`

## 主要資料結構與資料契約

- item evaluation 相關狀態：
  - `item_eval_payload`
  - `item_eval_method`
  - `lp_fractional_count`
  - `eff_group_count`
  - `item_eval_fallback`
- repair/restart 相關狀態：
  - `repair_passes`
  - `repair_swap_limit`
  - `restart_enabled`
  - `restart_window`
  - `restart_ratio`
- 這個模組直接重用 `BSCASMA_rl_rc_numba.py` 內的 RC helper，而不是自帶一整套。

## 資料流與控制流

1. adapter 驗證 RC/repair/restart 參數。
2. `BSMARCNumbaCore.pseudo_utility()` 用 `_build_lp_rc_item_eval_payload(...)` 產生基礎排序資料，必要時可打散效率分組。
3. `initial_pop()` 可在隨機貪婪、deterministic greedy、LP rounding、RCL greedy 間混搭。
4. `_bsma_rc_main_loop_numba(...)` 在 BSMA 主循環內加入：
   - RC-aware global row
   - `repair_v2`
   - stagnation restart
5. 結果回傳後，adapter 會把 repair/restart/item-eval 統計放進 metadata。

## 失敗路徑與例外條件

- `pop_size < 3`、repair/restart 參數超界、布林參數格式不合法都會失敗。
- RC payload 若無法從 LP 正常取得，會走 fallback 路徑，但流程不一定中止。

## 副作用與資源生命週期

- 使用 `_item_eval_cache` 快取 RC payload。
- 會在 metadata 中暴露 fallback、cache hit、swap/restart 次數，這些是重要的診斷副作用。
- 與基線版一樣會執行 `linprog`，但其角色已從單純 `cp_list` 擴展成 item evaluation。

## 與其他模組的關係

- 上游：`engine.builders`、`solver.registry`。
- 依賴：大量重用 `BSCASMA_rl_rc_numba.py` 的 helper。
- 參考基準：`BSMA_numba.py`。

## 對應函式索引與閱讀順序

1. `_bsma_rc_global_row`
2. `_bsma_rc_main_loop_numba`
3. `BSMARCNumbaCore`
4. `BSMARCNumbaCore.pseudo_utility`
5. `BSMARCNumbaCore.initial_pop`
6. `BSMARCNumbaCore.run`
7. `BSMARCNumbaSolver.solve`
8. RC helper 來源：`BSCASMA_rl_rc_numba.py`
