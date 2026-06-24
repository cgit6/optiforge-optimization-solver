# `simulator/__init__.py`

## 模組責任

`simulator/__init__.py` 是 simulator package 的匯出面，重新暴露 `Simulator` 與結果型別。

## 公開入口/主要類型

- `Simulator`
- `SimulatorResult`
- `SimulatorRunRow`

## 主要資料結構與資料契約

- 這三個型別都由 `simulator/core.py` 定義。
- package 匯出面本身不增加新的 runtime 契約。

## 資料流與控制流

1. 上游 import `mkp.simulator`。
2. package 把 core 中的型別重新匯出。

## 失敗路徑與例外條件

- 若 `simulator/core.py` 匯入失敗，這一層不可用。

## 副作用與資源生命週期

- 無直接副作用。

## 與其他模組的關係

- 上游：`engine`、`experiment`、tests、根套件。
- 下游：`simulator/core.py`。

## 對應函式索引與閱讀順序

1. `Simulator`
2. `SimulatorResult`
3. `SimulatorRunRow`
4. `__all__`
