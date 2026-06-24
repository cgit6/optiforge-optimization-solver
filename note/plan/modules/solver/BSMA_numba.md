# `solver/BSMA_numba.py`

## 模組責任

`solver/BSMA_numba.py` 是 BSMA 的 Numba 加速版。它保留 `BSMA.py` 的前置語意，但把主要迭代熱路徑合併到單一 `@njit` 主迴圈中。

## 公開入口/主要類型

- `_cp_list_cache_key(...)`
- `_expect_mkp_problem_tensors(...)`
- `_ctf_flip_probability_fast(...)`
- `_repair_row_inplace(...)`
- `_sort_pop_desc_deterministic_inplace(...)`
- `_select_two_distinct_indices_excluding(...)`
- `_bsma_main_loop_numba(...)`
- `BSMANumbaCore`
- `BSMANumbaSolver`

## 主要資料結構與資料契約

- `BSMANumbaCore` 要求 `values/weights/capacities` 都是 `np.int64` 且 C-contiguous。
- `_cp_list_cache` 以 problem tensors bytes 為 key，快取 LP 產生的 `cp_list`。
- `ctf_kind` 在 adapter 層會先被轉成 `ctf_id`，避免在 Numba hot-loop 中做字串判斷。

## 資料流與控制流

1. `BSMANumbaSolver.solve(...)` 驗證參數並解析 `ctf_id`。
2. `BSMANumbaCore` 初始化：
   - 驗證張量格式
   - 建立或重用 `cp_list`
   - 生成初始族群
3. `run()` 先用 Python 邏輯完成初始排序，再把陣列轉成 contiguous `float64` 工作陣列。
4. `_bsma_main_loop_numba(...)` 在單一 Numba 函式中完成：
   - 權重更新
   - `z_global` / local 分支
   - CTF 二值化
   - repair
   - 決定性排序
   - global best 更新
5. 回傳 `best_sol/best_fit`，再由 adapter 包裝為 `SolveResult`。

## 失敗路徑與例外條件

- 張量不是 `np.int64` 或非 contiguous 會在 `_expect_mkp_problem_tensors(...)` 失敗。
- `pop_size <= 0`、`z` 不在 `(0,1]`、`max_iter <= 0` 都會 fail-fast。
- 若 `numba` 不可用，模組無法載入。

## 副作用與資源生命週期

- 會使用類別層級 `_cp_list_cache`；這是跨執行共享的快取副作用。
- 仍會呼叫一次 `linprog` 建立 `cp_list`，之後可能命中 cache。
- metadata 會額外回報 `cp_list_cache_hit` 與 `numba=True`。

## 與其他模組的關係

- 上游：`engine.builders`、`solver.registry`。
- 下游：`BSMA_rc_numba.py` 重用這裡的 tensor 檢查、CTF 與排序 helper。
- 參考基準：`BSMA.py`。

## 核心函式與 helper 說明

### `_sort_pop_desc_deterministic_inplace(...)`

- 目的：在 Numba 內重現 `_argsort_pop_fit_desc_deterministic(...)` 的排序語意。
- 角色：它是 Python / Numba 版本對齊的重要 tie-breaking 契約。

### `_bsma_main_loop_numba(...)`

- 目的：把 BSMA 的權重更新、global/local 分支、CTF 二值化、repair、排序與 global best 更新合併到單一 `@njit` 主迴圈。
- 在演算法中的角色：這是 BSMA Numba 版的真正熱點。

### `BSMANumbaCore.pseudo_utility()`

- 目的：建立或命中 `_cp_list_cache`，減少重複 `linprog` 成本。
- 副作用：跨執行共享 cache，因此不同 run 之間會看到不同的 `cp_list_cache_hit` 狀態。

### `BSMANumbaCore.run()`

- 目的：把 Python 端初始化狀態轉成 contiguous 工作陣列後，交給 `_bsma_main_loop_numba(...)`。
- 注意事項：sort 後才進 Numba 主迴圈，這是與純 Python 版對齊 RNG 路徑的重要步驟。

### `BSMANumbaSolver.solve(...)`

- 角色：負責 stop condition、`z`、`ctf_id`、`run_seed` 解析與 metadata 輸出。
- 修改風險：這層 metadata 目前是 tests 與實驗診斷觀察 cache / numba 狀態的重要出口。

## 對應函式索引與閱讀順序

1. `_cp_list_cache_key`
2. `_expect_mkp_problem_tensors`
3. `_ctf_flip_probability_fast`
4. `_repair_row_inplace`
5. `_sort_pop_desc_deterministic_inplace`
6. `_map_position_excluding`
7. `_select_two_distinct_indices_excluding`
8. `_bsma_main_loop_numba`
9. `BSMANumbaCore`
10. `BSMANumbaCore.pseudo_utility`
11. `BSMANumbaCore.initial_pop`
12. `BSMANumbaCore.run`
13. `BSMANumbaSolver.solve`
