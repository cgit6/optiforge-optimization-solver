# `valid/bsca_population_trace.py`

## 模組責任

`valid/bsca_population_trace.py` 比對舊版 `BSCA` 與現行 `BSCACore` 的 population trace。它和 `bsma_population_trace.py` 架構相近，但需要額外處理 BSCA 同時使用 `random` 與 `numpy.random` 的雙源 RNG 契約。

## 公開入口/主要類型

- 主要資料型別：`PopulationTraceRow`、`TraceRunResult`、`FirstMismatch`、`ProblemTraceSummary`
- 主要 mixin / trace 類：`PopulationTraceMixin`、`NewTraceBSCA`
- 主要入口：`run_population_trace(...)`、`build_parser(...)`、`main(...)`

## 主要資料結構與資料契約

- trace row 與 summary 結構與 BSMA trace 腳本一致，但 summary 額外記錄 `a` 參數。
- old/new solver 必須在相同 `a`、`pop_size`、seed 下比較；舊版因未直接收 seed，初始化前必須同時對 `random` 與 `numpy` 做 seed。

## 資料流與控制流

1. `_load_old_bsca_class(...)` 動態載入 old BSCA。
2. `_make_old_trace_class(...)` 包裝 legacy class，顯式處理雙源 RNG seed。
3. `NewTraceBSCA` 對現行 core 掛 trace。
4. `_build_problem_from_yaml(...)`、`_run_old_trace(...)`、`_run_new_trace(...)` 建立並執行比對。
5. `_rows_match(...)`、`_first_mismatch(...)` 決定 trace 是否對齊。
6. `run_population_trace(...)` / `main(...)` 產出 CSV 與 summary。

## 失敗路徑與例外條件

- 若雙源 RNG seeding 漏掉，舊版與新版即使演算法一致也會表現成 trace mismatch。
- 任何 phase/rank/fit/digest 不一致都會反映在 summary 的 mismatch 欄位。

## 副作用與資源生命週期

- 會讀取 `old/` 與標準 problem YAML。
- 會寫出 population trace CSV 與 summary 檔。

## 與其他模組的關係

- 架構對應 `valid/bsma_population_trace.py`，但目標 solver 換成 `BSCA` / `BSCACore`。
- 可搭配 `tests/test_bsca2_solver.py` 使用：pytest 先守基本契約，這支腳本再守逐代軌跡。

## 對應函式索引與閱讀順序

1. `PopulationTraceRow`
2. `TraceRunResult`
3. `FirstMismatch`
4. `ProblemTraceSummary`
5. `_solution_digest`
6. `_trace_key`
7. `_sort_key`
8. `PopulationTraceMixin`
9. `_load_old_bsca_class`
10. `_make_old_trace_class`
11. `NewTraceBSCA`
12. `_build_problem_from_yaml`
13. `_run_old_trace`
14. `_run_new_trace`
15. `_rows_by_key`
16. `_rows_match`
17. `_first_mismatch`
18. `_write_population_csv`
19. `_compare_problem`
20. `_write_summary`
21. `_parse_problem_list`
22. `run_population_trace`
23. `build_parser`
24. `main`

## 核心函式與 helper 說明

### trace row dataclass 與 key helper

`PopulationTraceRow`、`TraceRunResult`、`FirstMismatch`、`ProblemTraceSummary` 與 `_solution_digest`、`_trace_key`、`_sort_key` 共同定義 BSCA trace 的可比對表示法。這層把 population、rank 與 phase 正規化，避免 CSV 層再做推測。

### `PopulationTraceMixin` / `_load_old_bsca_class` / `_make_old_trace_class` / `NewTraceBSCA`

這組型別用來對 old/new BSCA 都插入相同的 trace 掛鉤。其目的是把 refactor 差異壓縮成可重放、可對照的 row 集合。

### `_run_old_trace` / `_run_new_trace` / `_rows_by_key` / `_rows_match` / `_first_mismatch`

這些函式是單題 trace 比對的核心管線：執行、索引、比較、定位第一個 mismatch。只要 repair、sort 或 update 規則改動，這一層最容易先顯示漂移。

### `_write_population_csv` / `_compare_problem` / `_write_summary` / `run_population_trace`

這組函式把比對結果落地成 CSV 與 summary，再由 `build_parser`、`main` 提供批次命令列入口。
