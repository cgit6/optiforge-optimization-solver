# `rng/strategy.py`

## 模組責任

`rng/strategy.py` 定義 task seed 派生策略。它讓系統可以切換「每個 problem/repeat 派生穩定 seed」或「所有 problem 共用同一組 repeat seed list」等模式。

## 公開入口/主要類型

- `SeedStrategy`
- `DerivedPerProblemSeedStrategy`
- `SharedRepeatSeedListStrategy`

## 主要資料結構與資料契約

- `SeedStrategy` protocol 要求：
  - `build_task_seed(...)`
  - `build_task_seeds(...)`
- `DerivedPerProblemSeedStrategy`：依 problem identity 與 repeat index 派生 stable seed。
- `SharedRepeatSeedListStrategy`：每個 problem 共用同一組 repeat-index 對應 seed。

## 資料流與控制流

1. `Machine.expand_tasks(...)` 先建立 `SeedContext`。
2. `DerivedPerProblemSeedStrategy` 逐 problem/round 呼叫 `stable_task_seed(...)`。
3. `SharedRepeatSeedListStrategy` 則直接把固定 seed list 套到每個 problem 上。
4. 回傳的 seed map 最終變成 `RunTask.task_seed`。

## 失敗路徑與例外條件

- `problem_id` 不在 context 中、`repeat_index` 超界時，兩種策略都會失敗。
- `SharedRepeatSeedListStrategy.seeds` 長度必須等於 `context.repeat`。
- 所有 base seed 都會先經 `validate_base_seed(...)`。

## 副作用與資源生命週期

- 無 I/O 副作用。
- 對可重現性影響很大：改策略等於改 task seed 排程方式。

## 與其他模組的關係

- 上游：`engine.assembly` 把 strategy 注入 bundle；`cli.replay` 與 `cli.exp` 會選擇不同策略語意。
- 下游：`machine.core` 直接依賴這裡生成 `RunTask.task_seed`。

## 對應函式索引與閱讀順序

1. `SeedStrategy`
2. `DerivedPerProblemSeedStrategy.build_task_seeds`
3. `DerivedPerProblemSeedStrategy.build_task_seed`
4. `SharedRepeatSeedListStrategy`
5. `SharedRepeatSeedListStrategy.build_task_seeds`
6. `SharedRepeatSeedListStrategy.build_task_seed`
