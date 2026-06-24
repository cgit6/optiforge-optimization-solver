# `valid/bscasma_population_trace.py`

## 模組責任

`valid/bscasma_population_trace.py` 比對舊版 `BRLSMASCATest` 與現行 `BRLSMASCATestCore` 的 population trace。它是三個 population trace 腳本中最複雜的一支，因為除了 trace 對齊，還要記錄 old 版本已知的 `S=0` / NaN crash 行為是否與新版本一致。

## 公開入口/主要類型

- 主要資料型別：`PopulationTraceRow`、`TraceRunResult`、`FirstMismatch`、`ProblemTraceSummary`
- 主要 mixin / trace 類：`PopulationTraceMixin`、`NewTraceBSCASMATest`
- 主要入口：`run_population_trace(...)`、`build_parser(...)`、`main(...)`

## 主要資料結構與資料契約

- summary 除了一般 trace 對齊欄位，還記錄 `a`、`z`、`prob_arr`、`old_crashed_iteration`、`new_crashed_iteration`、`crash_match`。
- old/new solver 必須在相同 `pop_size`、`a`、`z`、`prob_arr`、seed 下比較。
- 若 old 版本在特定 iteration crash，新版是否 crash、何時 crash 也是比較契約的一部分。

## 資料流與控制流

1. `_load_old_bscasma_test_class(...)` 載入 legacy `BSCASMA` 類。
2. `_make_old_trace_class(...)` 與 `NewTraceBSCASMATest` 建立可追蹤 old/new solver。
3. `_safe_run_with_trace(...)` 用來捕捉 crash iteration 與例外型別。
4. `_run_old_trace(...)` / `_run_new_trace(...)` 執行單題。
5. `_rows_match(...)`、`_first_mismatch(...)`、`_compare_problem(...)` 統整 trace 與 crash 對齊。
6. `run_population_trace(...)` / `main(...)` 寫出 CSV / summary。

## 失敗路徑與例外條件

- old/new crash 行為若不一致，會被標為 `crash_match = false`。
- phase/rank/fit/digest 不一致、參數解析失敗或 problem YAML 缺失也都會使 summary 失敗。

## 副作用與資源生命週期

- 會讀取 `old/` 與標準 problem YAML。
- 會寫出 population trace CSV 與 summary 檔。
- 會在比較過程中暫時保存 crash metadata，但不改寫正式 solver 實作。

## 與其他模組的關係

- 結構近似 `bsma_population_trace.py` / `bsca_population_trace.py`，但對應 `solver.BSCASMA.BRLSMASCATestCore`。
- 可和 `tests/test_bscasma_solver.py` 搭配：pytest 守局部 helper/metadata，這支腳本守整體族群軌跡與 crash 相容性。

## 對應函式索引與閱讀順序

1. `PopulationTraceRow`
2. `TraceRunResult`
3. `FirstMismatch`
4. `ProblemTraceSummary`
5. `_solution_digest`
6. `_trace_key`
7. `_sort_key`
8. `PopulationTraceMixin`
9. `_load_old_bscasma_test_class`
10. `_make_old_trace_class`
11. `NewTraceBSCASMATest`
12. `_build_problem_from_yaml`
13. `_safe_run_with_trace`
14. `_run_old_trace`
15. `_run_new_trace`
16. `_rows_by_key`
17. `_rows_match`
18. `_first_mismatch`
19. `_write_population_csv`
20. `_compare_problem`
21. `_write_summary`
22. `_parse_problem_list`
23. `_parse_prob_arr`
24. `run_population_trace`
25. `build_parser`
26. `main`

## 核心函式與 helper 說明

### trace row dataclass、key helper 與 `_parse_prob_arr`

`PopulationTraceRow`、`TraceRunResult`、`FirstMismatch`、`ProblemTraceSummary` 定義 BSCASMA trace 的主資料面；`_solution_digest`、`_trace_key`、`_sort_key` 與 `_parse_prob_arr` 則處理 row 正規化與舊版機率陣列輸入。

### `PopulationTraceMixin` / `_load_old_bscasma_test_class` / `_make_old_trace_class` / `NewTraceBSCASMATest`

這組型別與 helper 讓 legacy `BSCASMA_test` 與現行 trace 版本共享輸出格式。因為這個家族比 BSMA/BSCA 多了方法切換與已知 crash 行為，所以 trace 包裝更重。

### `_safe_run_with_trace` / `_run_old_trace` / `_run_new_trace` / `_rows_by_key` / `_rows_match` / `_first_mismatch`

這是 BSCASMA trace 驗證的比對核心。`_safe_run_with_trace` 會把舊版已知 crash 納入結果表示，避免比對流程因 legacy exception 直接中斷。

### `_write_population_csv` / `_compare_problem` / `_write_summary` / `run_population_trace`

這組函式負責單題比較、報表輸出與整體 CLI orchestration，是目前定位 BSCASMA refactor 漂移最有效的研究腳本。
