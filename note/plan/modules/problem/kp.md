# `problem/kp.py`

## 模組責任

`problem/kp.py` 目前不是可執行題型實作，而是未來 0/1 knapsack 題型的保留擴充點。

## 公開入口/主要類型

- 目前無 class、function 或 registry spec。

## 主要資料結構與資料契約

- 檔案只保留註解，說明未來應在此定義：
  - `KPProblem`
  - YAML loader
  - shared-memory codec
- 因為沒有 `ProblemTypeSpec`，所以主流程無法透過 `problem_type: kp` 載入任何 YAML。

## 資料流與控制流

1. 現階段沒有 runtime 控制流。
2. 任何需要 KP 支援的工作，都必須先補完 model、loader、shared memory pack/attach 與 builder 註冊。

## 失敗路徑與例外條件

- 若讀者誤以為檔案存在就代表 `kp` 已支援，會在 `buildProblemRegistry()` 或 repository 載入階段發現沒有對應 problem type。

## 副作用與資源生命週期

- 無副作用。

## 與其他模組的關係

- 與 [`problem/builders.py`](builders.md) 的關係是「尚未納入 builder map 的保留位」。
- dashboard 與總覽文件應把它視為 extension point，而不是主流程模組。

## 對應函式索引與閱讀順序

1. module docstring
2. inline comment about future `KPProblem`
