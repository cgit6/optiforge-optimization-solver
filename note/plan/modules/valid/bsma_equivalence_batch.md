# `valid/bsma_equivalence_batch.py`

## 模組責任

`valid/bsma_equivalence_batch.py` 把 `bsma_equivalence.py` 的單題嚴格比對擴成 WEISH 題庫批次驗證，輸出全題 summary.json / summary.txt 與每題 trace。

## 公開入口/主要類型

- 主要入口：`run_weish_equivalence_suite(...)`、`main(...)`
- 主要 helper：`default_weish_problem_ids(...)`、`_parse_problem_list(...)`

## 主要資料結構與資料契約

- 預設 problem 集是 `weish01..weish30`。
- 輸出 summary 會紀錄 `trace_match`、`final_solution_match`、old/new objective、stop reason、evaluation upper bound 與單題耗時。
- 若 `ensure_yaml=True`，原始 benchmark 必須能先轉成標準 YAML，再交給 `ProblemRepository` 載入。

## 資料流與控制流

1. 決定 problem list、output directory 與 trace directory。
2. 依 budget 推導 `max_iter` 與理論 evaluation upper bound。
3. 建立 `ProblemRepository`。
4. 逐題視需要呼叫 `transformToYaml(...)`，再 `repository.load(...)`。
5. 對每題呼叫 `verify_equivalence_streaming(...)`，收集結果與耗時。
6. 寫出 `summary.json` 與人類可讀 `summary.txt`。

## 失敗路徑與例外條件

- raw dataset 無法轉 YAML、problem 載入失敗、trace verify 拋例外，都會中止該次批次驗證。
- 只要任一題 `trace_match` 或 `final_solution_match` 失敗，整體 `all_pass` 就會變成 false，CLI exit code 也會反映失敗。

## 副作用與資源生命週期

- 會在 output 目錄下建立 `traces/`、`summary.json`、`summary.txt`。
- 會讀取 `data/`、`configs/problems/`、`old/` 與 solver 模組。

## 與其他模組的關係

- 上游依賴 `valid/bsma_equivalence.py`。
- 也依賴 `cli.convert`、`converter`、`engine.repository` 與 `problem` registry 來確保 dataset 可被標準載入。

## 對應函式索引與閱讀順序

1. `default_weish_problem_ids`
2. `run_weish_equivalence_suite`
3. `_parse_problem_list`
4. `main`

## 核心函式與 helper 說明

### `default_weish_problem_ids` / `_parse_problem_list`

這兩個 helper 決定批次等價驗證要跑哪些題目。前者提供預設題單，後者處理 CLI 傳入的 problem list，讓使用者可以縮小或擴大驗證範圍。

### `run_weish_equivalence_suite`

這是批次版主入口。它逐題呼叫 `valid.bsma_equivalence` 的單題驗證核心，收集通過/失敗與 mismatch 細節，並形成整批 WEISH 驗證的摘要。

### `main`

CLI 入口負責把使用者輸入轉成 suite 參數並啟動整批驗證。它本身很薄，但決定了研究驗證腳本如何被手動操作。
