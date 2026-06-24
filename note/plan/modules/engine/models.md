# `engine/models.py`

## 模組責任

`engine/models.py` 定義執行鏈路共用的核心資料模型。這些 dataclass 是 CLI、engine、machine、simulator、stat/show 之間的共通語言。

## 公開入口/主要類型

- `ExperimentSpec`
- `RunTask`
- `SolveResult`

## 主要資料結構與資料契約

- `ExperimentSpec`：描述一次批次執行的靜態邊界，包含 dataset、problem ids、solver ids、repeat、worker count、problem type、base seed。
- `RunTask`：描述單一 `(problem_id, repeat_index, solver_id, param_set_index)` 的執行工單。
- `SolveResult`：solver 真正回傳的結果契約，至少要包含 `best_solution`、`best_objective`、`feasible`、`evaluation_count`、`stop_reason`、`runtime`。
- `SolveResult.metadata` 是開放欄位，讓 solver 或後處理層加上附加資訊，例如 `linprog_runtime`。

## 資料流與控制流

1. CLI 或 experiment config 先建立 `ExperimentSpec`。
2. `Machine.expand_tasks(...)` 依 spec 展開成多個 `RunTask`。
3. solver 執行後回傳 `SolveResult`。
4. `problem.validate(...)` 再把 `SolveResult` 轉成 `ValidationReport`，後續由 `tools.stat` 與 `tools.show` 消化。

## 失敗路徑與例外條件

- 三個 dataclass 都在 `__post_init__` 做強驗證。
- 空字串、負數 seed、重複 problem ids、重複 solver ids、非法 worker/repeat 都會在模型建立時 fail-fast。
- `SolveResult.best_solution` 必須是一維陣列；`best_objective` 會被正規化，若型別不對會直接失敗。

## 副作用與資源生命週期

- 幾乎沒有外部副作用；重點是建立不可變資料契約。
- `SolveResult.best_solution` 會被設成 read-only，避免後續統計或輸出階段意外修改 solver 回傳內容。
- `SolveResult.metadata` 與 `MachineResult.params` 類似，都會複製一份，避免呼叫端持有可變參照。

## 與其他模組的關係

- 上游：`cli.run.support`、`experiment.experiment`、`cli.replay.main` 建立 `ExperimentSpec`。
- 中游：`machine.core` 生產 `RunTask` 與 `SolveResult`。
- 下游：`problem.validation`、`tools.stat`、`tools.show` 都依賴這些資料模型。

## 核心函式與 helper 說明

### `ExperimentSpec.__post_init__()`

- 目的：在 runtime 真正開始前，把「批次執行邊界」驗到乾淨。
- 驗證內容：
  - 名稱、dataset、problem_type 不可空
  - `repeat`、`worker_count` 必須大於 0
  - `problem_ids`、`solver_ids` 不可空、不可含空字串、不可重複
  - `base_seed` 若提供，必須可正規化成非負整數
- 修改風險：這是很多 CLI / experiment 錯誤的第一道 gate；一旦放寬這裡，錯誤會延後到 `Machine.expand_tasks(...)` 或更後面才暴露。

### `RunTask.__post_init__()`

- 目的：確保單一工單能被當成 deterministic execution key。
- 重要欄位：
  - `repeat_index`
  - `task_seed`
  - `param_set_index`
  - 以及 `(problem_type, dataset, problem_id, solver_id)` identity
- 架構角色：`MachinePool`、`_task_key(...)`、seed bank replay 都假設這個物件一建出來就是合法工單。

### `SolveResult.__post_init__()`

- 目的：把 solver adapter 的輸出正規化成系統可消化的結果契約。
- 驗證與正規化：
  - `run_seed/evaluation_count/runtime/linprog_runtime` 不可為負
  - `stop_reason` 不可空
  - `best_objective` 交給 `normalize_objective_value(...)`
  - `best_solution` 必須是一維 array，且會被設成 read-only
  - `metadata` 會被複製成一般 dict
- 修改風險：統計與驗證層假設 `best_solution` 不會再被下游修改；若移除 read-only 設定，debug 時很難追資料污染。

## 對應函式索引與閱讀順序

1. `ExperimentSpec`
2. `RunTask`
3. `SolveResult`
