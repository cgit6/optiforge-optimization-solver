# `valid/bsma_numba_gk_benchmark.py`

## 模組責任

`valid/bsma_numba_gk_benchmark.py` 用來比對 `bsma` 與 `bsma_numba` 在 GK 前兩題上的結果一致性與總耗時，角色偏向效能/等價 smoke benchmark，而不是嚴格 trace 等價工具。

## 公開入口/主要類型

- 主要入口：`main()`
- 主要 helper：`_repo_root()`、`_load_problem(...)`、`_max_iter()`、`_bench_pair(...)`

## 主要資料結構與資料契約

- benchmark 固定比 `mk_gk01`、`mk_gk02`，repeat 語意由 seed 偏移表示。
- 環境需安裝 `numba`，否則腳本直接退出。
- `_bench_pair(...)` 會回傳 old/new objective、solution 一致性、runtime 與 speedup 指標。

## 資料流與控制流

1. `_max_iter()` 從環境變數 `MKP_BENCH_MAX_ITER` 取最大迭代數。
2. `_load_problem(...)` 透過 `ProblemRepository` 載入 GK 題目。
3. `_bench_pair(...)` 以相同 seed 分別執行 `BSMASolver` 與 `BSMANumbaSolver`。
4. `main()` 對 repeat=1、20 的語意做多 seed 迴圈，統計每題總耗時與整體 speedup。

## 失敗路徑與例外條件

- 未安裝 `numba` 直接 `SystemExit`。
- 題目 YAML 缺失或 solver 執行失敗會中止 benchmark。
- objective/solution 不一致不一定丟例外，但會在輸出中標示 `MISMATCH`。

## 副作用與資源生命週期

- 不寫正式報告檔，主要透過 stdout 輸出 benchmark 結果與 CLI 範例。
- 會讀取標準 repository 與 solver 模組。

## 與其他模組的關係

- 依賴 `engine.repository`、`problem` registry、`solver.BSMA` 與 `solver.BSMA_numba_v2`。
- 與 `tests/test_bsma_solver.py` 不同，這支腳本更關注實際題目上的 runtime/結果對照。

## 對應函式索引與閱讀順序

1. `_repo_root`
2. `_load_problem`
3. `_max_iter`
4. `_bench_pair`
5. `main`

## 核心函式與 helper 說明

### `_repo_root` / `_load_problem` / `_max_iter`

這三個 helper 決定 benchmark 的輸入來源與預算換算方式。`_load_problem` 走正式 repository 載入題目，`_max_iter` 則把 evaluation budget 轉成 BSMA/Numba 對齊的 outer-loop 次數。

### `_bench_pair`

這是 benchmark 的核心函式。它在同一題目、同一 seed、同一 budget 下對比 Python 與 Numba 版本的 objective 與 runtime，讓使用者快速判斷優化是否有性能收益且未明顯偏離結果。

### `main`

CLI 入口負責讀取 dataset/problem 範圍並執行多題 benchmark。它本身不做演算法比較邏輯，但決定整份 benchmark 報表如何被產出。
