# `rng/context.py`

## 模組責任

`rng/context.py` 定義 seed 派生時需要的最小上下文。它把 dataset/problem/repeat 的身份資訊固定成不可變資料模型。

## 公開入口/主要類型

- `SeedContext`

## 主要資料結構與資料契約

- `SeedContext` 包含：
  - `problem_type`
  - `dataset`
  - `problem_ids`
  - `repeat`
- `problem_ids` 必須非空且不可包含空字串。
- `repeat` 必須大於 0。

## 資料流與控制流

1. `Machine._seed_context()` 依 `ExperimentSpec` 建立 `SeedContext`。
2. `SeedStrategy.build_task_seed(s)` 讀取 context 決定種子派生範圍。
3. `stable_task_seed(...)` 或共享 seed list 再把這些 identity 轉成最終 task seed。

## 失敗路徑與例外條件

- 空的 `problem_type`、`dataset`、`problem_ids`，或 `repeat <= 0`，在 dataclass 初始化時就會失敗。

## 副作用與資源生命週期

- 無副作用。
- 此模組的角色是 seed 派生的靜態輸入契約。

## 與其他模組的關係

- 上游：`machine.core` 建立 context。
- 下游：`rng.strategy` 讀取 context 產生 task seed。

## 對應函式索引與閱讀順序

1. `SeedContext`
