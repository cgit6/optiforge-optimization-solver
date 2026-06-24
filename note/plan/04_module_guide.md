# Module Guide

本文件是模組級文件的入口頁。Wave 1 先補核心執行鏈路，Wave 2 補 solver/rng/converter 與 `cli.exp` 支撐模組，Wave 3 再把 `cli.exp` evaluator 家族補到 `.py` 粒度，Wave 4 把 `tests/` 與 `valid/` 驗證鏈路補到 `.py` 粒度，Wave 5 則把剩餘非 `old/` source module 全數補齊，包含薄入口、problem 次題型、`cli.convert` 與 `tools` 分析支援鏈。

## 建議閱讀順序

1. `cli.run` 主鏈路
2. `engine` 組裝層
3. `problem` 契約層
4. `simulator` / `machine` 執行層
5. `tools.stat` / `tools.show` 統計與輸出層
6. `cli.exp` collect 鏈路
7. `cli.replay` 重播鏈路
8. `solver` 演算法家族
9. `rng` 種子派生層
10. `converter` 與 `cli.convert` 原始資料轉換層
11. 演算法支援工具層
12. `tests` 自動化驗證層
13. `valid` 研究驗證層
14. package / wiring 薄入口層

## 核心鏈路模組

### CLI 入口

- [`cli/__init__.py`](modules/cli/__init__.md)：`cli` package 邊界與子命令命名空間。
- [`cli/run/__init__.py`](modules/cli/run/__init__.md)：`cli.run` package 邊界。
- [`cli/run/__main__.py`](modules/cli/run/__main__.md)：`python -m ...cli.run` 的薄啟動層。
- [`cli/run/main.py`](modules/cli/run/main.md)：單次執行 CLI 的薄 wiring 入口。
- [`cli/run/support.py`](modules/cli/run/support.md)：`cli.run` 的命令列轉譯、capability 驗證、bundle 建立、執行與資源回收。
- [`cli/convert/__init__.py`](modules/cli/convert/__init__.md)：`cli.convert` package 邊界。
- [`cli/convert/__main__.py`](modules/cli/convert/__main__.md)：`python -m ...cli.convert` 的薄啟動層。
- [`cli/convert/main.py`](modules/cli/convert/main.md)：raw dataset 轉 problem YAML 的命令列入口。
- [`cli/convert/register.py`](modules/cli/convert/register.md)：各 raw dataset parser 與 import-time registry 註冊。
- [`cli/exp/main.py`](modules/cli/exp/main.md)：`cli.exp` 的 evaluator 註冊與預設配置執行入口。
- [`cli/exp/__init__.py`](modules/cli/exp/__init__.md)：`cli.exp` package 的對外匯出面。
- [`cli/exp/__main__.py`](modules/cli/exp/__main__.md)：`python -m ...cli.exp` 的薄啟動層。
- [`cli/exp/mkp_base.py`](modules/cli/exp/mkp_base.md)：以外部 baseline `Pdev` 判斷 `bsma_numba`、`brlsmasca_rl_numba` 與 `bsca_numba` 是否達標。
- [`cli/exp/mkp_base2.py`](modules/cli/exp/mkp_base2.md)：以 projected peers 為基準，比較 `brlsmasca_rl_numba` 是否 strict best 或在 margin 內。
- [`cli/exp/mkp_calibration.py`](modules/cli/exp/mkp_calibration.md)：校準矩陣 evaluator，驗證 transfer function 與 target parameter combo。
- [`cli/exp/mkp_qpso.py`](modules/cli/exp/mkp_qpso.md)：把 QPSO baseline mean 納入 target variant 接受條件。
- [`cli/exp/mkp_random_collect.py`](modules/cli/exp/mkp_random_collect.md)：deterministic repeat 節流 evaluator。
- [`cli/replay/__init__.py`](modules/cli/replay/__init__.md)：`cli.replay` package 邊界。
- [`cli/replay/__main__.py`](modules/cli/replay/__main__.md)：`python -m ...cli.replay` 的薄啟動層。
- [`cli/replay/main.py`](modules/cli/replay/main.md)：seed bank replay 入口，負責還原 solver config 與 run seeds。

### Engine 組裝層

- [`engine/__init__.py`](modules/engine/__init__.md)：engine package 對外匯出面。
- [`engine/assembly.py`](modules/engine/assembly.md)：建構 `SimulationBundle` 與 `Engine.build(...)`。
- [`engine/bank.py`](modules/engine/bank.md)：catalog 掃描、`ProblemBank`、worker shared memory attach。
- [`engine/builders.py`](modules/engine/builders.md)：內建 solver builder map，提供標準 `SolverRegistry` 來源。
- [`engine/repository.py`](modules/engine/repository.md)：problem YAML 載入與 metadata 驗證。
- [`engine/configs.py`](modules/engine/configs.md)：solver config snapshot 與 worker init payload。
- [`engine/models.py`](modules/engine/models.md)：`ExperimentSpec`、`RunTask`、`SolveResult`。

### Problem 契約層

- [`problem/__init__.py`](modules/problem/__init__.md)：problem package 匯出面與 `ProblemModel` 相容別名。
- [`problem/builders.py`](modules/problem/builders.md)：內建 problem type spec 與 `ProblemRegistry` 工廠。
- [`problem/interface.py`](modules/problem/interface.md)：抽象 `Problem` 介面與共用正規化 helper。
- [`problem/registry.py`](modules/problem/registry.md)：problem type registry 與 shm pack/attach 契約。
- [`problem/mkp.py`](modules/problem/mkp.md)：MKP model、YAML loader、shared memory pack/attach。
- [`problem/tsp.py`](modules/problem/tsp.md)：TSP model、permutation/min 契約與 shared memory pack。
- [`problem/yaml.py`](modules/problem/yaml.md)：problem YAML loader 共用欄位/identity 驗證 helper。
- [`problem/kp.py`](modules/problem/kp.md)：0/1 knapsack 題型保留擴充點，未進 runtime builder。
- [`problem/vrp.py`](modules/problem/vrp.md)：vehicle routing 題型保留擴充點，未進 runtime builder。
- [`problem/validation.py`](modules/problem/validation.md)：`ValidationReport` 與 objective/direction 正規化。

### 執行層

- [`simulator/__init__.py`](modules/simulator/__init__.md)：simulator package 邊界。
- [`simulator/core.py`](modules/simulator/core.md)：單 solver 調度器與 `SimulatorResult`。
- [`machine/__init__.py`](modules/machine/__init__.md)：machine package 邊界。
- [`machine/core.py`](modules/machine/core.md)：`Machine`、`MachinePool`、`MachinePoolSession`、process worker 路徑。

### Experiment Collect 層

- [`experiment/__init__.py`](modules/experiment/__init__.md)：experiment package 邊界與對外匯出面。
- [`experiment/config.py`](modules/experiment/config.md)：`exp_cfg.yaml` schema、solver capability 驗證、problem metadata 驗證。
- [`experiment/evaluation.py`](modules/experiment/evaluation.md)：round evaluator 的資料契約。
- [`experiment/experiment.py`](modules/experiment/experiment.md)：collect loop、window scheduler、seed bank 寫出。
- [`experiment/seed_bank.py`](modules/experiment/seed_bank.md)：seed bank 格式、讀寫、查詢。

### 統計與輸出層

- [`tools/__init__.py`](modules/tools/__init__.md)：tools package 對外匯出面。
- [`tools/stat.py`](modules/tools/stat.md)：`ResultEntry`、`SummaryReport` 與統計 helper。
- [`tools/show.py`](modules/tools/show.md)：CSV/JSON 輸出與 summary 落地。
- [`tools/solver_config_loader.py`](modules/tools/solver_config_loader.md)：solver YAML 的底層 schema 驗證與 param-set 展開。

### 演算法支援工具層

- [`tools/continuous_to_binary.py`](modules/tools/continuous_to_binary.md)：Python 側 CTF 名稱、順序與 `ctf_id` 契約。
- [`tools/ctf_numba.py`](modules/tools/ctf_numba.md)：Numba hot-loop 專用的 `ctf_id -> probability` 分派。
- [`tools/mkp_item_eval_experiment.py`](modules/tools/mkp_item_eval_experiment.md)：MKP item-evaluation 變體批次比較工具。
- [`tools/mkp_rc_feature_ablation.py`](modules/tools/mkp_rc_feature_ablation.md)：`brlsmasca_rl_rc_numba` feature ablation 工具。
- [`tools/mkp_score_scaffold.py`](modules/tools/mkp_score_scaffold.md)：score-layer random+repair scaffold。

### Solver 演算法層

- [`solver/registry.py`](modules/solver/registry.md)：solver protocol、builder registry 與 stub solver。
- [`solver/BSMA.py`](modules/solver/BSMA.md)：BSMA 純 Python 基線。
- [`solver/BSMA_numba.py`](modules/solver/BSMA_numba.md)：BSMA Numba 主線。
- [`solver/BSMA_rc_numba.py`](modules/solver/BSMA_rc_numba.md)：BSMA 的 RC / repair / restart 版。
- [`solver/BSCA.py`](modules/solver/BSCA.md)：BSCA 純 Python 基線。
- [`solver/BSCA_numba.py`](modules/solver/BSCA_numba.md)：BSCA Numba 主線。
- [`solver/BSCA_rc_numba.py`](modules/solver/BSCA_rc_numba.md)：BSCA 的 RC / repair / restart 版。
- [`solver/BSCASMA.py`](modules/solver/BSCASMA.md)：混合 SMA/SCA 測試策略基線。
- [`solver/BSCASMA_test_numba.py`](modules/solver/BSCASMA_test_numba.md)：混合測試策略 Numba 版。
- [`solver/BSCASMA_rl_numba.py`](modules/solver/BSCASMA_rl_numba.md)：混合 RL/Q-learning 版。
- [`solver/BSCASMA_rl_rc_numba.py`](modules/solver/BSCASMA_rl_rc_numba.md)：RC、guided binary、local search、archive/path relinking 最完整版本。
- [`solver/__init__.py`](modules/solver/__init__.md)：solver package 標記。

### RNG 與轉換層

- [`rng/__init__.py`](modules/rng/__init__.md)：RNG package 匯出入口。
- [`rng/context.py`](modules/rng/context.md)：seed 派生上下文。
- [`rng/seeding.py`](modules/rng/seeding.md)：stable task seed hash。
- [`rng/factory.py`](modules/rng/factory.md)：`np.random.Generator` factory。
- [`rng/strategy.py`](modules/rng/strategy.md)：seed strategy protocol 與實作。
- [`converter/__init__.py`](modules/converter/__init__.md)：converter package 匯出入口。
- [`converter/register.py`](modules/converter/register.md)：raw parser registry。
- [`converter/converter.py`](modules/converter/converter.md)：raw benchmark 轉 `ProblemModel` / YAML。

### Root / Wiring 層

- [`__init__.py`](modules/__init__.md)：套件根層 re-export 與 lazy `main` 入口。
- [`pytest_plugin.py`](modules/pytest_plugin.md)：從子目錄執行 pytest 時的收集修正器。

### Tests 自動化驗證層

- CLI / Experiment：
  [`tests/test_app.py`](modules/tests/test_app.md)、[`tests/test_cli_exp.py`](modules/tests/test_cli_exp.md)、[`tests/test_exp_config.py`](modules/tests/test_exp_config.md)、[`tests/test_exp_evaluation.py`](modules/tests/test_exp_evaluation.md)、[`tests/test_experiment_run.py`](modules/tests/test_experiment_run.md)、[`tests/test_seed_bank_replay.py`](modules/tests/test_seed_bank_replay.md)
- Engine / Simulator / Machine / Output：
  [`tests/test_engine.py`](modules/tests/test_engine.md)、[`tests/test_machine.py`](modules/tests/test_machine.md)、[`tests/test_simulator.py`](modules/tests/test_simulator.md)、[`tests/test_simulator_batch.py`](modules/tests/test_simulator_batch.md)、[`tests/test_stat.py`](modules/tests/test_stat.md)
- Problem / Contracts / RNG / Config：
  [`tests/test_contracts.py`](modules/tests/test_contracts.md)、[`tests/test_problem_registry.py`](modules/tests/test_problem_registry.md)、[`tests/test_problem_repository.py`](modules/tests/test_problem_repository.md)、[`tests/test_tsp_problem_type.py`](modules/tests/test_tsp_problem_type.md)、[`tests/test_validator.py`](modules/tests/test_validator.md)、[`tests/test_rng.py`](modules/tests/test_rng.md)、[`tests/test_solver_config_loader.py`](modules/tests/test_solver_config_loader.md)、[`tests/test_solver_registry.py`](modules/tests/test_solver_registry.md)
- Solver regression：
  [`tests/test_bsma_solver.py`](modules/tests/test_bsma_solver.md)、[`tests/test_bsca2_solver.py`](modules/tests/test_bsca2_solver.md)、[`tests/test_bscasma_solver.py`](modules/tests/test_bscasma_solver.md)、[`tests/test_rc_numba_solvers.py`](modules/tests/test_rc_numba_solvers.md)、[`tests/test_continuous_to_binary.py`](modules/tests/test_continuous_to_binary.md)
- Research helper / scaffold：
  [`tests/test_converter_registry.py`](modules/tests/test_converter_registry.md)、[`tests/test_mkp_item_eval_experiment.py`](modules/tests/test_mkp_item_eval_experiment.md)、[`tests/test_mkp_score_scaffold.py`](modules/tests/test_mkp_score_scaffold.md)、[`tests/test_stage1_validation.py`](modules/tests/test_stage1_validation.md)

### Valid 研究驗證層

- [`valid/__init__.py`](modules/valid/__init__.md)：`mkp.valid` package 邊界。
- [`valid/bsma_equivalence.py`](modules/valid/bsma_equivalence.md)：舊版 BSMA 與現行 core 的嚴格等價驗證。
- [`valid/bsma_equivalence_batch.py`](modules/valid/bsma_equivalence_batch.md)：WEISH 題庫批次等價驗證。
- [`valid/bsma_population_trace.py`](modules/valid/bsma_population_trace.md)：BSMA old/new population trace 比對。
- [`valid/bsca_population_trace.py`](modules/valid/bsca_population_trace.md)：BSCA old/new population trace 比對。
- [`valid/bscasma_population_trace.py`](modules/valid/bscasma_population_trace.md)：BSCASMA old/new population trace 與 crash 行為比對。
- [`valid/bsma_numba_gk_benchmark.py`](modules/valid/bsma_numba_gk_benchmark.md)：BSMA vs BSMA_numba GK benchmark。
- [`valid/stage1_validation.py`](modules/valid/stage1_validation.md)：legacy script 與新 CLI 的 stage-1 refactor 驗證。

## 目錄級摘要

這裡保留全 repo 的目錄級摘要，用來定位尚未進入 Wave 1 深寫的區塊。

| Directory | Python Files | Lines | Responsibility |
|---|---:|---:|---|
| `.` | 2 | 109 | 套件根或輔助入口。 |
| `cli` | 20 | 2389 | CLI 入口與命令列編排。 |
| `converter` | 3 | 176 | 題庫 parser registry 與 YAML 轉換工具。 |
| `engine` | 7 | 753 | repository、catalog、problem bank、solver config、bundle 組裝。 |
| `experiment` | 5 | 1441 | collect 實驗、evaluator 契約、seed bank。 |
| `machine` | 2 | 536 | solver variant 執行單位與 process pool。 |
| `old` | 23 | 3046 | 歷史演算法與舊實驗腳本。 |
| `problem` | 10 | 790 | problem model、validation、registry、shared memory pack。 |
| `rng` | 5 | 211 | seed 派生與 RNG factory。 |
| `simulator` | 2 | 190 | 單 solver 調度器。 |
| `solver` | 12 | 8408 | 求解器與演算法核心。 |
| `tests` | 28 | 8636 | pytest 測試。 |
| `tools` | 9 | 2163 | 統計、輸出、solver config loader 與其他輔助工具。 |
| `valid` | 8 | 3406 | 等價性、trace、benchmark 驗證腳本。 |

## 與 API 參考的關係

- `04_module_guide.md`：回答「這個模組在系統中負責什麼、跟誰互動、資源怎麼流」。
- `05_api_reference.md`：回答「有哪些 class/function/helper」。
- `note/plan/modules/*.md`：回答「這個 `.py` 模組內部的資料契約、控制流、失敗路徑與閱讀順序」。

目前非 `old/` source modules 已全部升級到模組級文件；`old/` 明確視為歷史參考區，暫不納入短期補強目標。dashboard 的主要缺口已轉成函式級去模板化與治理自動檢查。
