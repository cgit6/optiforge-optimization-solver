# `rng/__init__.py`

## 模組責任

`rng/__init__.py` 是 RNG 子系統的封裝入口。它把 seed context、seed strategy 與 RNG factory 重新匯出，讓上游模組不用分別知道子檔案位置。

## 公開入口/主要類型

- `SeedContext`
- `RngFactory`
- `make_numpy_rng(...)`
- `SeedStrategy`
- `DerivedPerProblemSeedStrategy`
- `SharedRepeatSeedListStrategy`

## 主要資料結構與資料契約

- 對外公開的是 `__all__` 中列出的 RNG API。
- 上游通常只依賴 `rng` 套件層，不需要直接碰 `rng.context`、`rng.seeding`、`rng.factory`、`rng.strategy` 的檔案路徑。

## 資料流與控制流

1. 上游模組 `from ..rng import ...`。
2. `rng.__init__` 將具體型別與函式自子模組重新匯出。
3. `Machine`、`Engine`、`Experiment` 在組裝時以這些匯出名稱使用 seed strategy 與 factory。

## 失敗路徑與例外條件

- 本模組本身沒有業務邏輯；錯誤主要來自被匯出的子模組。
- 若子模組匯出名稱變更但 `__all__` 未同步，會造成上游 import 契約中斷。

## 副作用與資源生命週期

- 無 I/O、shared memory 或全域狀態副作用。
- 生命週期重點是維持 package-level import API 的穩定性。

## 與其他模組的關係

- 上游：`engine.assembly`、`machine.core`、`experiment.experiment`、`cli.replay.main`。
- 下游：`rng.context`、`rng.factory`、`rng.strategy` 提供真正實作。

## 對應函式索引與閱讀順序

1. `SeedContext`
2. `RngFactory`
3. `make_numpy_rng`
4. `SeedStrategy`
5. `DerivedPerProblemSeedStrategy`
6. `SharedRepeatSeedListStrategy`
