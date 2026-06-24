# `experiment/experiment.py`

## 模組責任

`experiment/experiment.py` 是 `cli.exp` 的主流程。它負責多 solver variant、多 dataset setting、多 problem 的 collect loop，並以 evaluator 決定哪些 repeat 被正式收集，最後寫 summary 與 seed bank。

## 公開入口/主要類型

- `ProblemCollectionReport`
- `ExperimentReport`
- `Experiment`
- `register(...)`
- `build(...)`
- `executeExperiment(...)`

## 主要資料結構與資料契約

- `Experiment` 持有 `ExperimentConfig` 與兩個執行期累積區：
  - `_seed_bank_problem_entries`
  - `_seed_bank_variants`
- `ProblemCollectionReport` 描述單一 problem collect 結果，包括收集數、嘗試到第幾個 repeat、實際收下的 repeat indices 與 seeds。
- `ExperimentReport` 是整個 `cli.exp` 的最終摘要。
- evaluator 註冊表 `_EVALUATORS` 以字串名稱綁定 callable，這是 experiment config 與執行器之間的橋接。

## 資料流與控制流

1. `build(...)` 先呼叫 `load_config(...)` 建出 `ExperimentConfig`。
2. `Experiment.run(...)` 先檢查所有 configured evaluator 都已註冊。
3. 建立 experiment output directory；若同名目錄已存在，會先整棵刪除再重建。
4. 對每個 `DatasetSetting` 呼叫 `_build_dataset_simulators(...)`：
   - 建立 dataset 專屬 `ExperimentSpec`
   - 用 `Engine.build(...)` 建 bundle
   - 拆成多個 single-solver `Simulator`
5. `_run_dataset(...)` 用 `_selected_machines(...)` 選出 config 指定的 solver variants，並建立 `MachinePoolSession`。
6. `_run_problem(...)` 以 repeat window 前進：
   - `_window_tasks(...)` 只展開當前 window 的 tasks
   - `session.run_tasks(...)` 執行所有 variant 的這一輪候選任務
   - `_result_for_repeat(...)` 切出單一 repeat 的 `SimulatorResult`
   - `_evaluate_candidate_round(...)` 把 projected summary 丟給所有 evaluator
   - 若全部通過，才把 rows 累進 collected 結果
7. problem collect 完成後，`write_simulator_result(...)` 寫每個 variant 的 runs/summary。
8. `_record_seed_bank_problem(...)` 寫入可重播資訊。
9. 所有 dataset 都完成後，輸出 `summary.json` 與 `seed_bank.json`。

## 失敗路徑與例外條件

- evaluator 未註冊時，`Experiment.run(...)` 一開始就會失敗。
- output 目錄刪除/建立若出錯，整個實驗會中止。
- 某個 dataset 或 problem build bundle 失敗時，不會進入 collect loop。
- `_run_problem(...)` 若在 `repeat` 上限內仍收不滿 `collects`，會丟 `RuntimeError`，表示 evaluator 條件過嚴或 repeat 上限不足。
- `_shared_round_seed(...)` 若同一 repeat 的多 variant 任務 seed 不一致，會丟 `RuntimeError`；這是 seed strategy 或 task 建構違反資料契約的訊號。

## 副作用與資源生命週期

- `Experiment.run(...)` 會刪除既有 `output/<experiment_name>` 目錄，這是本模組最大的檔案系統副作用。
- 每個 dataset 建出的一組 simulators 共享同一份 `ProblemBank`；`finally` 只關閉 `simulators[0]`，等同關閉該 bundle 的 shared memory。
- `MachinePoolSession` 在 dataset collect 期間重用同一個 process pool，減少多輪 window 的 spawn 成本；dataset 結束時透過 context manager 自動 shutdown。
- `summary.json` 與 `seed_bank.json` 是 collect 流程的正式輸出物，不是暫存檔。

## 與其他模組的關係

- 上游：`cli.exp.main` 與 evaluator 註冊模組。
- 依賴：`experiment.config`、`experiment.evaluation`、`experiment.seed_bank`、`engine.assembly`、`machine.core`、`tools.show`、`tools.stat`。
- 下游：`cli.replay` 消費 seed bank；人類讀者或分析工具消費 summary 與 variant output。

## 核心函式與 helper 說明

### `Experiment.run(...)`

- 目的：執行整個 collect workflow，並輸出 `summary.json` 與 `seed_bank.json`。
- 控制流：
  1. 驗 evaluator registry
  2. 重建 experiment output root
  3. 初始化 `_CollectionProgress`
  4. 逐 `DatasetSetting` 建 simulators 並執行 `_run_dataset(...)`
  5. 關閉 dataset bundle 的 shared memory
  6. 寫最終 report 與 seed bank
- 最大副作用：若 `output/<experiment_name>` 已存在，會整棵刪掉重建。
- 修改風險：這是少數明確會 destructive overwrite 的正式入口，不能把寫檔策略改成增量而不同步更新 replay/測試預期。

### `Experiment._build_dataset_simulators(...)`

- 目的：把單一 `DatasetSetting` 轉成 dataset 專屬的 multi-solver simulators。
- 關鍵點：
  - `ExperimentSpec.experiment_name` 會拼上 `dataset_setting.experiment_id`
  - `base_seed` 固定使用 `EXP_BASE_SEED`
  - seed strategy 固定是 `DerivedPerProblemSeedStrategy()`
- 架構角色：這裡把 collect 設定轉回一般 runtime bundle，讓 `cli.exp` 不需要自己處理 problem bank 或 solver config 組裝細節。

### `Experiment._run_dataset(...)`

- 目的：在一個 dataset setting 內，對每個 problem 啟動 collect。
- 重要設計：先用 `_selected_machines(...)` 固定 solver variants，再建立一個可重用的 `MachinePoolSession`，供同 dataset 下所有 problems 共用。

### `Experiment._run_problem(...)`

- 目的：對單一 problem 執行 windowed collect，直到收滿 `cfg.collects` 或耗盡 `cfg.repeat`。
- 控制流：
  1. 初始化各 variant 的累積 rows
  2. 依 `_repeat_window_size(...)` 決定這輪要跑多少 repeat
  3. `_window_tasks(...)` 只展開當前 window
  4. `session.run_tasks(...)` 執行
  5. `_result_for_repeat(...)` 抽出單一 repeat 的候選結果
  6. `_evaluate_candidate_round(...)` 用 projected summary 做 evaluator 決策
  7. accepted 才 append rows 並記錄 repeat index / run seed
  8. 收滿後寫 variant outputs 並記 seed bank
- 關鍵資料契約：多 variant 在同一 `repeat_index` 必須共享同一個 seed，否則 `_shared_round_seed(...)` 會拒絕。
- 修改風險：這裡同時決定 collect 行為、輸出節奏與 seed bank 內容，是 `cli.exp` 最脆弱的核心函式。

### `Experiment._record_seed_bank_problem(...)`

- 目的：把一個 problem 的 collected repeat/seed 與 variant config snapshot 寫進內部 seed bank 緩衝區。
- 重要檢查：相同 `variant_key` 若已存在但 config snapshot 不一致，直接丟 `RuntimeError`，防止 seed bank 寫入同名異義 variant。

### `register(...)` / `build(...)` / `executeExperiment(...)`

- `register(...)`：evaluator registry 的正式註冊入口；`cli.exp.main` 會在啟動時集中註冊。
- `build(...)`：讀 `exp_cfg.yaml` 並回傳 `Experiment` 物件。
- `executeExperiment(...)`：薄 facade，讓外部可直接以 `Experiment` instance 執行 collect。

### `_assert_configured_evaluators_registered(...)` / `_evaluate_candidate_round(...)`

- `_assert_configured_evaluators_registered(...)`：在真正跑 collect 前做 registry completeness check。
- `_evaluate_candidate_round(...)`：
  - 先用 `_variant_summaries(...)` 生成 projected summaries
  - 再對每個 evaluation 建 `RoundEvalInput`
  - 收集 `RoundEvalDecision`
- 設計重點：evaluator 看的是「如果把這輪收進來，整體統計會變成什麼」，而不是只看 round 自身。

### `_selected_machines(...)` / `_repeat_window_size(...)` / `_window_tasks(...)`

- `_selected_machines(...)`：把 simulators 內所有 machines 收斂成 config 指定的 variant 子集。
- `_repeat_window_size(...)`：用 `ceil(worker_count / variant_count)` 控制一輪同時推進多少 repeat，避免單輪 tasks 爆太大。
- `_window_tasks(...)`：只為當前 problem + 當前 repeat 視窗展開 tasks，是 collect 演算法的 scheduler 邊界。

### `_result_for_repeat(...)` / `_copy_rows_by_variant(...)` / `_append_round_rows(...)` / `_machine_results_from_rows(...)`

- 這四個 helper 共同負責「候選 round -> projected cumulative result -> accepted cumulative result」的資料重組。
- 核心目的：不重跑 solver，就能在每個 candidate repeat 後重新計算 evaluator 看的 summary。

### `_shared_round_seed(...)` / `_variant_summaries(...)`

- `_shared_round_seed(...)`：驗證同一 round 的多 variant 確實共享 seed，並提取那個 seed 寫入 seed bank。
- `_variant_summaries(...)`：把 `SimulatorResult` 轉成 evaluator 要看的 `VariantSummary` tuple；這裡橋接了 `tools.stat` 與 `experiment.evaluation`。

### `_CollectionProgress` / `_write_json(...)`

- `_CollectionProgress`：
  - 保存每個 `(dataset_experiment_id, problem_id)` 已收集數
  - 每 `COLLECTION_PROGRESS_INTERVAL` 次 evaluator 決策才輸出一次進度
- `_write_json(...)`：
  - 本模組最底層的 JSON writer
  - 只負責 mkdir + dump，不處理語意驗證

## 對應函式索引與閱讀順序

1. `ProblemCollectionReport`
2. `ExperimentReport`
3. `Experiment.run`
4. `Experiment._build_dataset_simulators`
5. `Experiment._run_dataset`
6. `Experiment._run_problem`
7. `Experiment._record_seed_bank_problem`
8. `register`
9. `_clear_registered_evaluators_for_tests`
10. `build`
11. `executeExperiment`
12. `_assert_configured_evaluators_registered`
13. `_evaluate_candidate_round`
14. `_selected_machines`
15. `_repeat_window_size`
16. `_window_tasks`
17. `_result_for_repeat`
18. `_copy_rows_by_variant`
19. `_append_round_rows`
20. `_machine_results_from_rows`
21. `_shared_round_seed`
22. `_variant_summaries`
23. `_CollectionProgress`
24. `_write_json`
