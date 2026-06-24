# Validation And Tests

## Purpose

這一層回答的問題不是「功能怎麼跑」，而是「系統怎麼知道自己沒壞」。本專案目前的驗證鏈路分成三層：

1. 執行期 validation：每個 `SolveResult` 都會被 problem model 重新驗證。
2. pytest 自動化測試：保護資料契約、整合流程與 solver regression。
3. `valid/` 研究驗證腳本：保護 legacy equivalence、population trace、benchmark 與 refactor 遷移。

## Runtime Validation Flow

每個 solver 回傳 `SolveResult` 後，資料會沿著這條鏈路被再檢查一次：

1. `solver.solve(...)`
2. `SolveResult`
3. `problem.validate(...)`
4. `ValidationReport`
5. `tools.stat.machine_result_entries(...)`
6. `tools.stat.summarize(...)`
7. `SummaryReport`
8. `cli.exp` evaluator 讀取 projected summary / baseline

其中 problem validation 的核心內容包括：

- `violates_constraints(solution)`：判斷解是否違反限制。
- `fitness(solution)`：重新計算 objective。
- `build_validation_report(...)`：建立 `ValidationReport`，包含 feasible、objective_valid、objective_mismatch、best_known_reached、best_known_gap。

`tools.stat` 只把 feasible 且 objective valid 的 run 納入 objective statistics，並把 infeasible、objective mismatch、runtime error 分類到 `excluded_counts`。這個規則也是 `tests/test_stat.py`、`tests/test_validator.py` 與 `tests/test_exp_evaluation.py` 的共同基礎。

## Pytest Coverage Structure

目前 `tests/` 有 `28` 個 Python 測試檔，且都已補上模組級文件。這批測試大致分成六類。

## 函式級補強現況

目前 `tests/` / `valid/` 的函式級工程說明已補到全覆蓋，但精度仍有主次之分。核心主鏈、solver regression 與研究驗證腳本已是手寫工程說明；薄入口與小型輔助測試則維持較短的函式級條目。重點檔包括：

- 主流程整合：`test_app.py`、`test_engine.py`、`test_machine.py`、`test_simulator.py`、`test_simulator_batch.py`
- 實驗與 evaluator：`test_experiment_run.py`、`test_exp_evaluation.py`
- validation / output 契約：`test_stat.py`、`test_validator.py`、`test_problem_repository.py`、`test_solver_config_loader.py`
- solver regression：`test_bsma_solver.py`、`test_bscasma_solver.py`、`test_rc_numba_solvers.py`
- 遷移驗收：`test_stage1_validation.py`
- 研究驗證腳本：`valid/bsma_equivalence.py`、`valid/bsma_equivalence_batch.py`、`valid/bsma_population_trace.py`、`valid/bsca_population_trace.py`、`valid/bscasma_population_trace.py`、`valid/bsma_numba_gk_benchmark.py`、`valid/stage1_validation.py`

目前剩下的缺口不再是 `tests/valid` 有沒有函式級章節，而是：

- `05_api_reference.md` 對 `tests/valid` 的人工工程補充仍屬選擇性覆蓋，不是每檔都有。
- 小型測試檔雖然已進函式級，但說明深度仍低於 runtime 主鏈與 solver family。
- dashboard 自動檢查與模板句統計仍未自動化。

### 1. 資料契約與問題層

- `tests/test_contracts.py`
- `tests/test_problem_registry.py`
- `tests/test_problem_repository.py`
- `tests/test_tsp_problem_type.py`
- `tests/test_validator.py`
- `tests/test_rng.py`

這一層主要守 `ProblemModel`、`RunTask`、`SolveResult`、repository YAML、problem validation 與 seed contract。它們是所有上層流程的最低依賴。

### 2. CLI / Engine / Simulator / Machine 整合層

- `tests/test_app.py`
- `tests/test_engine.py`
- `tests/test_machine.py`
- `tests/test_simulator.py`
- `tests/test_simulator_batch.py`

這一層守住從 CLI 參數、bundle 組裝、task 展開、shared seed 到 batch/process worker 的主執行鏈。

### 3. Solver regression 層

- `tests/test_bsma_solver.py`
- `tests/test_bsca2_solver.py`
- `tests/test_bscasma_solver.py`
- `tests/test_rc_numba_solvers.py`
- `tests/test_continuous_to_binary.py`
- `tests/test_solver_registry.py`

這一層重點在同 seed determinism、stop condition、repair/helper 契約、metadata，以及 hot-loop 相關 feature flag 的回歸。

### 4. Experiment / Evaluator / Replay 層

- `tests/test_cli_exp.py`
- `tests/test_exp_config.py`
- `tests/test_exp_evaluation.py`
- `tests/test_experiment_run.py`
- `tests/test_seed_bank_replay.py`

這一層守 collect scheduler、evaluator registry、projected summary 判斷、seed bank 與 replay snapshot 契約。

### 5. 統計與輸出層

- `tests/test_stat.py`
- `tests/test_solver_config_loader.py`
- `tests/test_converter_registry.py`

這一層守 summary 規則、excluded counts、solver YAML schema 與 raw benchmark 轉 problem YAML 的資料鏈。

### 6. 研究輔助工具層

- `tests/test_mkp_item_eval_experiment.py`
- `tests/test_mkp_score_scaffold.py`
- `tests/test_stage1_validation.py`

這些測試不是主 runtime，但保護研究腳手架與重型驗證腳本的最小 helper 契約。

## `valid/` Research Validation Structure

`valid/` 目前有 `8` 個 Python 模組。它們和 pytest 的差別在於：這些腳本通常較重、執行成本較高，而且比較接近「研究結果是否仍然一致」而不是「程式介面是否合法」。

### 1. 嚴格等價驗證

- `valid/bsma_equivalence.py`
- `valid/bsma_equivalence_batch.py`

用途：

- 比對 `old/BSMA.py` 與現行 `solver/BSMA.py` 是否在同 seed、同 budget 下產生一致 trace / objective / solution。
- 批次版會把單題驗證擴成 WEISH 題庫級別的整批驗證。

### 2. Population Trace 驗證

- `valid/bsma_population_trace.py`
- `valid/bsca_population_trace.py`
- `valid/bscasma_population_trace.py`

用途：

- 把 old/new solver 在每個 phase、每個 iteration、每個 rank 的 population snapshot 拉出來逐列比較。
- 若 refactor 後行為漂移，這類腳本能定位第一個 mismatch。
- `bscasma_population_trace.py` 還額外記錄 old 版本已知 crash 行為是否與新版本一致。

### 3. Benchmark 與遷移驗收

- `valid/bsma_numba_gk_benchmark.py`
- `valid/stage1_validation.py`

用途：

- benchmark 腳本偏向 `bsma` / `bsma_numba` 實際題目上的結果與耗時比較。
- stage1 validation 會同時跑 legacy script 與新 CLI，驗證 refactor 是否仍能重現 baseline。

## Validation/Test Flow By Change Type

### 文件或 config-only 修改

1. 靜態檢查 `note/plan` 與 dashboard 同步。
2. 若動到 experiment config schema，再跑 `tests/test_exp_config.py`。

### CLI / Engine / Simulator / Machine 修改

1. `tests/test_app.py`
2. `tests/test_engine.py`
3. `tests/test_machine.py`
4. `tests/test_simulator.py`
5. `tests/test_simulator_batch.py`

### Solver / hot-loop helper 修改

1. 對應 solver pytest：`tests/test_bsma_solver.py`、`tests/test_bsca2_solver.py`、`tests/test_bscasma_solver.py`、`tests/test_rc_numba_solvers.py`
2. 若改到 continuous-to-binary / CTF helper，再跑 `tests/test_continuous_to_binary.py`
3. 視風險加跑：
   - `valid/bsma_equivalence.py`
   - `valid/*_population_trace.py`
   - `valid/bsma_numba_gk_benchmark.py`

### Experiment / evaluator / replay 修改

1. `tests/test_cli_exp.py`
2. `tests/test_exp_config.py`
3. `tests/test_exp_evaluation.py`
4. `tests/test_experiment_run.py`
5. `tests/test_seed_bank_replay.py`

### Validation / stat / output 修改

1. `tests/test_validator.py`
2. `tests/test_stat.py`
3. 需要時補跑 `tests/test_exp_evaluation.py`，因 evaluator 直接依賴 summary contract

### Legacy/refactor 遷移修改

1. `tests/test_stage1_validation.py`
2. `valid/stage1_validation.py`
3. 視 solver 家族選擇對應 equivalence / population trace

## 與模組級文件的關係

- `note/plan/modules/tests/*.md`：回答每個 pytest 模組在保什麼契約。
- `note/plan/modules/valid/*.md`：回答每個研究驗證腳本比較什麼、輸出什麼、成本在哪裡。
- 本文件：回答這兩層在整個系統裡如何分工、什麼時候該跑哪一層。
