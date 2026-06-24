# `machine/__init__.py`

## 模組責任

`machine/__init__.py` 是 machine layer 的 package 匯出面，重新暴露單 variant 執行與 process pool API。

## 公開入口/主要類型

- `Machine`
- `MachinePool`
- `MachinePoolSession`
- `MachineResult`
- `SimulatorRunRow`

## 主要資料結構與資料契約

- 所有型別都直接來自 `machine/core.py`。
- 這一層不新增資料契約，只定義 package 級匯出面。

## 資料流與控制流

1. 上游 import `mkp.machine`。
2. package 把 core layer 的型別重新暴露。

## 失敗路徑與例外條件

- 若 `machine/core.py` 匯入失敗，這一層也會失敗。

## 副作用與資源生命週期

- 無直接副作用。

## 與其他模組的關係

- 上游：`simulator`、`experiment`、tests、根套件。
- 下游：`machine/core.py`。

## 對應函式索引與閱讀順序

1. `Machine`
2. `MachinePool`
3. `MachinePoolSession`
4. `MachineResult`
5. `SimulatorRunRow`
6. `__all__`
