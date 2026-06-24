# Data And Config

## 資料與設定的責任分界

這個專案的資料契約可以分成四層：

1. 原始 benchmark 層：`data/<dataset>/...`
2. 正式 problem 定義層：`configs/problems/<problem_type>/<dataset>/<problem>.yaml`
3. solver / experiment 設定層：`configs/solvers/*.yaml`、`cli/exp/exp_cfg.yaml`
4. 執行輸出層：`output/...`

其中第 1、2、3 層屬於「建置前或執行前配置」，第 4 層屬於 runtime 產物。

## 原始資料到摘要報表的契約鏈

核心資料會沿著下列鏈路流動：

1. `data/<dataset>` raw 檔
2. `cli.convert` / `cli/convert/register.py` / `converter.*` parser
3. `configs/problems/<problem_type>/<dataset>/*.yaml`
4. `ProblemRepository.read_metadata(...)` 或 `load(...)`
5. `problem/yaml.py` + 各 `problem/*` loader 建立 `Problem` model，例如 `MKPProblem`、`TSPProblem`
6. `ProblemBank` shared memory pack
7. `Machine` / `RunTask`
8. `SolveResult`
9. `ValidationReport`
10. `ResultEntry`
11. `SummaryReport`
12. `tools.show` 寫出的 `runs.*` 與 `summary.*`

如果鏈路中任一層的 identity 或 schema 不一致，系統會盡量在靠前位置 fail-fast，而不是等到 solver 執行時才發現。

## Build-time 與 Runtime 的分界

### Build-time / 執行前

- `data/<dataset>`：原始 benchmark，只供 converter 使用。
- `configs/problems/.../*.yaml`：正式 problem schema，供 repository 與 config 驗證使用。
- `configs/solvers/*.yaml`：solver 能力與 param set 宣告，供 `SolverConfigLoader`、`SolverConfigsSnapshot`、`experiment.config` 使用。
- `cli/exp/exp_cfg.yaml`：實驗排程描述，定義要跑哪些 solver variants、dataset settings、problems 與 evaluators。

### Runtime / 執行期

- `ProblemRepository`：把 problem YAML 載入成 `Problem` model。
- `SolverConfigsSnapshot`：把 solver YAML 載入成記憶體快照。
- `ProblemBank`：把本次執行實際要用的題目轉成 shared memory。
- `Machine` / `MachinePool` / `Simulator` / `Experiment`：真正執行 solver、validation、collect。
- `output/...`：本次執行的正式產物。

重點是：problem YAML 與 solver YAML 在 runtime 會被讀取，但它們的責任仍然是「提供靜態契約」；真正的執行期狀態是 repository model、config snapshot、task、solve result 與 summary。

## Problem type builder 與 YAML validator

problem family 是否真的能進 runtime，不是看 repo 裡有沒有 `problem/*.py`，而是看兩層契約：

- [`problem/builders.py`](modules/problem/builders.md)
  - 決定哪些 `ProblemTypeSpec` 會被註冊進 `ProblemRegistry`
  - 目前啟用的是 `mkp` 與 `tsp`
- [`problem/yaml.py`](modules/problem/yaml.md)
  - 提供所有 loader 共用的必要欄位檢查與 identity 檢查

因此：

- `problem/kp.py`、`problem/vrp.py` 目前只是 extension point，不是有效 problem type
- `ProblemRepository` 是否能載入某個 YAML，取決於：
  1. 檔案路徑是否符合 `resolve_path(...)`
  2. `problem_type` 是否已在 builder map 中啟用
  3. 對應 loader/model 是否通過 schema 與 shape 驗證

## Problem YAML

problem YAML 的 canonical 路徑是 `configs/problems/<problem_type>/<dataset>/<problem_id>.yaml`。目前 runtime 已啟用的 problem type 是 `mkp` 與 `tsp`，但 repo 內已提交的正式 catalog 幾乎都仍是 MKP。

### 路徑契約

- 第一層：`problem_type`
- 第二層：`dataset`
- 檔名：`<problem_id>.yaml`

`ProblemRepository.resolve_path(...)` 完全依賴這個路徑規則。

`engine/bank.scan_catalog(...)` 也只會掃描 `configs/problems/<problem_type>/<dataset>/*.yaml` 這一層，不會遞迴到更深的子目錄。

### 內容契約

典型 MKP YAML 欄位：

- `problem_id`
- `dataset`
- `problem_type`
- `items`
- `dim`
- `values`
- `weights`
- `capacities`
- `best_known`

典型 TSP YAML 欄位：

- `problem_id`
- `dataset`
- `problem_type: tsp`
- `n_cities`
- `distance_matrix`
- `best_known`
- `coords`（可選）

### 執行期責任

- `ProblemRepository.read_metadata(...)` 先讀 `problem_type`、`encoding`、`direction` 做 fail-fast 驗證。
- `ProblemRepository.load(...)` 再用 registry loader 建立 `Problem` model。
- `ProblemBank.build(...)` 只會把本次 `ExperimentSpec` 真正用到的 problem 轉進 shared memory。

### 題型現況與既有資料差異

- runtime builder 已支援 `tsp`，對應 loader 在 [`problem/tsp.py`](modules/problem/tsp.md)。
- 但 repo 目前已提交的 TSP 範例 YAML 位於 `configs/problems/mkp/tsp/SMALL/*.yaml`，不是 canonical 的 `configs/problems/tsp/SMALL/*.yaml`。
- 這代表：
  - TSP 題型支援是存在的
  - 但正式 catalog 仍以 MKP 為主
  - TSP canonical path 目前主要由 [`tests/test_tsp_problem_type.py`](modules/tests/test_tsp_problem_type.md) 的臨時 fixture 驗證
- 文件上應把這些 `mkp/tsp/SMALL` 檔視為參考資料，而不是標準 catalog 佈局的代表例。

### 目前清點

- `mkp/GK`: `11` YAML files
- `mkp/HP`: `2` YAML files
- `mkp/OR10x100`: `30` YAML files
- `mkp/OR10x250`: `30` YAML files
- `mkp/OR10x500`: `30` YAML files
- `mkp/OR30x100`: `30` YAML files
- `mkp/OR30x250`: `30` YAML files
- `mkp/OR30x500`: `30` YAML files
- `mkp/OR5x100`: `30` YAML files
- `mkp/OR5x250`: `30` YAML files
- `mkp/OR5x500`: `30` YAML files
- `mkp/PB`: `6` YAML files
- `mkp/PET`: `6` YAML files
- `mkp/SENT`: `2` YAML files
- `mkp/WEING`: `8` YAML files
- `mkp/WEISH`: `30` YAML files
- `mkp/tsp`: `2` YAML files（位於 `SMALL/` 子目錄，屬於非 canonical TSP sample path）
- `mkp/tsp`: `2` YAML files

## Solver YAML

solver YAML 位於 `configs/solvers/*.yaml`，由 `tools.solver_config_loader.SolverConfigLoader` 載入。

### 靜態責任

- 宣告 `solver_id`
- 宣告 `solver_class`
- 宣告 solver `capabilities`
- 宣告 `stop_condition`
- 宣告全部 `params` 組

### 執行期責任

- `experiment.config` 用它驗證 `param_idx` 是否存在、solver capability 是否相容。
- `SolverConfigsSnapshot.build(...)` 會在 engine 組裝階段把指定 solver variants 預載入記憶體。
- `Machine.run_task(...)` 執行前只會從快照複製一份 config，再補上 `run_seed`；不直接讀檔。

### 重要欄位

- `solver_id`
- `solver_class`
- `capabilities.problem_types`
- `capabilities.encodings`
- `capabilities.directions`
- `stop_condition`
- `params`

### 目前 solver config

- `brlsmasca`: `1` param sets, path `configs/solvers/brlsmasca.yaml`
- `brlsmasca_rl_numba`: `27` param sets, path `configs/solvers/brlsmasca_rl_numba.yaml`
- `brlsmasca_rl_rc_numba`: `27` param sets, path `configs/solvers/brlsmasca_rl_rc_numba.yaml`
- `brlsmasca_test_numba`: `9` param sets, path `configs/solvers/brlsmasca_test_numba.yaml`
- `bsca`: `1` param sets, path `configs/solvers/bsca.yaml`
- `bsca_numba`: `9` param sets, path `configs/solvers/bsca_numba.yaml`
- `bsca_rc_numba`: `9` param sets, path `configs/solvers/bsca_rc_numba.yaml`
- `bsma`: `3` param sets, path `configs/solvers/bsma.yaml`
- `bsma_numba`: `9` param sets, path `configs/solvers/bsma_numba.yaml`
- `bsma_rc_numba`: `9` param sets, path `configs/solvers/bsma_rc_numba.yaml`

## `cli/exp/exp_cfg.yaml`

`cli/exp/exp_cfg.yaml` 是 collect 實驗的排程檔。

### 靜態責任

- 宣告實驗名稱 `experiment_name`
- 宣告要收幾個樣本 `collects`
- 宣告 solver selections `solvers`
- 宣告 repeat 上限 `repeat`
- 宣告 dataset/problem/evaluator 排程 `dataset_settings`

### 執行期責任

- `experiment.config.load_config(...)` 會把它解析成 `ExperimentConfig`。
- `Experiment.run(...)` 依此建立 dataset 專屬 `ExperimentSpec` 與 collect loop。
- evaluator 名稱只在執行開始前檢查是否已註冊；是否通過則在每輪 collect 時決定。

### 關鍵欄位

- `solvers[].solver`
- `solvers[].param_idx`
- `dataset_settings[].experiment-id`
- `dataset_settings[].dataset`
- `dataset_settings[].type`
- `dataset_settings[].problems[].problem`
- `dataset_settings[].problems[].evaluation`
- `dataset_settings[].problems[].base_line`

## Raw Data

原始 benchmark 位於 `data/<dataset>`。正式文件不逐筆抄內容，只保留格式、來源與目錄清點。

raw data 到 YAML 的 parser 對應主要在 [`cli/convert/register.py`](modules/cli/convert/register.md)：

- WEISH / WEING / PB / PET / SENT / HP / CB：共用 flat-number 格式切片
- GK：使用逐 item row 格式

- `GK`: `11` raw files
- `GK2`: `11` raw files
- `HP`: `2` raw files
- `OR10x100`: `31` raw files
- `OR10x250`: `31` raw files
- `OR10x500`: `31` raw files
- `OR30x100`: `31` raw files
- `OR30x250`: `31` raw files
- `OR30x500`: `31` raw files
- `OR5x100`: `31` raw files
- `OR5x250`: `31` raw files
- `OR5x500`: `31` raw files
- `PB`: `6` raw files
- `PB2`: `156` raw files
- `PET`: `6` raw files
- `SENT`: `2` raw files
- `WEING`: `8` raw files
- `WEISH`: `30` raw files

## Output

### `cli.run` / `cli.replay` 的 variant 輸出

`tools.show.write_simulator_result(...)` 依 `(solver_id, param_set_index)` 寫入：

```text
output/<experiment_name>/<solver_id>/param_<index>/
  runs.csv
  runs.json
  summary.csv
  summary.json
```

### `cli.exp` 的輸出層級

`cli.exp` 會在上述 variant 目錄之外，再多一層 dataset experiment id 與 problem id：

```text
output/<experiment_name>/<dataset_experiment_id>/<problem_id>/<solver_id>/param_<index>/
  runs.csv
  runs.json
  summary.csv
  summary.json

output/<experiment_name>/
  summary.json
  seed_bank.json
```

### 輸出形成責任

- `runs.*`：每筆 run 的標準化紀錄。
- `summary.*`：單一 solver variant 的統計摘要。
- experiment 根目錄 `summary.json`：problem collect 結果摘要。
- `seed_bank.json`：後續 `cli.replay` 的正式輸入。
