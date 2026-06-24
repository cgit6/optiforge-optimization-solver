# `engine/builders.py`

## 模組責任

`engine/builders.py` 集中宣告內建 solver builder map。它是 runtime solver registry 的預設來源，讓 `Machine`、`Experiment`、研究工具都能用同一套 solver id 建立 solver instance。

## 公開入口/主要類型

- `solverBuilders()`

## 主要資料結構與資料契約

- 回傳型別是 `dict[str, SolverBuilder]`。
- key 必須與 `configs/solvers/<solver_id>.yaml` 的 `solver_id`、`SolverRegistry.register(...)` 使用的名稱一致。
- value 是零參數 builder，負責回傳新的 solver instance，而不是重用舊實例。

## 資料流與控制流

1. import 各 solver class。
2. `solverBuilders()` 回傳固定 mapping。
3. 上游呼叫端再把這份 mapping 註冊到 `SolverRegistry`，或覆寫其中一部分做測試/實驗。

## 失敗路徑與例外條件

- 任一 solver class import 失敗，會在模組載入階段直接失敗。
- 若這裡的 key 與 solver YAML、`SolverRegistry.create(...)` 使用的名稱不同步，錯誤通常會延後到 registry lookup 或 CLI 驗證階段才浮現。

## 副作用與資源生命週期

- 無執行期副作用；每次呼叫只建立新的 mapping。
- builder lambda 每次都應產生新 solver，避免跨 run 共用可變狀態。

## 與其他模組的關係

- 上游：`cli.run`、`experiment`、研究工具常用它建立標準 `SolverRegistry`。
- 下游：[`solver/registry.py`](../solver/registry.md) 接收 builder；各 solver module 提供實際 class。
- 架構上它是「solver family 與 engine 組裝層」之間的接點。

## 對應函式索引與閱讀順序

1. `solverBuilders`
