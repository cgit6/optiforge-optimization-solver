# `problem/vrp.py`

## 模組責任

`problem/vrp.py` 目前是 vehicle routing problem 的保留擴充點，尚未進入 runtime 主流程。

## 公開入口/主要類型

- 目前無 class、function 或 registry spec。

## 主要資料結構與資料契約

- 檔案只保留註解，說明未來應在此定義：
  - `VRPProblem`
  - loader
  - shared-memory codec
- 因為沒有 builder 與 registry spec，任何 `problem_type: vrp` YAML 都不會被主流程接受。

## 資料流與控制流

1. 現階段沒有 runtime 控制流。
2. 若未來啟用 VRP，仍需同步補上 registry、repository、tests 與 module guide。

## 失敗路徑與例外條件

- 目前主要風險是名稱誤導；檔案存在不等於系統已支援 VRP。

## 副作用與資源生命週期

- 無副作用。

## 與其他模組的關係

- 與 [`problem/builders.py`](builders.md) 的關係和 `kp.py` 相同：是尚未納入 builder map 的 extension point。
- dashboard 中不應把它算成缺失功能，而應算成已明示的未啟用題型。

## 對應函式索引與閱讀順序

1. module docstring
2. inline comment about future `VRPProblem`
