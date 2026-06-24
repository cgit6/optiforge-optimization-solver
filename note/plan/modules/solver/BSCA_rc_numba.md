# `solver/BSCA_rc_numba.py`

## 模組責任

`solver/BSCA_rc_numba.py` 在 BSCA Numba 主線上加入 RC item evaluation、Repair 2.0、mixed initialization 與 restart 機制，是 `BSCA` 家族對應的 RC 版。

## 公開入口/主要類型

- `_bsca_rc_main_loop_numba(...)`
- `BSCARCNumbaCore`
- `BSCARCNumbaSolver`

## 主要資料結構與資料契約

- item evaluation payload 與 `BSMARCNumbaCore` 類似，保存 bucket、LP fractional 狀態與 fallback 資訊。
- repair/restart 參數族與 `BSMA_rc_numba.py` 大致一致。
- `a` 仍是 BSCA 專屬主參數。

## 資料流與控制流

1. adapter 讀 solver YAML params，解析 RC、repair、restart 相關參數。
2. core 利用 `_build_lp_rc_item_eval_payload(...)` 與 `_shuffle_efficiency_groups(...)` 建立或重用 `cp_list`。
3. `initial_pop()` 可選 mixed initialization。
4. `_bsca_rc_main_loop_numba(...)` 在 BSCA 主迴圈內套用：
   - RC-aware repair
   - stagnation restart
   - 決定性排序
5. metadata 回報 item evaluation 與 repair/restart 統計。

## 失敗路徑與例外條件

- RC/repair/restart 參數非法時直接失敗。
- LP payload 無法正常建立時可能走 fallback，但如果基礎 schema 或 tensor 契約不符仍會中止。

## 副作用與資源生命週期

- 使用 `_item_eval_cache` 做跨執行快取。
- 會在 metadata 回報 `item_eval_method`、fallback 與 restart/repair 計數。

## 與其他模組的關係

- 上游：`engine.builders`、`solver.registry`。
- 依賴：重用 `BSCASMA_rl_rc_numba.py` 的 RC helper。
- 參考基準：`BSCA_numba.py`。

## 對應函式索引與閱讀順序

1. `_bsca_rc_main_loop_numba`
2. `BSCARCNumbaCore`
3. `BSCARCNumbaCore.pseudo_utility`
4. `BSCARCNumbaCore.initial_pop`
5. `BSCARCNumbaCore.run`
6. `BSCARCNumbaSolver.solve`
7. RC helper 來源：`BSCASMA_rl_rc_numba.py`
