# `valid/bsma_population_trace.py`

## 模組責任

`valid/bsma_population_trace.py` 比對舊版 `BSMA` 與現行 `BSMACore` 的 population-level trace。它比 `bsma_equivalence.py` 更偏向「逐代、逐 rank、逐 phase」的族群快照比較，用於定位 refactor 漂移發生在哪一個迭代與哪一筆個體。

## 公開入口/主要類型

- 主要資料型別：`PopulationTraceRow`、`TraceRunResult`、`FirstMismatch`、`ProblemTraceSummary`
- 主要 mixin / trace 類：`PopulationTraceMixin`、`NewTraceBSMA`
- 主要入口：`run_population_trace(...)`、`build_parser(...)`、`main(...)`

## 主要資料結構與資料契約

- `PopulationTraceRow` 用 `(phase, iteration, rank)` 定位單一快照，內容包括 `fit` 與 solution digest。
- `TraceRunResult` 聚合單次 run 的最終 objective、stop reason 與所有 trace rows。
- `ProblemTraceSummary` 則是單題 summary，紀錄 initial unsorted/sorted、population trace、final solution 是否匹配，以及 first mismatch 位置。
- 預設 problem 集含 HP/PB/PET/SENT/WEING/WEISH 各題。

## 資料流與控制流

1. `_load_old_bsma_class(...)` 與 `_make_old_trace_class(...)` 動態包裝 legacy solver，讓它能輸出 population snapshot。
2. `NewTraceBSMA` 對現行 core 做對應 trace 掛鉤。
3. `_build_problem_from_yaml(...)` 載入標準 problem YAML。
4. `_run_old_trace(...)` / `_run_new_trace(...)` 執行並收集 trace rows。
5. `_rows_by_key(...)`、`_rows_match(...)`、`_first_mismatch(...)` 做逐 key 比對。
6. `_write_population_csv(...)`、`_write_summary(...)` 寫出單題與批次結果。
7. `run_population_trace(...)` / `main(...)` 統籌多題執行。

## 失敗路徑與例外條件

- legacy solver、problem YAML 或標準 package 路徑缺失時會 fail-fast。
- old/new row 數量、phase、rank、fit、digest 任一不一致都會在 summary 中呈現 first mismatch。

## 副作用與資源生命週期

- 會讀取 `old/` 與 `configs/problems/`。
- 會寫出 population trace CSV 與 summary 檔。
- 執行期間會暫時建立 trace-aware old/new solver 類別，但不改寫正式 runtime 模組。

## 與其他模組的關係

- 與 `valid/bsma_equivalence.py` 互補：equivalence 強調 digest 對齊，population trace 更強調定位漂移。
- 依賴 `problem.ProblemModel` 與 `solver.BSMA.BSMACore`。

## 對應函式索引與閱讀順序

1. `PopulationTraceRow`
2. `TraceRunResult`
3. `FirstMismatch`
4. `ProblemTraceSummary`
5. `_solution_digest`
6. `_trace_key`
7. `_sort_key`
8. `PopulationTraceMixin`
9. `_load_old_bsma_class`
10. `_make_old_trace_class`
11. `NewTraceBSMA`
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

`PopulationTraceRow`、`TraceRunResult`、`FirstMismatch`、`ProblemTraceSummary` 定義 trace 比對的資料面；`_solution_digest`、`_trace_key`、`_sort_key` 則把 population snapshot 正規化成可排序、可比對的鍵。

### `PopulationTraceMixin` / `_load_old_bsma_class` / `_make_old_trace_class` / `NewTraceBSMA`

這組型別與 helper 讓 old/new solver 都能輸出同格式 trace。它們的責任不是求解，而是把演算法內部狀態暴露成比對工件。

### `_run_old_trace` / `_run_new_trace` / `_rows_by_key` / `_rows_match` / `_first_mismatch`

這是 trace 驗證核心。前兩者實際執行 old/new solver，後三者把結果對齊後找出第一個偏移點，供 refactor 偵錯使用。

### `_write_population_csv` / `_compare_problem` / `_write_summary` / `run_population_trace`

這組函式負責單題比較、輸出 CSV 與 summary，最後由 `build_parser`、`main` 暴露成 CLI。它們是高成本但高定位能力的研究驗證工具。
