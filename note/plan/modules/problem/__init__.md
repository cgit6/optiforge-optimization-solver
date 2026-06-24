# `problem/__init__.py`

## 模組責任

`problem/__init__.py` 是 problem package 的對外匯出面。它把主流程需要的抽象型別、registry API、MKP/TSP model 與 validation 型別重新匯出。

## 公開入口/主要類型

- `Direction`
- `DirectionSpec`
- `ObjectiveValue`
- `ScalarObjective`
- `Problem`
- `ProblemModel`
- `MKPProblem`
- `TSPProblem`
- `ProblemRegistry`
- `ProblemTypeSpec`
- `ValidationReport`
- `problemBuilders`
- `buildProblemRegistry`

## 主要資料結構與資料契約

- `ProblemModel` 目前被別名到 `MKPProblem`，這是現況相容設計，不代表 registry 只支援 MKP。
- `__all__` 定義 package 對外保證的符號集合。
- 真正可註冊的 problem family 以 `problemBuilders()` 為準，目前是 `mkp` 與 `tsp`。

## 資料流與控制流

1. 外部 import `problem` package。
2. package 重新暴露 builders、interface、registry、validation 與主 problem models。
3. 真正的 YAML 載入、shared memory 與 validation 行為仍在各子模組中完成。

## 失敗路徑與例外條件

- 若 re-export 名稱與子模組不同步，會在 import 階段失敗。
- `ProblemModel = MKPProblem` 可能讓讀者誤以為其他題型已完全整合；維護時需以 `buildProblemRegistry()` 的實際註冊內容為準。

## 副作用與資源生命週期

- 幾乎沒有執行期副作用。
- 主要責任是維持 package API 穩定，降低呼叫端對子模組路徑的耦合。

## 與其他模組的關係

- 上游：`engine.repository`、`tools`、`tests`、solver 支援工具大量使用 `from ..problem import ...`。
- 下游：[`problem/builders.py`](builders.md)、[`problem/mkp.py`](mkp.md)、[`problem/tsp.py`](tsp.md)、[`problem/validation.py`](validation.md)。

## 對應函式索引與閱讀順序

1. package-level exports
2. `ProblemModel`
3. `__all__`
