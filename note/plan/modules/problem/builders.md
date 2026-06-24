# `problem/builders.py`

## 模組責任

`problem/builders.py` 定義內建 problem type spec，並提供建立 `ProblemRegistry` 的標準工廠。它決定主流程目前真正啟用哪些題型。

## 公開入口/主要類型

- `problemBuilders()`
- `buildProblemRegistry(...)`

## 主要資料結構與資料契約

- `problemBuilders()` 回傳 `dict[str, ProblemTypeSpec]`。
- key 必須與 `ProblemTypeSpec.problem_type` 完全一致。
- 目前只註冊：
  - `mkp`
  - `tsp`
- `kp.py`、`vrp.py` 雖然存在，但尚未進入 builder map，因此不是有效 runtime problem type。

## 資料流與控制流

1. `problemBuilders()` 收集各題型 spec。
2. `buildProblemRegistry(...)` 建立空 registry。
3. 逐一呼叫 `registry.register(spec)` 完成註冊。
4. 若外部傳入自訂 `builders`，就用外部版本覆寫預設內建集合。

## 失敗路徑與例外條件

- builder dict 的 key 與 `spec.problem_type` 不一致時，`buildProblemRegistry(...)` 直接丟 `ValueError`。
- 若兩個 spec 嘗試註冊同名 problem type，實際衝突處理由 `ProblemRegistry.register(...)` 決定。

## 副作用與資源生命週期

- 無 I/O 副作用。
- 每次呼叫都建立新的 registry，避免跨測試或跨流程共享狀態。

## 與其他模組的關係

- 上游：`engine.repository`、`engine.bank`、`tools/*`、測試與研究腳本使用它建立標準 registry。
- 下游：[`problem/mkp.py`](mkp.md)、[`problem/tsp.py`](tsp.md) 提供 `ProblemTypeSpec`。
- 它是「package 內有哪些題型真正進入主流程」的單一事實來源。

## 核心函式與 helper 說明

### `problemBuilders()`

- 目的：宣告目前 active runtime 真的啟用哪些題型。
- 目前內容：只回傳 `mkp` 與 `tsp` 兩個 `ProblemTypeSpec`。
- 維護意義：這裡比 `problem/` 目錄更重要，因為檔案存在不代表題型已經進入主流程。

### `buildProblemRegistry(builders=None)`

- 目的：用 builder map 建立一份新的 `ProblemRegistry`。
- 控制流：若未注入自訂 builders，就採 `problemBuilders()`；之後逐一檢查 dict key 與 `spec.problem_type` 是否一致，再註冊進 registry。
- 失敗路徑：key/spec 不一致時直接丟 `ValueError`，避免 runtime 題型名稱分裂。

## 對應函式索引與閱讀順序

1. `problemBuilders`
2. `buildProblemRegistry`
