# `solver/BSCA.py`

## 模組責任

`solver/BSCA.py` 提供 BSCA 的純 Python 基線版本，角色與 `BSMA.py` 類似：作為數值語意基準與 Numba 版本的對照來源。

## 公開入口/主要類型

- `BSCACore`
- `BSCASolver`

## 主要資料結構與資料契約

- `BSCACore` 保存 problem tensors、族群解、fitness 與 global best。
- `cp_list` 同樣由 LP pseudo utility 建立。
- 主要可調參數是：
  - `pop_size`
  - `a`
  - `max_iter`
  - `ctf_kind`

## 資料流與控制流

1. `BSCASolver.solve(...)` 驗證 `max_iterations` 與 params。
2. 以 `run_seed` 重設 numpy 全域 RNG。
3. `BSCACore` 用 LP 建立 `cp_list`，並初始化族群。
4. `BSCACore.run()` 每代對每個 bit 計算：
   - `r1` 振幅退火
   - `sin/cos` 位移
   - CTF 二值化
   - `repair(...)` 修正不可行解
5. 每次個體更新後可能更新 global best，最後回傳 `SolveResult`。

## 失敗路徑與例外條件

- 只支援 `stop_condition.type=max_iterations`。
- `pop_size <= 0`、`a <= 0`、`max_iter <= 0` 都會失敗。
- `repair(...)` 的第二段刻意不 `break`，這是現有語意的一部分，修改時需小心不要誤改。

## 副作用與資源生命週期

- 會呼叫 `linprog` 並記錄 `linprog_runtime`。
- 會重設 numpy 全域 RNG，以維持與舊版一致的隨機路徑。

## 與其他模組的關係

- 上游：`solver.registry`、`engine.builders`。
- 下游：`BSCA_numba.py` 以此檔為數值行為參考。
- 共用：排序邏輯重用 `BSMA._argsort_pop_fit_desc_deterministic(...)`。

## 核心函式與 helper 說明

### `BSCACore.pseudo_utility()`

- 目的：與 BSMA family 一樣，用 LP 影子價格推導 `cp_list`。
- 角色：它決定了 BSCA 初始化與 repair 的共同物品優先序。

### `BSCACore.repair(trial_sol, trial_fit)`

- 目的：把更新後的 bit vector 修回可行解。
- 關鍵語意：第二段遇到無法加入某物品時不會 `break`，而是繼續掃完整個 `cp_list`；這是現有 BSCA 契約的一部分。

### `BSCACore.run()`

- 目的：執行純 Python BSCA 主循環。
- 控制流：每代對每個 bit 計算 `r1`、`r2`、`r3`、`r4`，走 `sin/cos` 位移，經 CTF 二值化，再做 repair 與 global best 更新。
- 修改風險：`abs(r1 * sin/cos)` 的位置與括號結構已被文件固定；誤改最容易造成與歷史版本脫鉤。

### `BSCASolver.solve(...)`

- 目的：驗證 `max_iterations`、`pop_size`、`a` 與 `ctf_kind`，建立 `BSCACore` 並輸出標準 `SolveResult`。
- 副作用：會重設 numpy 全域 RNG。

## 對應函式索引與閱讀順序

1. `BSCACore.__init__`
2. `BSCACore.pseudo_utility`
3. `BSCACore.initial_pop`
4. `BSCACore.repair`
5. `BSCACore.sort_pop`
6. `BSCACore.run`
7. `BSCASolver.solve`
