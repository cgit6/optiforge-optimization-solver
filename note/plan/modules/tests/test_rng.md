# `tests/test_rng.py`

## 模組責任

`test_rng.py` 驗證 seed 驗證、stable task seed 雜湊、seed strategy 與 numpy RNG factory 的基本契約。

## 公開入口/主要類型

- pytest 自動發現測試
- 主要測試群：base seed validation、stable task seed regression、seed strategy mapping、RNG factory、shared repeat seed list

## 主要資料結構與資料契約

負數 base seed 必須被拒絕；既有 regression seed 值不可漂移；`SharedRepeatSeedListStrategy` 必須對每個 problem 重用同一串 repeat seeds。

## 資料流與控制流

測試先鎖定單點 regression 值，再驗證策略展開映射與 RNG factory 重現性。

## 失敗路徑與例外條件

只要 seed mapping 漂移，就會改變整個實驗與 replay 的可重現性，因此這些測試是高敏感度回歸防線。

## 副作用與資源生命週期

純函式測試，無 I/O。

## 與其他模組的關係

目標模組是 `mkp.rng` 與 `mkp.rng.seeding`。

## 對應函式索引與閱讀順序

1. `test_validate_base_seed_rejects_negative_values`
2. `test_stable_task_seed_matches_existing_regression_values`
3. `test_seed_strategy_builds_expected_task_seed_mapping`
4. `test_make_numpy_rng_returns_reproducible_generator`
5. `test_shared_repeat_seed_list_strategy_reuses_same_seed_list_for_each_problem`
6. `test_shared_repeat_seed_list_strategy_requires_repeat_length_match`

## 核心函式與 helper 說明

### `test_validate_base_seed_rejects_negative_values`

這個案例固定 seed 入口的最低防呆規則：`base_seed` 不可為負值。它保護的是所有上層流程共用的前置條件。

### `test_stable_task_seed_matches_existing_regression_values`

這個測試把 `stable_task_seed(...)` 的幾個歷史回歸值寫死，避免 hash 或 seed 演算法被不小心改掉，進而破壞舊實驗可重現性。

### `test_seed_strategy_builds_expected_task_seed_mapping`

這個案例鎖定 `DerivedPerProblemSeedStrategy` 的 key->seed 映射規則，確保 problem/repeat 維度的分配是可推導且穩定的。

### `test_make_numpy_rng_returns_reproducible_generator` / `test_shared_repeat_seed_list_strategy_*`

前者保護 RNG factory 的同 seed 可重現性；後兩個案例則描述 `SharedRepeatSeedListStrategy` 如何跨 problem 重用同一組 repeat seed，以及長度不匹配時必須 fail-fast。
