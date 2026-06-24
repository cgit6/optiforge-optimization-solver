# `rng/factory.py`

## 模組責任

`rng/factory.py` 定義 solver 執行時的 RNG factory 契約與預設實作。

## 公開入口/主要類型

- `RngFactory`
- `make_numpy_rng(...)`

## 主要資料結構與資料契約

- `RngFactory` 是 `Callable[[int], np.random.Generator]`。
- `make_numpy_rng(...)` 目前固定回傳 `np.random.default_rng(seed)`。

## 資料流與控制流

1. `Engine.build(...)` 預設把 `make_numpy_rng` 放進 `SimulationBundle`。
2. `Machine.run_task(...)` 以 `task_seed` 呼叫 factory。
3. solver 只收到 `np.random.Generator`，不關心 factory 的實作來源。

## 失敗路徑與例外條件

- 本模組本身沒有驗證邏輯；若 seed 型別異常，多半會由 numpy 自身處理。

## 副作用與資源生命週期

- 無檔案或全域副作用。
- 每次 factory 呼叫都會建立獨立 generator，避免 task 之間共享 RNG 狀態。

## 與其他模組的關係

- 上游：`engine.assembly`、`machine.core`。
- 下游：所有 solver adapter 透過 `Machine` 間接使用這裡建立的 generator。

## 對應函式索引與閱讀順序

1. `RngFactory`
2. `make_numpy_rng`
