# `experiment/evaluation.py`

## 模組責任

`experiment/evaluation.py` 定義 round evaluator 的資料契約。它不負責註冊 evaluator，也不負責 collect 流程本身，但所有 evaluator 函式都以這裡的型別為輸入輸出。

## 公開入口/主要類型

- `VariantSummary`
- `RoundEvalInput`
- `RoundEvalDecision`
- `RoundEvaluator` type alias

## 主要資料結構與資料契約

- `VariantSummary`：單一 solver variant 的彙整快照，內含 `solver_id`、`param_set_index`、`params`、`summary`。
- `RoundEvalInput`：evaluator 執行時拿到的完整上下文，包含：
  - dataset/problem setting
  - 當前 `problem_id`、`repeat_index`
  - evaluator 設定
  - `variant_summaries`
  - `round_result`
  - `collected_result`
  - `candidate_result`
  - `projected_result`
- `RoundEvalDecision`：evaluator 的判決，至少包含 `passed` 與可選 message/metadata。

## 資料流與控制流

1. `experiment.experiment._variant_summaries(...)` 從 `SimulatorResult` 生出 `VariantSummary`。
2. `_evaluate_candidate_round(...)` 為每個 configured evaluator 建立 `RoundEvalInput`。
3. evaluator 函式回傳 `RoundEvalDecision`。
4. collect 流程以 `all(decision.passed)` 決定是否接受這一輪 repeat。

## 失敗路徑與例外條件

- 這個模組本身幾乎不做流程控制，主要失敗點是 dataclass 初始化不合法或外部 evaluator 回傳非預期內容。
- 真正的 evaluator lookup 與 missing evaluator 檢查在 `experiment.experiment`。

## 副作用與資源生命週期

- 無 I/O、shared memory 或 process pool 副作用。
- 角色是固定跨模組資料契約，讓 evaluator 與 collect 主流程解耦。

## 與其他模組的關係

- 上游：`experiment.experiment` 建立 `RoundEvalInput`。
- 下游：`cli/exp/evaluators/*.py` 或其他註冊 evaluator 實作消費這些型別。
- 與 `tools.stat` 間接耦合，因為 `VariantSummary.summary` 來自 summary 模組。

## 核心函式與 helper 說明

### `VariantSummary.__post_init__()`

- 目的：保證 variant identity 可用於 evaluator 比較與 detail 輸出。
- 控制流：檢查 `solver_id` 非空、`param_set_index >= 0`，再把 `params` 複製成普通 `dict`，避免外部持有可變 mapping。
- 角色：所有 `cli.exp` evaluator 其實都把它當作 projected variant 的標準讀取介面。

### `RoundEvalInput.__post_init__()`

- 目的：保證 evaluator 拿到的是一致、可比較的 round 上下文。
- 關鍵契約：`evaluation_name` 必須等於 `evaluation.name`、`variant_summaries` 不能為空、`repeat_index >= 0`。
- 在流程中的角色：這個 dataclass 把 collect 主流程與 evaluator 模組解耦，讓 evaluator 可以專注讀資料而不用重驗 config identity。

### `RoundEvalDecision.__post_init__()`

- 目的：把 `passed` 與 `verdict` 綁成一致狀態，避免 evaluator 回傳自相矛盾結果。
- 控制流：`verdict` 只能是 `PASS` 或 `FAIL`，且 `passed` 必須與之對應；`details` 會被複製成獨立 `dict`。
- 角色：這是 collect loop 接受/拒絕某個 repeat 的最終資料契約。

### `RoundEvaluator`

- 角色：型別別名看似很薄，但它定義了 evaluator 註冊表真正接受的 callable 介面。
- 維護意義：只要 evaluator 仍遵守 `RoundEvalInput -> RoundEvalDecision`，就能在不改 collect 主流程的前提下擴充新判則。

## 對應函式索引與閱讀順序

1. `VariantSummary`
2. `RoundEvalInput`
3. `RoundEvalDecision`
4. `RoundEvaluator`
