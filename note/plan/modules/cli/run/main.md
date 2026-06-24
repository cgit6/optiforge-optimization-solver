# `cli/run/main.py`

## 模組責任

`cli/run/main.py` 是單次 solver 執行 CLI 的薄入口。它把命令列參數交給 `cli/run/support.py`，自己只保留 wiring、可測試注入點與預設 seed strategy。

## 公開入口/主要類型

- `main(...)`

## 主要資料結構與資料契約

- `main(...)` 可注入：
  - `argv`
  - `problem_root`
  - `solver_root`
  - `output_root`
- 預設 seed strategy 固定是 `DerivedPerProblemSeedStrategy()`。
- 回傳值直接透傳 `executeSimulator(...)` 的結果，實際型別與輸出副作用由 support 模組定義。

## 資料流與控制流

1. 呼叫 `parser()` 取得完整 CLI schema。
2. `parse_args(...)` 後交給 `createExperimentSpec(...)` 轉成執行規格。
3. `buildSimulationBundle(...)` 載入 problem repository、solver configs、shared memory bank 與 `Simulator`。
4. 最後交給 `executeSimulator(...)` 執行、輸出結果並回收資源。

## 失敗路徑與例外條件

- CLI 參數不合法時，`argparse` 直接終止。
- spec 建立、bundle 組裝、capability 檢查、problem 載入、solver config 載入任一失敗都會由 support 層往上拋出。
- 本模組本身沒有額外錯誤復原；它刻意維持薄入口，避免複製 support 層邏輯。

## 副作用與資源生命週期

- 本模組不直接管理 shared memory、output 或 worker process。
- 所有 runtime 資源生命週期都委派給 `buildSimulationBundle(...)` / `executeSimulator(...)`。
- 主要價值是讓測試可替換 roots 與 `argv`。

## 與其他模組的關係

- 上游：[`cli/run/__main__.py`](__main__.md)、外部 `python -m ...cli.run`、測試。
- 下游：[`cli/run/support.py`](support.md)、`rng.DerivedPerProblemSeedStrategy`。
- 若要理解真正執行鏈路，應直接接著讀 `support.md`。

## 對應函式索引與閱讀順序

1. `main`
2. [`cli/run/support.py`](support.md)
