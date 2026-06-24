# Python 模組 Inventory

此檔由靜態 AST 掃描產生，供 `05_api_reference.md` 與 coverage checklist 對照。

| Path | Lines | Classes | Functions/Methods | Role | Module Doc |
|---|---:|---:|---:|---|---|
| `__init__.py` | 80 | 0 | 1 | 套件根或輔助入口。 | MKP simulation system package. |
| `cli/__init__.py` | 1 | 0 | 0 | 套件根或輔助入口。 | 命令列子套件（`mkp.cli.run` 為模擬批次主入口）。 |
| `cli/convert/__init__.py` | 25 | 0 | 0 | 原始題庫轉 YAML 的 CLI。 | 題庫轉換 CLI：解析命令列並選擇轉換函數。 |
| `cli/convert/__main__.py` | 8 | 0 | 0 | 原始題庫轉 YAML 的 CLI。 | 允許以 `python -m mkp.cli.convert` 執行題庫轉換。 |
| `cli/convert/main.py` | 61 | 0 | 3 | 原始題庫轉 YAML 的 CLI。 |  |
| `cli/convert/register.py` | 162 | 0 | 11 | 原始題庫轉 YAML 的 CLI。 |  |
| `cli/exp/__init__.py` | 41 | 0 | 0 | 實驗搜尋 CLI 與 evaluator 註冊。 | Experiment CLI entrypoint and bundled evaluators. |
| `cli/exp/__main__.py` | 7 | 0 | 0 | 實驗搜尋 CLI 與 evaluator 註冊。 |  |
| `cli/exp/main.py` | 72 | 0 | 1 | 實驗搜尋 CLI 與 evaluator 註冊。 |  |
| `cli/exp/mkp_base.py` | 211 | 0 | 8 | 實驗搜尋 CLI 與 evaluator 註冊。 |  |
| `cli/exp/mkp_base2.py` | 185 | 0 | 6 | 實驗搜尋 CLI 與 evaluator 註冊。 |  |
| `cli/exp/mkp_calibration.py` | 1030 | 0 | 33 | 實驗搜尋 CLI 與 evaluator 註冊。 |  |
| `cli/exp/mkp_qpso.py` | 101 | 0 | 5 | 實驗搜尋 CLI 與 evaluator 註冊。 |  |
| `cli/exp/mkp_random_collect.py` | 64 | 0 | 4 | 實驗搜尋 CLI 與 evaluator 註冊。 |  |
| `cli/replay/__init__.py` | 7 | 0 | 0 | 依 seed_bank 重播已接受 run。 | Seed bank replay CLI. |
| `cli/replay/__main__.py` | 8 | 0 | 0 | 依 seed_bank 重播已接受 run。 | 允許以 `python -m mkp.cli.replay` 重現 seed_bank.json。 |
| `cli/replay/main.py` | 166 | 0 | 5 | 依 seed_bank 重播已接受 run。 |  |
| `cli/run/__init__.py` | 21 | 0 | 0 | CLI run 入口與單次模擬編排。 | 模擬批次主入口：CLI 解析、驗證與 `executeSimulator` 編排。 |
| `cli/run/__main__.py` | 8 | 0 | 0 | CLI run 入口與單次模擬編排。 | 允許以 `python -m mkp.cli.run` 執行模擬批次。 |
| `cli/run/main.py` | 33 | 0 | 1 | CLI run 入口與單次模擬編排。 |  |
| `cli/run/support.py` | 178 | 0 | 8 | CLI run 入口與單次模擬編排。 | CLI 之後的編排：驗證參數、呼叫 `engine.build`、建立 `Simulator` 與執行批次、由 show 模組輸出、釋放 SHM。 |
| `converter/__init__.py` | 26 | 0 | 0 | 題庫 parser registry 與 YAML 轉換工具。 |  |
| `converter/converter.py` | 114 | 0 | 7 | 題庫 parser registry 與 YAML 轉換工具。 | 由 MKP 題庫原始檔建立 ProblemModel / 對應 YAML。 |
| `converter/register.py` | 36 | 0 | 4 | 題庫 parser registry 與 YAML 轉換工具。 |  |
| `engine/__init__.py` | 13 | 0 | 0 | 組裝 repository、registry、problem bank、solver config 與 simulator。 | Engine 子系統：組裝題庫掃描、`ProblemBank` 與 `SimulationBundle`。 |
| `engine/assembly.py` | 170 | 2 | 6 | 組裝 repository、registry、problem bank、solver config 與 simulator。 | SimulationBundle、`build` 與 `Engine` 組裝介面。 |
| `engine/bank.py` | 229 | 4 | 15 | 組裝 repository、registry、problem bank、solver config 與 simulator。 | 題庫掃描、Catalog、CatalogSummary，以及以 shared_memory 共用的 ProblemBank。 |
| `engine/builders.py` | 32 | 0 | 1 | 組裝 repository、registry、problem bank、solver config 與 simulator。 | 內建求解器建構子（可由 `build(..., solver_builders=...)` 覆寫）。 |
| `engine/configs.py` | 88 | 1 | 7 | 組裝 repository、registry、problem bank、solver config 與 simulator。 | 於 engine 階段預載 solver YAML，執行期僅從記憶體讀取（與題庫預載對齊）。 |
| `engine/models.py` | 120 | 3 | 3 | 組裝 repository、registry、problem bank、solver config 與 simulator。 |  |
| `engine/repository.py` | 101 | 1 | 5 | 組裝 repository、registry、problem bank、solver config 與 simulator。 |  |
| `experiment/__init__.py` | 61 | 0 | 0 | 多 solver/多參數實驗搜尋與收集。 | Experiment domain package: streaming round collection execution. |
| `experiment/config.py` | 528 | 6 | 35 | 多 solver/多參數實驗搜尋與收集。 |  |
| `experiment/evaluation.py` | 78 | 3 | 3 | 多 solver/多參數實驗搜尋與收集。 |  |
| `experiment/experiment.py` | 595 | 4 | 26 | 多 solver/多參數實驗搜尋與收集。 |  |
| `experiment/seed_bank.py` | 179 | 0 | 10 | 多 solver/多參數實驗搜尋與收集。 |  |
| `machine/__init__.py` | 5 | 0 | 0 | solver variant 執行單位與 process pool。 | Machine layer: one solver parameter variant executes its own run tasks. |
| `machine/core.py` | 531 | 5 | 31 | solver variant 執行單位與 process pool。 |  |
| `old/BSCA.py` | 271 | 2 | 12 | 歷史演算法與舊實驗腳本。 |  |
| `old/BSCASMA.py` | 774 | 2 | 32 | 歷史演算法與舊實驗腳本。 |  |
| `old/BSMA.py` | 176 | 1 | 6 | 歷史演算法與舊實驗腳本。 |  |
| `old/GUROBI/gb3.py` | 76 | 0 | 1 | 歷史演算法與舊實驗腳本。 |  |
| `old/GUROBI/gb3_limit.py` | 74 | 0 | 1 | 歷史演算法與舊實驗腳本。 |  |
| `old/GUROBI/gb_relaxation.py` | 153 | 0 | 3 | 歷史演算法與舊實驗腳本。 |  |
| `old/GUROBI/main_cb.py` | 80 | 1 | 3 | 歷史演算法與舊實驗腳本。 |  |
| `old/GUROBI/main_gk.py` | 111 | 1 | 3 | 歷史演算法與舊實驗腳本。 |  |
| `old/GUROBI/main_hp.py` | 74 | 1 | 3 | 歷史演算法與舊實驗腳本。 |  |
| `old/GUROBI/main_pb.py` | 75 | 1 | 3 | 歷史演算法與舊實驗腳本。 |  |
| `old/GUROBI/main_sent.py` | 76 | 1 | 3 | 歷史演算法與舊實驗腳本。 |  |
| `old/GUROBI/main_weing.py` | 106 | 1 | 3 | 歷史演算法與舊實驗腳本。 |  |
| `old/GUROBI/main_weish.py` | 106 | 1 | 3 | 歷史演算法與舊實驗腳本。 |  |
| `old/GUROBI/scipy.py` | 19 | 0 | 1 | 歷史演算法與舊實驗腳本。 |  |
| `old/main1cb.py` | 100 | 1 | 3 | 歷史演算法與舊實驗腳本。 |  |
| `old/main1gk.py` | 102 | 1 | 3 | 歷史演算法與舊實驗腳本。 |  |
| `old/main1hp.py` | 100 | 1 | 3 | 歷史演算法與舊實驗腳本。 |  |
| `old/main1pb.py` | 100 | 1 | 3 | 歷史演算法與舊實驗腳本。 |  |
| `old/main1pet.py` | 123 | 1 | 3 | 歷史演算法與舊實驗腳本。 |  |
| `old/main1sent.py` | 110 | 1 | 4 | 歷史演算法與舊實驗腳本。 |  |
| `old/main1weing.py` | 99 | 1 | 3 | 歷史演算法與舊實驗腳本。 |  |
| `old/main1weish.py` | 97 | 1 | 3 | 歷史演算法與舊實驗腳本。 |  |
| `old/transform.py` | 44 | 0 | 0 | 歷史演算法與舊實驗腳本。 |  |
| `problem/__init__.py` | 28 | 0 | 0 | 優化問題資料模型、驗證與 shared-memory pack。 | Optimization problem definitions and registration helpers. |
| `problem/builders.py` | 22 | 0 | 2 | 優化問題資料模型、驗證與 shared-memory pack。 |  |
| `problem/interface.py` | 91 | 1 | 7 | 優化問題資料模型、驗證與 shared-memory pack。 |  |
| `problem/kp.py` | 5 | 0 | 0 | 優化問題資料模型、驗證與 shared-memory pack。 | Extension point for a future 0/1 knapsack problem definition. |
| `problem/mkp.py` | 182 | 2 | 8 | 優化問題資料模型、驗證與 shared-memory pack。 |  |
| `problem/registry.py` | 80 | 3 | 7 | 優化問題資料模型、驗證與 shared-memory pack。 |  |
| `problem/tsp.py` | 146 | 2 | 8 | 優化問題資料模型、驗證與 shared-memory pack。 |  |
| `problem/validation.py` | 202 | 1 | 13 | 優化問題資料模型、驗證與 shared-memory pack。 |  |
| `problem/vrp.py` | 5 | 0 | 0 | 優化問題資料模型、驗證與 shared-memory pack。 | Extension point for a future vehicle routing problem definition. |
| `problem/yaml.py` | 29 | 0 | 2 | 優化問題資料模型、驗證與 shared-memory pack。 |  |
| `pytest_plugin.py` | 29 | 0 | 1 | 套件根或輔助入口。 | pytest 插件：從專案子目錄啟動時，自動補上 <rootdir>/tests 作為收集路徑。 |
| `rng/__init__.py` | 12 | 0 | 0 | seed 派生與 RNG factory。 |  |
| `rng/context.py` | 23 | 1 | 1 | seed 派生與 RNG factory。 |  |
| `rng/factory.py` | 12 | 0 | 1 | seed 派生與 RNG factory。 |  |
| `rng/seeding.py` | 37 | 0 | 2 | seed 派生與 RNG factory。 |  |
| `rng/strategy.py` | 127 | 3 | 7 | seed 派生與 RNG factory。 |  |
| `simulator/__init__.py` | 5 | 0 | 0 | 批次模擬調度器。 | 實驗編排與批次執行：`Simulator` 整合 ProblemBank、Registry、驗證；輸出由 stat 模組接手。 |
| `simulator/core.py` | 185 | 2 | 16 | 批次模擬調度器。 |  |
| `solver/BSCA.py` | 231 | 2 | 7 | 求解器與演算法核心。 |  |
| `solver/BSCASMA.py` | 415 | 2 | 15 | 求解器與演算法核心。 |  |
| `solver/BSCASMA_rl_numba.py` | 895 | 2 | 27 | 求解器與演算法核心。 | BRLSMASCA RL/Q-learning Numba solver. |
| `solver/BSCASMA_rl_rc_numba.py` | 3660 | 2 | 80 | 求解器與演算法核心。 | BRLSMASCA RL/Q-learning Numba solver with LP reduced-cost item evaluation. |
| `solver/BSCASMA_test_numba.py` | 667 | 2 | 20 | 求解器與演算法核心。 | BRLSMASCA test-policy Numba solver. |
| `solver/BSCA_numba.py` | 391 | 2 | 10 | 求解器與演算法核心。 | BSCA 的 Numba 加速版 v2：與 ``BSCACore`` 主迴圈數值行為對齊。 |
| `solver/BSCA_rc_numba.py` | 600 | 2 | 12 | 求解器與演算法核心。 | BSCA Numba variant with LP reduced-cost item evaluation and Repair 2.0. |
| `solver/BSMA.py` | 309 | 2 | 9 | 求解器與演算法核心。 |  |
| `solver/BSMA_numba.py` | 513 | 2 | 14 | 求解器與演算法核心。 | BSMA 的 Numba 加速版：與 [solver/BSMA.py](BSMA.py) 的 ``BSMACore`` 主迴圈語意對齊。 |
| `solver/BSMA_rc_numba.py` | 652 | 2 | 13 | 求解器與演算法核心。 | BSMA Numba variant with LP reduced-cost item evaluation and Repair 2.0. |
| `solver/__init__.py` | 1 | 0 | 0 | 求解器與演算法核心。 | 演算法實作與註冊表。 |
| `solver/registry.py` | 74 | 3 | 6 | 求解器與演算法核心。 |  |
| `tests/test_app.py` | 321 | 0 | 12 | pytest 測試。 |  |
| `tests/test_bsca2_solver.py` | 200 | 0 | 12 | pytest 測試。 |  |
| `tests/test_bscasma_solver.py` | 1379 | 0 | 44 | pytest 測試。 |  |
| `tests/test_bsma_solver.py` | 164 | 0 | 12 | pytest 測試。 |  |
| `tests/test_cli_exp.py` | 61 | 1 | 4 | pytest 測試。 |  |
| `tests/test_continuous_to_binary.py` | 40 | 0 | 4 | pytest 測試。 |  |
| `tests/test_contracts.py` | 200 | 1 | 12 | pytest 測試。 |  |
| `tests/test_converter_registry.py` | 220 | 0 | 14 | pytest 測試。 |  |
| `tests/test_engine.py` | 308 | 0 | 11 | pytest 測試。 |  |
| `tests/test_exp_config.py` | 429 | 0 | 17 | pytest 測試。 |  |
| `tests/test_exp_evaluation.py` | 1123 | 0 | 42 | pytest 測試。 |  |
| `tests/test_experiment_run.py` | 371 | 0 | 17 | pytest 測試。 |  |
| `tests/test_machine.py` | 323 | 1 | 13 | pytest 測試。 |  |
| `tests/test_mkp_item_eval_experiment.py` | 77 | 0 | 4 | pytest 測試。 |  |
| `tests/test_mkp_score_scaffold.py` | 92 | 0 | 5 | pytest 測試。 |  |
| `tests/test_problem_registry.py` | 130 | 0 | 6 | pytest 測試。 |  |
| `tests/test_problem_repository.py` | 293 | 0 | 13 | pytest 測試。 |  |
| `tests/test_rc_numba_solvers.py` | 262 | 0 | 10 | pytest 測試。 |  |
| `tests/test_rng.py` | 122 | 0 | 6 | pytest 測試。 |  |
| `tests/test_seed_bank_replay.py` | 163 | 0 | 8 | pytest 測試。 |  |
| `tests/test_simulator.py` | 252 | 1 | 11 | pytest 測試。 |  |
| `tests/test_simulator_batch.py` | 794 | 1 | 28 | pytest 測試。 |  |
| `tests/test_solver_config_loader.py` | 374 | 0 | 13 | pytest 測試。 |  |
| `tests/test_solver_registry.py` | 71 | 0 | 5 | pytest 測試。 |  |
| `tests/test_stage1_validation.py` | 66 | 2 | 5 | pytest 測試。 |  |
| `tests/test_stat.py` | 563 | 0 | 18 | pytest 測試。 |  |
| `tests/test_tsp_problem_type.py` | 125 | 0 | 5 | pytest 測試。 |  |
| `tests/test_validator.py` | 113 | 0 | 9 | pytest 測試。 |  |
| `tools/__init__.py` | 1 | 0 | 0 | 統計、輸出、實驗輔助與轉換函數工具。 | 工具模組：結果統計、結果輸出與 solver YAML 載入。 |
| `tools/continuous_to_binary.py` | 130 | 0 | 15 | 統計、輸出、實驗輔助與轉換函數工具。 | 連續基因值 → 與 Uniform(0,1) 比較用之標量（CTF：continuous-to-flip）。 |
| `tools/ctf_numba.py` | 57 | 0 | 1 | 統計、輸出、實驗輔助與轉換函數工具。 | 與 continuous_to_binary 對應之 nopython scalar CTF（供 Numba 主迴圈內整數分流）。 |
| `tools/mkp_item_eval_experiment.py` | 576 | 1 | 17 | 統計、輸出、實驗輔助與轉換函數工具。 |  |
| `tools/mkp_rc_feature_ablation.py` | 267 | 1 | 9 | 統計、輸出、實驗輔助與轉換函數工具。 |  |
| `tools/mkp_score_scaffold.py` | 410 | 1 | 10 | 統計、輸出、實驗輔助與轉換函數工具。 |  |
| `tools/show.py` | 223 | 0 | 12 | 統計、輸出、實驗輔助與轉換函數工具。 | 結果輸出模組：將已整理的 run entries 與摘要統計寫入檔案。 |
| `tools/solver_config_loader.py` | 126 | 1 | 6 | 統計、輸出、實驗輔助與轉換函數工具。 |  |
| `tools/stat.py` | 373 | 7 | 15 | 統計、輸出、實驗輔助與轉換函數工具。 | 統計彙整模組：將模擬結果整理為標準化資料與摘要統計。 |
| `valid/__init__.py` | 1 | 0 | 0 | 驗證/等價性/benchmark 輔助腳本。 | 舊版對齊、等價驗證與階段一煙霧測試腳本。 |
| `valid/bsca_population_trace.py` | 702 | 7 | 25 | 驗證/等價性/benchmark 輔助腳本。 |  |
| `valid/bscasma_population_trace.py` | 847 | 7 | 27 | 驗證/等價性/benchmark 輔助腳本。 |  |
| `valid/bsma_equivalence.py` | 540 | 2 | 22 | 驗證/等價性/benchmark 輔助腳本。 |  |
| `valid/bsma_equivalence_batch.py` | 160 | 0 | 4 | 驗證/等價性/benchmark 輔助腳本。 | WEISH 全題庫批次：舊版 BSMA vs BSMACore 串流等價驗證。 |
| `valid/bsma_numba_gk_benchmark.py` | 133 | 0 | 5 | 驗證/等價性/benchmark 輔助腳本。 | 比對 ``bsma`` 與 ``bsma_numba`` 在 GK 前兩題、repeat=1 / 20 的結果與總耗時。 |
| `valid/bsma_population_trace.py` | 733 | 7 | 25 | 驗證/等價性/benchmark 輔助腳本。 |  |
| `valid/stage1_validation.py` | 290 | 2 | 9 | 驗證/等價性/benchmark 輔助腳本。 |  |
