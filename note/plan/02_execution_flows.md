# Execution Flows

本文件只描述主流程，不重複展開每個函式的逐行 API。模組級責任與更細的控制細節請直接對照 `note/plan/modules/`。

## 核心資料轉換鏈

主執行鏈路中，資料會沿著下列順序收斂與轉換：

1. `configs/problems/<type>/<dataset>/<problem>.yaml`
2. `ProblemRepository.read_metadata(...)` 或 `ProblemRepository.load(...)`
3. `Problem` model，例如 `MKPProblem`
4. `ProblemBank` shared memory pack
5. `Machine` 取得 `Problem`、solver config、RNG，建立 `RunTask`
6. solver 回傳 `SolveResult`
7. `problem.validate(...)` 產生 `ValidationReport`
8. `tools.stat.machine_result_entries(...)` 轉成 `ResultEntry`
9. `tools.stat.summarize(...)` 轉成 `SummaryReport`
10. `tools.show.write_simulator_result(...)` 寫出 `runs.*` 與 `summary.*`

這條鏈是 `cli.run`、`cli.exp`、`cli.replay` 共用的核心契約。不同 CLI 只是在 task 來源、收集邏輯與輸出層級上不同。

## Shared Memory 生命週期

`ProblemBank` 是目前主流程中最重要的共用資源。

1. `Engine.build(...)` 內部呼叫 `ProblemBank.build(...)`，為本次實驗實際要用的 problem 建立 shared memory。
2. 主行程直接持有 `ProblemBank` 與原始 `Problem` models。
3. process worker 啟動時，`machine.core._configure_process_worker(...)` 透過 `configure_problem_bank_worker(...)` attach `ProblemWorkerView`。
4. worker 只 attach，不 unlink；shared memory 所有權仍屬主行程。
5. `cli.run` 在 `executeSimulator(...)` 的 `finally` 中關閉 `bundle.problem_bank`。
6. `cli.exp` 每個 dataset bundle 結束時，在 `finally` 中呼叫 `simulators[0].close()`；因多個 simulators 共用同一個 bank，關一次即可。
7. `cli.replay` 每個 replay group 結束時，在 `_run_replay_group(...)` 的 `finally` 中呼叫 `sim.close()`。

若流程在 solver 執行前就失敗，通常不會建立 worker attach；若失敗發生在執行中，最外層的 `finally` 仍必須回收主行程的 shared memory。

## `cli.run`

`cli.run` 是單一 solver、單一 param set、單一 dataset/problem type 的直接模擬入口。

### 正常流程

1. `cli/run/main.py::main` 建立 parser 並解析命令列。
2. `cli/run/support.py::createExperimentSpec(...)` 將 CLI 參數轉成 `ExperimentSpec`。
3. `buildSimulationBundle(...)` 驗證 `--set`，並呼叫 `validate_execute_args(...)`。
4. `validate_execute_args(...)`：
   - 用 `ProblemRepository.read_metadata(...)` 讀 problem metadata
   - 確認所有 problem 共享同一組 `problem_type / encoding / direction`
   - 用 `SolverConfigLoader` 檢查 solver capability 與指定 param set
5. `Engine.build(...)`：
   - 掃描 catalog
   - 驗證 spec 中的 problem 都在 catalog 中
   - 真正載入問題 YAML
   - 建立 `SolverConfigsSnapshot`
   - 建立 `ProblemBank`
6. `SimulationBundle.new_simulator()` 建立單 solver `Simulator`。
7. `executeSimulator(...)` 依 `worker_count` 選 `run_sequential()` 或 `run_batch()`。
8. `Machine.run_task(...)` 取得 problem、solver config、RNG、solver instance，呼叫 `solver.solve(...)`。
9. `problem.validate(...)` 把 `SolveResult` 轉成 `ValidationReport`。
10. `tools.show.write_simulator_result(...)` 依 variant 輸出 runs/summary。

### 失敗分支

- `--solver` 非單一值、`--set < 0`、`--problems` 是空 CSV 會在 CLI 支援層失敗。
- problem metadata 若混用不同 type/encoding/direction，`validate_execute_args(...)` 會拒絕執行。
- solver capability 不相容、problem YAML 不存在、problem YAML 損壞、param set 超界，都會在 `Engine.build(...)` 前後 fail-fast。
- batch 模式下若 worker solver registry 未正確註冊，`MachinePool` 會在送 task 前中止。
- solver 執行期錯誤會由 `SolveResult.error` 或直接例外暴露；若是未攔截例外，整個批次中止。

### 輸出形成順序

1. `MachineResult.rows`
2. `ResultEntry` bucket
3. `runs.csv` / `runs.json`
4. `SummaryReport`
5. `summary.csv` / `summary.json`

### 資源回收

- `executeSimulator(...)` 用 `finally` 確保 `bundle.problem_bank.close()` 一定被呼叫。
- `tools.show` 在每個 variant 輸出前會先刪掉舊 output dir，再重建。

## `cli.exp`

`cli.exp` 是多 solver variant 的收集式實驗入口。它不保證每個 repeat 都保留，而是以 evaluator 決定哪些 round 被正式收錄。

### 正常流程

1. `cli/exp/main.py` 載入 evaluator 模組，先完成註冊。
2. `experiment.config.load_config(...)` 解析 `cli/exp/exp_cfg.yaml`：
   - 驗證 top-level schema
   - 驗證 solver param indices
   - 驗證 dataset/problem 存在
   - 驗證 solver capability 對應 problem metadata
3. `Experiment.run(...)` 建立 `output/<experiment_name>`；若已存在會先整棵刪除。
4. 每個 `DatasetSetting` 透過 `_build_dataset_simulators(...)` 建立一份 bundle 與多個 single-solver simulators。
5. `_selected_machines(...)` 從 simulators 中挑出 config 指定的 solver variants。
6. `MachinePool.session()` 建立可重用 process pool。
7. 對每個 problem：
   - `_repeat_window_size(...)` 決定每輪視窗大小
   - `_window_tasks(...)` 只展開當前 repeat window 的 task
   - `session.run_tasks(...)` 執行候選 round
   - `_result_for_repeat(...)` 取出該 repeat 的 `SimulatorResult`
   - `_variant_summaries(...)` 先從 projected rows 算暫時 summary
   - `_evaluate_candidate_round(...)` 呼叫所有 evaluator
   - 若全部 `passed`，才將該 repeat 累積到 collected rows
8. problem collect 完成後，`write_simulator_result(...)` 寫該 problem 下每個 variant 的 runs/summary。
9. `_record_seed_bank_problem(...)` 記錄 variant config snapshot、collected repeat indices 與 run seeds。
10. 所有 dataset 完成後，寫 experiment 層級的 `summary.json` 與 `seed_bank.json`。

### 失敗分支

- evaluator 名稱未註冊時，`Experiment.run(...)` 一開始就會失敗。
- `collects > repeat` 或 evaluator 條件太嚴，導致在 repeat 上限內收不滿樣本時，`_run_problem(...)` 會丟 `RuntimeError`。
- 若某輪 task 之間的 shared round seed 不一致，`_shared_round_seed(...)` 會視為嚴重契約錯誤並中止。
- process pool 中任何 future 失敗，`MachinePoolSession` 會取消 pending futures 並把例外往上拋。
- 某 dataset 的 bundle 建立失敗或輸出目錄建立失敗，會中止該次實驗。

### 輸出形成順序

1. 每個 problem/variant 的 `runs.csv`、`runs.json`
2. 每個 problem/variant 的 `summary.csv`、`summary.json`
3. experiment 根目錄 `summary.json`
4. experiment 根目錄 `seed_bank.json`

### 資源回收

- 每個 dataset 用一個 `MachinePoolSession`，dataset 結束即 shutdown。
- 每組 dataset simulators 共享同一份 `ProblemBank`，在 `finally` 中只關閉一次。

## `cli.replay`

`cli.replay` 依 `seed_bank.json` 重播 `cli.exp` 已接受的 runs，不再重新做 evaluator collect。

### 正常流程

1. `cli/replay/main.py` 解析 `--seed-bank`、`--solver`、`--set`、`--worker`。
2. `load_seed_bank(...)` 讀檔並驗證 seed bank 結構。
3. `variant_config(...)` 取出指定 variant 的 solver config snapshot。
4. `matching_problem_entries(...)` 取出此 variant 真正能重播的 problem entries。
5. `_group_problem_entries(...)` 依 `(dataset, problem_type)` 分組。
6. 每個 group 執行 `_run_replay_group(...)`：
   - 建立單 solver `ExperimentSpec`
   - 用 `Engine.build(...)` 建出對應 dataset/problem type 的 bundle
   - 用 `SolverConfigsSnapshot.from_configs(...)` 固定 replay variant
   - 用 seed bank 裡的 `run_seeds` 直接建立 `RunTask`
   - 用 `MachinePool.run_tasks(...)` 執行
7. 合併所有 rows 成一個單 variant `SimulatorResult`。
8. `write_simulator_result(...)` 寫 replay 輸出，並把 seed bank source metadata 併入 summary。

### 失敗分支

- seed bank 中沒有指定 variant、沒有可重播 problem、結構不合法，replay 前就會失敗。
- 某個 group 內若 problem YAML 不存在或 solver config snapshot 不合法，會在 group 執行期中止。

### 資源回收

- 每個 group 各自建立 bundle 與 `Simulator`，在 `_run_replay_group(...)` 的 `finally` 中立刻關閉 shared memory。

## `cli.convert`

`cli.convert` 是離線資料轉換流程，將 `data/<dataset>` 內的 raw benchmark 轉成 `configs/problems/.../*.yaml`。

1. `cli/convert/main.py` 解析 dataset、converter key、repo root 等參數。
2. `cli/convert/register.py` 提供 benchmark parser 註冊表。
3. `converter.register.getConverter(...)` 找到對應 parser。
4. `converter.converter.transformToYaml(...)` 把 raw data 轉成標準 problem YAML。

這條流程不建立 `ProblemBank`，但它決定了 `ProblemRepository` 後續可以讀到的靜態資料格式。
