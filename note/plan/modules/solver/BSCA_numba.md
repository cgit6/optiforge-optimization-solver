# `solver/BSCA_numba.py`

## 模組責任

`solver/BSCA_numba.py` 是 BSCA 的 Numba 加速版，角色與 `BSMA_numba.py` 類似：保持基線語意，但把 bit 更新與 repair 熱路徑搬進單一 `@njit` 主迴圈。

## 公開入口/主要類型

- `_cp_list_cache_key(...)`
- `_ctf_flip_probability_fast(...)`
- `_repair_bsca_row_inplace(...)`
- `_bsca_main_loop_numba(...)`
- `BSCANumbaCore`
- `BSCANumbaSolver`

## 主要資料結構與資料契約

- problem tensors 仍要求 `np.int64` 且 C-contiguous。
- `_cp_list_cache` 快取 LP 推得的 `cp_list`。
- `a` 是主要退火振幅參數。

## 資料流與控制流

1. adapter 驗證 `pop_size`、`a`、`max_iter`。
2. core 先建立 `cp_list` 與初始族群。
3. `run()` 將狀態轉成 contiguous Numba 工作陣列。
4. `_bsca_main_loop_numba(...)` 在單一函式中完成：
   - `sin/cos` 位移
   - CTF 二值化
   - repair
   - global best 更新
   - 每代末排序
5. adapter 產出 `SolveResult` 與簡單 metadata。

## 失敗路徑與例外條件

- `a <= 0`、`pop_size <= 0`、`max_iter <= 0` 都會失敗。
- 張量格式不合契約時會在 `_expect_mkp_problem_tensors(...)` 中止。

## 副作用與資源生命週期

- 使用 `linprog` 與 `_cp_list_cache`。
- metadata 會標示 `cp_list_cache_hit` 與 `numba=True`。

## 與其他模組的關係

- 上游：`engine.builders`、`solver.registry`。
- 下游：`BSCA_rc_numba.py` 重用 RC 相關擴充模式。
- 參考基準：`BSCA.py`。

## 核心函式與 helper 說明

### `_repair_bsca_row_inplace(...)`

- 目的：在 Numba hot-loop 中完成單列 repair。
- 關鍵語意：與純 Python `BSCACore.repair(...)` 對齊，第二段同樣不因單次加入失敗而提早 `break`。

### `_bsca_main_loop_numba(...)`

- 目的：把 BSCA 的 bit 更新、CTF 二值化、repair、global best 更新與排序集中到單一 `@njit` 主迴圈。
- 在演算法中的角色：這是 BSCA Numba 版真正的 hot-loop 核心。

### `BSCANumbaCore.pseudo_utility()`

- 目的：建立或重用 `_cp_list_cache` 中的 `cp_list`。
- 副作用：命中 cache 時 `linprog_runtime` 會是 `0.0`，並在 metadata 中反映 `cp_list_cache_hit=True`。

### `BSCANumbaCore.run()`

- 目的：準備 contiguous 工作陣列後呼叫 `_bsca_main_loop_numba(...)`。
- 控制流：先做 Python 端初始排序，再進 Numba 主迴圈，最後把 `gbest_sol` 轉回整數 bit 向量。

### `BSCANumbaSolver.solve(...)`

- 角色：adapter 層，只負責驗參、種子、`ctf_id` 解析與 `SolveResult` 包裝。
- 維護建議：任何想保留「Numba 與純 Python 對齊」的變更，都應優先從 core/kernel 層下手，而不是在這層插入新邏輯。

## 對應函式索引與閱讀順序

1. `_cp_list_cache_key`
2. `_ctf_flip_probability_fast`
3. `_repair_bsca_row_inplace`
4. `_bsca_main_loop_numba`
5. `BSCANumbaCore`
6. `BSCANumbaCore.pseudo_utility`
7. `BSCANumbaCore.initial_pop`
8. `BSCANumbaCore.run`
9. `BSCANumbaSolver.solve`
