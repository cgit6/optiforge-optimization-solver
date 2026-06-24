# `valid/bsma_equivalence.py`

## 模組責任

`valid/bsma_equivalence.py` 提供舊版 `old/BSMA` 與現行 `solver/BSMA.py` 之間的嚴格等價驗證工具。它不是單元測試，而是以 trace digest、final solution/objective 與可選 loop metadata 來比較 old/new 演算法是否真的對齊。

## 公開入口/主要類型

- 主要資料型別：`TraceDigest`、`EquivalenceReport`
- 主要入口：`verify_equivalence_streaming(...)`、`verify_equivalence(...)`、`write_equivalence_report(...)`
- 主要 helper：`max_outer_iterations_for_budget(...)`、`_run_old_with_trace*`、`_run_new_with_trace*`

## 主要資料結構與資料契約

- `TraceDigest` 代表每一步 trace 的最小比較單位：`step`、`phase`、solution digest、`best_fit`。
- `EquivalenceReport` 聚合 dataset/problem/seed/max_iterations、old/new final objective、trace 是否匹配、first mismatch 與新 core loop metadata。
- 輸入 problem 必須能從 `configs/problems/.../*.yaml` 載入成 `ProblemModel`。
- old/new solver 都必須在相同 seed、相同 budget/max iterations 下運行，否則等價比較沒有意義。

## 資料流與控制流

1. `_build_problem_from_yaml(...)` 讀取標準 problem YAML。
2. `max_outer_iterations_for_budget(...)` 把 evaluation budget 轉成與 `pop_size` 對齊的 `max_iter`。
3. `_run_old_with_trace(...)` / `_run_old_with_trace_stream_to_file(...)` 以 monkeypatch 方式掛住舊版 `repair`、`sort_pop`，輸出 trace digest。
4. `_run_new_with_trace(...)` / `_run_new_with_trace_stream_compare_file(...)` 對現行 `BSMACore` 做對應 trace 掛鉤。
5. `verify_equivalence_streaming(...)` 走串流比對，避免把完整 trace 全部留在記憶體。
6. `verify_equivalence(...)` 與 `write_equivalence_report(...)` 產出可供人工檢查的摘要。

## 失敗路徑與例外條件

- problem YAML 缺失、`old/BSMA.py` 不存在、匯入 legacy class 失敗都會直接中止。
- budget 小於 `pop_size` 會被 `max_outer_iterations_for_budget(...)` 拒絕。
- trace mismatch、final solution mismatch、objective mismatch 不一定是例外，但會反映在 `EquivalenceReport` 與輸出的 mismatch 欄位。

## 副作用與資源生命週期

- 會讀取標準 problem YAML 與 `old/` 程式。
- streaming 模式會在 trace directory 下寫出 trace 檔與等價報告。
- 執行時會暫時 monkeypatch `BSMACore` 或 old solver 方法，作用範圍侷限在單次驗證函式內。

## 與其他模組的關係

- 依賴 `mkp.problem.ProblemModel`、`mkp.solver.BSMA.BSMACore` / `BSMASolver`。
- 直接比較 `old/BSMA.py` 與現行 solver，是 solver refactor 的高成本回歸防線。
- `valid/bsma_equivalence_batch.py` 會以此模組作為逐題驗證核心。

## 對應函式索引與閱讀順序

1. `TraceDigest`
2. `EquivalenceReport`
3. `_digest_solution`
4. `max_outer_iterations_for_budget`
5. `_trace_digest_to_line`
6. `_trace_digest_from_line`
7. `_capture_new_loop_meta`
8. `_build_problem_from_yaml`
9. `_run_old_with_trace`
10. `_run_new_with_trace`
11. `_run_old_with_trace_stream_to_file`
12. `_run_new_with_trace_stream_compare_file`
13. `verify_equivalence_streaming`
14. `verify_equivalence`
15. `write_equivalence_report`

## 核心函式與 helper 說明

### `TraceDigest` / `EquivalenceReport`

這兩個 dataclass 定義了「什麼叫做等價」。`TraceDigest` 是單一步驟的最小比較單位，`EquivalenceReport` 則把 final objective、solution、trace 是否一致與 first mismatch 聚合起來，供後續批次工具與人工閱讀。

### `_build_problem_from_yaml` / `max_outer_iterations_for_budget`

這組 helper 把標準 YAML 與 legacy budget 語意轉成 old/new solver 都能共用的輸入。`max_outer_iterations_for_budget(...)` 特別重要，因為若 outer-loop 預算換算錯誤，後面的「不等價」其實只是 budget 沒對齊。

### `_run_old_with_trace*` / `_run_new_with_trace*`

這四個函式是等價驗證的核心。它們會暫時掛住 old/new solver 的關鍵節點，收集 trace digest，並在 streaming 模式下降低記憶體壓力。修改 solver hot-loop 時，這裡通常是最先暴露漂移的位置。

### `verify_equivalence_streaming` / `verify_equivalence` / `write_equivalence_report`

這三個公開入口負責 orchestrate 等價比較、產生 `EquivalenceReport`、並把結果寫成可追溯的報表。batch 腳本與手動驗證都依賴這一層。
