# Experiment And Evaluation

## Purpose

`experiment/` 支援研究流程中「跑到符合條件的 seed/round 為止」的實驗搜尋。它不是單純批次跑完所有 repeats，而是把每個 repeat 視為 candidate round，先做 projected summary，再交給 evaluator 判斷是否值得正式收錄。

這條鏈路的核心目標有三個：

- 把 solver family 的探索條件寫成可重播的程式化規則。
- 在 collect 過程中就過濾掉不符研究假設的 round。
- 把最後真正被接受的 run seeds 與 solver config 一起落地，供 `cli.replay` 重播。

## 責任邊界

- `experiment.config`：
  解析 `cli/exp/exp_cfg.yaml`，檢查 problem/solver metadata 與 evaluator 基本配置。
- `experiment.experiment`：
  管 collect loop、window scheduling、candidate/projected/collected result 的轉換，以及 output/seed bank 寫出。
- `experiment.evaluation`：
  定義 evaluator 的資料契約。
- `cli/exp/*.py` evaluator 模組：
  只做判斷，不建立 task、不操作 simulator、不寫檔。
- `experiment.seed_bank`：
  保存可重播資訊。

這個分層很重要。若 evaluator 開始操作 machine、改寫 collect 狀態或讀寫 output，就會破壞 `cli.exp` 目前的可重播設計。

## Config Model

`experiment.config` 會把 `cli/exp/exp_cfg.yaml` 解析成以下執行期資料模型：

- `ExperimentConfig`：整體 experiment name、collects、repeat、dataset settings、worker count。
- `SolverSelection`：solver id 與 param indices，決定 collect 時要保留哪些 variants。
- `DatasetSetting`：dataset experiment id、dataset、problem type、problem settings。
- `ProblemSetting`：problem id 與 evaluations。
- `EvaluationSpec` / `EvaluationBaseline`：evaluator 名稱、baseline `mean` / `pdev` 與附帶 metadata。

解析階段會先攔掉：

- YAML key 遺漏或多餘欄位
- `collects` / `repeat` / worker 等非正整數欄位
- solver param index 越界
- dataset / problem id 不存在
- solver capability 與 problem type 不匹配

## Collection Flow

1. `build(...)` 載入 `ExperimentConfig`。
2. `Experiment.run(...)` 驗證所有 configured evaluator 都已註冊。
3. 清空並重建 `output/<experiment_name>/`。
4. 逐一處理 `DatasetSetting`：
   - 建立 `ExperimentSpec`
   - 透過 `Engine.build(...)` 載入 repository、bank、machines、bundle
   - 拆成多個 single-solver `Simulator`
5. `_selected_machines(...)` 依 `cfg.solver_variants` 只保留要 collect 的 variants。
6. `_run_problem(...)` 用 worker count 與 machine 數推導 window size，逐窗展開 `RunTask`。
7. `MachinePoolSession.run_tasks(...)` 執行當前窗口的候選 runs。
8. `_result_for_repeat(...)` 先切出單一 repeat 的 candidate result，再和既有收集結果合成 projected result。
9. `_variant_summaries(...)` 為每個 projected variant 產生 `VariantSummary`。
10. `_evaluate_candidate_round(...)` 依 problem setting 的 evaluator 清單逐一判斷。
11. 全部 `passed` 才：
    - append round rows 到 collected result
    - 記錄 `repeat_index`
    - 驗證並記錄 shared run seed
12. 每個 problem collect 完成後，寫 variant result、summary、`seed_bank.json`、最終 `summary.json`。

## 資料契約鏈

實驗層最重要的不是函式名稱，而是中間資料是否能穩定銜接：

1. `exp_cfg.yaml`
2. `ExperimentConfig`
3. `ExperimentSpec`
4. `SimulationBundle`
5. `RunTask`
6. `SimulatorResult`
7. `VariantSummary`
8. `RoundEvalInput`
9. `RoundEvalDecision`
10. `SummaryReport`
11. `SeedBank`

其中最容易出問題的是第 `7 -> 9` 段。evaluator 並不看原始 run rows，而是看 `VariantSummary` 與 baseline，因此 summary 聚合欄位、excluded counts、param metadata 變更時，最先需要回頭檢查的是 evaluator。

## Evaluator Registry

`experiment.experiment._EVALUATORS` 是 evaluator registry。`cli/exp/main.py` 會在啟動時 import evaluator 模組並逐一 `register(...)`。真正的 collect loop 只依 evaluator 名稱 lookup callable，不直接 import evaluator 模組。

這個設計代表兩件事：

- `exp_cfg.yaml` 與 evaluator 的橋接點是字串名稱。
- 漏註冊 evaluator 屬於啟動期錯誤，不會等到 collect 中途才發現。

## Evaluator Family

目前 `cli/exp` 的 evaluator 可分成四個家族：

### 1. Baseline `Pdev` 家族

- `cli/exp/mkp_base.py`
- `cli/exp/mkp_base2.py`

用途：

- 把 projected variants 與外部 baseline 或同輪 projected peers 比較。
- 接受條件通常是「strict best」或「在 margin 內」。

核心契約：

- projected summary 必須全 valid / 全 feasible / 無 excluded counts。
- `overall.pdev` 必須存在。

### 2. Baseline `Mean` 家族

- `cli/exp/mkp_qpso.py`

用途：

- 把外部 QPSO baseline mean 當作最低門檻，要求指定 target variant 的 `avg_objective` 至少達標。

核心契約：

- baseline 中必須存在 `name == "qpso"` 的 mean。
- target variant 固定為 `brlsmasca_rl_rc_numba/param_20`。

### 3. Calibration Matrix 家族

- `cli/exp/mkp_calibration.py`

用途：

- 把所有 variants 視為 `bsma` / `bsca` / `bscasma` 的校準矩陣。
- 驗證 transfer function 是否以 `abs_pow_16` 為優勢。
- 驗證 target parameter combo 是否是 strict best，或至少落在允許 margin。
- 在特定 problem 上再加 lead / lag 約束。

核心契約：

- projected variants 必須形成完整 `45` 組 calibration combo set。
- `params` 中的 `ctf`、`z`、`a` 不能缺。
- evaluator 看的是 family-level ranking，不是單一 solver 的局部表現。

### 4. Deterministic Sampling 家族

- `cli/exp/mkp_random_collect.py`

用途：

- 不看 solver 表現，只以 deterministic hash 節流 repeat 收集頻率。

核心契約：

- 相同 `dataset/problem_id/repeat_index` 必須得到穩定結果。
- 它只控制收樣密度，不保證收進來的 round 有研究價值，因此通常要和其他 evaluator 並用。

## Failure Path

`cli.exp` 的主要失敗點有四類：

- 啟動前：
  - evaluator 未註冊
  - config schema 錯誤
  - solver/problem metadata 不一致
- collect 中：
  - output 目錄重建失敗
  - bundle / simulator build 失敗
  - repeat 上限內收不滿 `collects`
  - 同一 repeat 的 shared run seed 不一致
- evaluator 中：
  - baseline 缺失
  - projected summary 不可比較
  - calibration combo set 不完整
  - evaluator 被套用到錯誤題目集合
- 收尾：
  - summary / seed bank 寫出失敗

目前文件已把這些失敗點寫到模組級，但 tests/valid 還沒補齊，所以「如何用驗證腳本確認 evaluator 假設沒壞掉」仍是 dashboard 缺口。

## Seed Bank

`experiment.seed_bank` 負責輸出可重播資料：

- source：experiment name、base seed、seed strategy。
- variants：solver id、param set index、config snapshot。
- problems：dataset、problem type、problem id、run seeds。

`cli.replay` 會直接讀 seed bank 中的 run seeds 建立 task，因此 seed bank 不只是附帶檔案，而是 collect 流程的正式交付物。evaluator 如何篩選 round，會直接決定 seed bank 中有哪些 repeat 能被後續研究拿來重播。
