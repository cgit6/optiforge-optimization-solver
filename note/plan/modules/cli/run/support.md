# `cli/run/support.py`

## 模組責任

`cli/run/support.py` 是 `cli.run` 在 parser 後面的編排層。它負責把命令列參數轉成 `ExperimentSpec`，驗證 problem 與 solver capability，相容後再組裝 `SimulationBundle`、執行 `Simulator`、輸出結果並回收 shared memory。

## 公開入口/主要類型

- `_splitProblemIds(...)`
- `_splitSolverIds(...)`
- `validate_execute_args(...)`
- `parser()`
- `createExperimentSpec(...)`
- `buildSimulationBundle(...)`
- `executeSimulator(...)`

## 主要資料結構與資料契約

- `cli.run` 一次只接受單一 solver；若要多 solver 比較，應走 `cli.exp`。
- `--set` 必須指定單一 param set index，並且 `>= 0`。
- `ExperimentSpec` 由 CLI 參數直接建立，`base_seed` 對應 `--seed`，代表整次執行的 immutable base seed。
- `validate_execute_args(...)` 要求同一次執行中的所有 problem metadata 必須共享同一個 `(problem_type, encoding, direction)` 組合。

## 資料流與控制流

1. `parser()` 定義 CLI 參數結構。
2. `createExperimentSpec(...)` 解析 problem ids 與 solver ids，建立 `ExperimentSpec`。
3. `buildSimulationBundle(...)` 先驗證 `--set`，再呼叫 `validate_execute_args(...)`。
4. `validate_execute_args(...)` 用 `ProblemRepository.read_metadata(...)` 讀 problem metadata，並用 `SolverConfigLoader` 驗證 solver capability。
5. 驗證通過後，`engine.build(...)` 建出只包含指定 param set 的 `SimulationBundle`。
6. `executeSimulator(...)` 建立 `Simulator`，依 `worker_count` 走 sequential 或 batch。
7. 執行完成後交給 `tools.show.write_simulator_result(...)` 寫出 runs 與 summary。
8. 無論成功失敗，`finally` 都會關閉 `bundle.problem_bank`。

## 失敗路徑與例外條件

- `--solver` 空白、`--problems` 空白 CSV、`--set < 0` 都會在 CLI 支援層直接拒絕。
- problem metadata 混入不同 `problem_type`、`encoding` 或 `direction` 時，`validate_execute_args(...)` 會失敗。
- solver capability 不支援 problem type、encoding 或 direction 時，也會在正式 build 前 fail-fast。
- `engine.build(...)`、`sim.run_batch()`、`sim.run_sequential()` 的任何例外都會往上拋，但 shared memory 仍會在 `finally` 清理。

## 副作用與資源生命週期

- 會讀 `configs/problems` 與 `configs/solvers`。
- `executeSimulator(...)` 會寫 `output/<experiment_name>/<solver_id>/param_<index>/...`。
- shared memory 壽命始於 `buildSimulationBundle(...)` 建出 bank，終於 `executeSimulator(...)` 的 `finally` 區塊。

## 與其他模組的關係

- 上游：`cli/run/main.py` 只負責呼叫這個支援模組。
- 依賴：`engine.assembly`、`engine.repository`、`problem.registry builder`、`tools.solver_config_loader`、`tools.show`。
- 下游：`SimulatorResult` 可再被 `tools.stat` 或測試直接檢查。

## 核心函式與 helper 說明

### `_splitProblemIds(raw)` / `_splitSolverIds(raw)`

- 目的：把 CLI 文字參數正規化成去空白的 tuple。
- 失敗路徑：空字串、只有逗號或全部都是空白片段時直接丟 `ValueError`。
- 在流程中的角色：它們是 `createExperimentSpec(...)` 的第一層輸入閘門，避免把無效 id 帶進 engine。

### `validate_execute_args(...)`

- 目的：在建立 `SimulationBundle` 前先做 problem metadata 與 solver capability 的相容性檢查。
- 控制流：建立標準 `ProblemRegistry` 與 `ProblemRepository`，讀每個 problem 的 metadata，確認 `(problem_type, encoding, direction)` 一致，再用 `SolverConfigLoader` 驗 solver 支援能力。
- 主要被呼叫者：`repository.read_metadata(...)`、`SolverConfigLoader.load(...)` / `load_all(...)`、`_direction_atoms(...)`。
- 失敗路徑：多 solver、混合題型/編碼/方向、solver 不支援問題契約、指定 `param_set_index` 不存在，都會在這裡 fail-fast。
- 修改風險：若把檢查延後到 `engine.build(...)` 或 `Machine.run_task(...)`，錯誤位置會變得更晚、更難診斷。

### `_direction_atoms(direction)`

- 目的：把 scalar 或 tuple 形式的 `DirectionSpec` 正規化成集合，方便 capability 比對。
- 在演算法中的角色：這不是數學 helper，而是 schema bridge，讓 solver YAML 的支援方向宣告能和 problem metadata 對齊。

### `parser()`

- 目的：定義 `cli.run` 的命令列介面。
- 主要輸出：`argparse.ArgumentParser`，其中 `--type` 會映射到 `args.problem_type`，`--set` 映射到單一 `param_set_index`。
- 注意事項：這裡只定義參數結構；真正的語意驗證仍在 `createExperimentSpec(...)` 與 `validate_execute_args(...)`。

### `createExperimentSpec(args)`

- 目的：把 parser 產生的 `Namespace` 轉成不可變的 `ExperimentSpec`。
- 資料契約：保留 CLI 提供的 dataset、problem ids、solver ids、repeat、worker count、base seed；不在這裡做外部 I/O 驗證。
- 主要呼叫者：`cli.run.main.main()` 與 CLI 相關測試。

### `buildSimulationBundle(...)`

- 目的：把 `cli.run` 的單次執行要求轉成可直接執行的 `SimulationBundle`。
- 控制流：先檢查 `param_set_index >= 0`，再做 `validate_execute_args(...)`，最後呼叫 `engine.build(...)` 並把 solver param set 範圍縮成單一 index。
- 角色：它把 `cli.run` 和 `cli.exp` 分開，確保 run 模式不會意外跑整個 param family。

### `executeSimulator(bundle, output_root)`

- 目的：執行 bundle、選擇 sequential 或 batch 路徑、把結果寫到 output。
- 控制流：`bundle.new_simulator()` -> `run_batch()`/`run_sequential()` -> `write_simulator_result(...)` -> `finally: bundle.problem_bank.close()`。
- 副作用：建立執行期 worker、寫 `runs.jsonl`/`summary.json` 等輸出檔，並回收 shared memory。
- 修改風險：`finally` 中的 close 是 `cli.run` shared memory 生命週期的最後保證，不能為了抽象化而省略。

## 對應函式索引與閱讀順序

1. `_splitProblemIds`
2. `_splitSolverIds`
3. `validate_execute_args`
4. `_direction_atoms`
5. `parser`
6. `createExperimentSpec`
7. `buildSimulationBundle`
8. `executeSimulator`
