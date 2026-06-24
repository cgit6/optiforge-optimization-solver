# `tests/test_seed_bank_replay.py`

## 模組責任

`test_seed_bank_replay.py` 驗證 `cli.exp` 產出的 `seed_bank.json` 與 `cli.replay` 之間的重播契約。

## 公開入口/主要類型

- pytest 自動發現測試
- 主要 helper：`_clear_evaluators`、`_write_problem_yaml`、`_write_solver_yaml`、`_write_exp_yaml`、`_run_experiment`
- 主要測試群：seed bank write、snapshot replay、unknown variant fail-fast

## 主要資料結構與資料契約

seed bank 必須記錄 problem run seeds 與 variant config snapshot；replay 必須使用 snapshot，而不是讀當前 solver YAML。

## 資料流與控制流

helpers 先跑最小 experiment 產生 seed bank，再測 replay 使用 snapshot、缺 variant 時 fail-fast。

## 失敗路徑與例外條件

若 replay 偷讀當前 YAML 或允許未記錄 variant 被重播，collect 的可重現性就失效。

## 副作用與資源生命週期

會在 `tmp_path` 寫出 experiment output、seed bank 與 replay output。

## 與其他模組的關係

目標模組是 `mkp.experiment`、`mkp.cli.replay` 與 `mkp.experiment.experiment`。

## 對應函式索引與閱讀順序

1. `_clear_evaluators`
2. `_write_problem_yaml`
3. `_write_solver_yaml`
4. `_write_exp_yaml`
5. `_run_experiment`
6. `test_exp_writes_seed_bank_with_problem_seeds_and_variant_snapshot`
7. `test_replay_uses_seed_bank_solver_config_snapshot_not_current_yaml`
8. `test_replay_fails_for_unrecorded_solver_variant`

## 核心函式與 helper 說明

### `_clear_evaluators` 與 YAML/project helper 群

`_clear_evaluators` 先清空全域 evaluator registry，避免 seed-bank / replay 測試互相污染。`_write_problem_yaml`、`_write_solver_yaml`、`_write_exp_yaml`、`_run_experiment` 則建立最小的 collect + replay 測試場景。

### `test_exp_writes_seed_bank_with_problem_seeds_and_variant_snapshot`

這個案例描述 seed bank 的主資料契約：版本號、來源 experiment 名稱、variant 快照、每個 problem 收集到的 repeat index 與 run seeds 都必須被完整寫出。

### `test_replay_uses_seed_bank_solver_config_snapshot_not_current_yaml`

這是 replay 功能最重要的 regression test。它故意在實驗完成後修改當前 solver YAML，確認 replay 仍應該使用 seed bank 內保存的 solver config snapshot，而不是讀現況檔案。

### `test_replay_fails_for_unrecorded_solver_variant`

這個案例固定 replay 的 fail-fast 邊界：seed bank 沒記錄的 solver variant 不得被靜默回退或猜測。
