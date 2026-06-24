# `cli/replay/main.py`

## 模組責任

`cli/replay/main.py` 負責把 `seed_bank.json` 中已接受的 run seed 重播一次。它不是重新做 collect，而是用舊 seed 與舊 solver config snapshot 重建當時的 variant 執行。

## 公開入口/主要類型

- `parser()`
- `main(...)`
- `replay_seed_bank(...)`
- `_group_problem_entries(...)`
- `_run_replay_group(...)`

## 主要資料結構與資料契約

- `seed_bank.json` 必須包含：
  - 變體快照 `variants`
  - 可重播題目條目 `problems`
  - `run_seeds`
- replay 只接受單一 `(solver_id, param_set_index)`。
- `_group_problem_entries(...)` 以 `(dataset, problem_type)` 分組，確保一個 `ExperimentSpec` 只對應單一 dataset/problem type。
- `_run_replay_group(...)` 直接建立 `RunTask`，不再透過 seed strategy 派生 seed。

## 資料流與控制流

1. `parser()` 讀 `--seed-bank`、`--solver`、`--set`、`--worker`。
2. `replay_seed_bank(...)` 載入並驗證 seed bank。
3. `variant_config(...)` 取出指定 solver variant 的 solver config snapshot。
4. `matching_problem_entries(...)` 找出此 variant 真正能重播的 problem 清單。
5. `_group_problem_entries(...)` 依 dataset/problem type 分組。
6. 每個 group 呼叫 `_run_replay_group(...)`：
   - 建立單 solver `ExperimentSpec`
   - 用 `Engine.build(...)` 建 bundle
   - 用 `SolverConfigsSnapshot.from_configs(...)` 把 seed bank 內的 config 固定下來
   - 依 `run_seeds` 建 `RunTask`
   - 用 `MachinePool.run_tasks(...)` 執行
7. 所有 rows 合併成單一 `SimulatorResult`，最後用 `write_simulator_result(...)` 輸出 replay 結果。

## 失敗路徑與例外條件

- `--set < 0` 或 `worker_count <= 0` 會立即失敗。
- seed bank 結構不合法、找不到指定 variant、找不到可重播 problem，會在 replay 前中止。
- 若某個 replay group 在執行時發生 solver 或 problem 載入錯誤，整個 replay 流程會中止。
- `_run_replay_group(...)` 的 `finally` 會呼叫 `sim.close()`，避免 group 之間累積 shared memory。

## 副作用與資源生命週期

- 會讀 `seed_bank.json` 與 `configs/problems`。
- 每個 group 都會建立一份新的 `ProblemBank`；group 結束時立即關閉。
- 會在 `output/<experiment_name>/...` 下輸出 replay 結果，並附帶來源 seed bank metadata。

## 與其他模組的關係

- 上游：seed bank 由 `experiment.experiment` 產生。
- 依賴：`experiment.seed_bank`、`engine.assembly`、`engine.configs`、`machine.core`、`tools.show`。
- 下游：輸出的 `SimulatorResult` 結構與 `cli.run` 一致，因此 `tools.stat` 與 tests 可以共用檢查方式。

## 對應函式索引與閱讀順序

1. `parser`
2. `main`
3. `replay_seed_bank`
4. `_group_problem_entries`
5. `_run_replay_group`
