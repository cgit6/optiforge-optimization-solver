# `engine/__init__.py`

## 模組責任

`engine/__init__.py` 是 engine 子系統的 package 匯出面，集中暴露 `Engine`、`SimulationBundle`、`build(...)` 與 `SolverConfigsSnapshot`。

## 公開入口/主要類型

- `Engine`
- `SimulationBundle`
- `build`
- `SolverConfigsSnapshot`

## 主要資料結構與資料契約

- `Engine` / `SimulationBundle` 來自 `assembly.py`。
- `SolverConfigsSnapshot` 來自 `configs.py`。
- 這一層本身不建立新的契約，只重新組織 engine API。

## 資料流與控制流

1. 上游 import `mkp.engine`。
2. package 重新暴露組裝層常用型別與函式。
3. 下游實作仍由 `assembly.py`、`configs.py` 等模組承擔。

## 失敗路徑與例外條件

- 若下游模組匯入失敗，整個 engine package 匯出面都會失敗。

## 副作用與資源生命週期

- 無直接 I/O 或 shared memory 副作用。

## 與其他模組的關係

- 上游：CLI、experiment、tests、根套件 `mkp`。
- 下游：`engine/assembly.py`、`engine/configs.py`。

## 對應函式索引與閱讀順序

1. `Engine`
2. `SimulationBundle`
3. `build`
4. `SolverConfigsSnapshot`
5. `__all__`
