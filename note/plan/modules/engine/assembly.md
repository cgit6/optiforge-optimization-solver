# `engine/assembly.py`

## 模組責任

`engine/assembly.py` 是核心組裝層。它把 problem registry、problem repository、catalog 掃描、`ProblemBank` shared memory、solver config snapshot 與 solver registry builder 串成一個 `SimulationBundle`，供 `cli.run`、`cli.exp`、`cli.replay` 後續建立 `Simulator`。

## 公開入口/主要類型

- `build(...)`：組裝 `SimulationBundle` 的實際函式。
- `SimulationBundle`：封裝本次執行需要的 catalog、題目 bank、solver 設定與 RNG 策略。
- `Engine.build(...)`：靜態入口，語意上等同於 `build(...)`。

## 主要資料結構與資料契約

- `ExperimentSpec`：宣告 dataset、problem ids、solver ids、repeat、worker count、problem type 與 base seed。
- `CatalogSummary` / `ProblemCatalogEntry`：描述 `problem_root` 掃描結果，確認實驗要求的題目在實體 YAML 目錄中存在。
- `ProblemRepository`：把 YAML 載成 `Problem` model，並做 problem type registry 驗證。
- `ProblemBank`：把本次實驗實際會用到的 problem model 轉成 shared memory pack，讓主行程與 worker 共用。
- `SolverConfigsSnapshot`：把 solver YAML 預載到記憶體，並以 `(solver_id, param_set_index)` 為 key 提供不可變快照語意。

## 資料流與控制流

1. `build(...)` 先用 `problemBuilders()` 建立 `ProblemRegistry`。
2. 建立 `ProblemRepository`，讓 YAML 載入與模型驗證集中在 repository 層。
3. `scanProblemCatalog(...)` 掃描 `problem_root`，建立 catalog 與 summary。
4. `assert_spec_problems_in_catalog(...)` 先檢查實驗要求的 problem 是否真的存在於掃描清單。
5. `validate_spec_problems_in_repository(...)` 再實際載入本次實驗用到的 YAML，提早暴露 schema 或內容錯誤。
6. 建立 `SolverConfigsSnapshot`，把 solver YAML 固定下來。
7. `ProblemBank.build(...)` 依 `ExperimentSpec` 把 problem model 打包到 shared memory。
8. 回傳 `SimulationBundle`；此時還沒有真正建立 `Simulator`。
9. 呼叫端再用 `SimulationBundle.new_simulator()` 或 `new_simulators()` 建立單 solver 調度器。

## 失敗路徑與例外條件

- `problem_root` 不存在或不是目錄時，catalog 掃描階段直接失敗。
- `ExperimentSpec` 中要求的 problem 不在 catalog 時，`assert_spec_problems_in_catalog(...)` 會丟 `FileNotFoundError`。
- YAML 缺檔、格式錯誤、problem type 不一致、loader 驗證失敗，都會在 repository 驗證階段直接中止。
- solver config 缺檔、param set index 不存在、YAML 缺必要欄位，會在 `SolverConfigsSnapshot.build(...)` 內中止。
- `SimulationBundle.new_simulator()` 只接受單一 solver spec；多 solver spec 會要求改用 `new_simulators()`。

## 副作用與資源生命週期

- `ProblemBank.build(...)` 會配置 shared memory block。這是本模組最重要的資源副作用。
- `SimulationBundle` 本身不自動清理 shared memory；呼叫端必須在流程尾端呼叫 `bundle.problem_bank.close()`，或透過 `Simulator.close()` 收尾。
- `new_simulators()` 會共用同一份 `ProblemBank` 與 `SolverConfigsSnapshot`，因此只需要關閉一次 shared memory。

## 與其他模組的關係

- 上游：`cli.run.support`、`experiment.experiment`、`cli.replay.main` 以 `Engine.build(...)` 為組裝入口。
- 下游：`simulator.core` 從 `SimulationBundle` 建出 `Simulator`；`machine.core` 再使用其中的 `ProblemBank`、solver registry 與 config snapshot。
- 依賴：`engine.bank`、`engine.repository`、`engine.configs`、`problem.registry`、`solver.builders`、`rng`。

## 核心函式與 helper 說明

### `build(...)`

- 目的：把一個 `ExperimentSpec` 收斂成可執行的 `SimulationBundle`，並在真正跑 solver 前把 catalog、YAML、solver config 與 shared memory 問題一次驗完。
- 主要輸入：`spec`、`problem_root`、`solver_root`、`seed_strategy`，另可注入 `solver_param_set_indices` 與預建 `solver_configs`。
- 主要輸出：`SimulationBundle`；此時 `ProblemBank` 已建好，`SolverConfigsSnapshot` 也已固定，但尚未產生 `Simulator`。
- 副作用：掃描 problem 目錄、讀 problem YAML、讀 solver YAML、配置 shared memory。
- 主要呼叫者：`cli.run.support.buildSimulationBundle(...)`、`Experiment._build_dataset_simulators(...)`、`cli.replay`。
- 主要被呼叫者：`scanProblemCatalog(...)`、`assert_spec_problems_in_catalog(...)`、`validate_spec_problems_in_repository(...)`、`SolverConfigsSnapshot.build(...)`、`ProblemBank.build(...)`。
- 修改風險：這裡的驗證順序決定 fail-fast 位置；若把 repository 驗證延後，錯誤就會拖到 worker 或 solver 執行時才爆出。

### `SimulationBundle.new_simulator()`

- 目的：把 bundle 轉成單一 solver variant 的 `Simulator`。
- 前提：`spec.solver_ids` 必須只剩一個 solver，否則呼叫端應改用 `new_simulators()`。
- 資料契約：不複製 `ProblemBank` 或 `SolverConfigsSnapshot`，而是直接共用 bundle 內的資源。
- 風險：若呼叫端對 multi-solver spec 誤用這個入口，會在這裡被明確拒絕，而不是默默只挑第一個 solver。

### `SimulationBundle.new_simulators()`

- 目的：把 multi-solver spec 拆成多個 single-solver `Simulator`，讓 `cli.exp` 或 replay 能逐 variant 收集與輸出。
- 控制流：用 `dataclasses.replace(...)` 只替換 `solver_ids`，其餘 dataset/problem/repeat/base_seed 都保持一致。
- 資料契約：所有 `Simulator` 共用同一份 `ProblemBank` 與 `SolverConfigsSnapshot`；這就是 Wave 1 文件中強調的「只關一次 shared memory」來源。
- 修改風險：如果未來把這裡改成深複製 bundle，shared memory 與 config immutability 成本都會上升。

### `SimulationBundle._new_solver_registry()`

- 目的：根據 `solver_builders` 建出新的 `SolverRegistry` instance。
- 為什麼存在：solver registry 本身有可變註冊表，不能在多個 `Simulator` / worker 間共享同一個 registry object。
- 風險：若 builder map 與 `configs/solvers/*.yaml` 中的 `solver_id` 不同步，錯誤通常會在 `Machine.run_task(...)` 建 solver 前才浮現。

### `SimulationBundle.new()`

- 角色：歷史相容 alias，語意等同 `new_simulator()`。
- 維護建議：除非要保留舊呼叫點，不建議再擴充新行為到 `new()`；應以 `new_simulator()` 為單一真實入口。

### `Engine.build(...)`

- 角色：靜態 facade，只是把參數轉交給模組層 `build(...)`。
- 主要價值：讓上游以 `Engine.build(...)` 這個穩定名字使用組裝層，不必直接依賴模組函式。

## 對應函式索引與閱讀順序

1. `build`
2. `SimulationBundle`
3. `SimulationBundle.new_simulator`
4. `SimulationBundle.new_simulators`
5. `SimulationBundle._new_solver_registry`
6. `Engine.build`
