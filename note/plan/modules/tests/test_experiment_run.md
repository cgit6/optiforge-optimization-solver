# `tests/test_experiment_run.py`

## 模組責任

`test_experiment_run.py` 驗證 `Experiment.run(...)` 的 collect scheduler、shared round seed、repeat limit、unknown evaluator fail-fast 與 process worker 路徑。

## 公開入口/主要類型

- pytest 自動發現測試
- 主要 fixture/helper：`_clear_evaluators`、`_write_problem_yaml`、`_write_solver_yaml`、`_config_text`、`_project`
- 主要測試群：streaming scheduler、collect stop、shared seed、repeat limit、empty evaluation、unknown evaluator、process worker、status log

## 主要資料結構與資料契約

evaluator 只決定收不收 candidate round；被拒絕的 round 不得寫入 collected runs，收滿 `collects` 後必須立即停止同 problem 後續 repeat。

## 資料流與控制流

fixture 先清 evaluator registry，helpers 建最小 problem/solver/exp project；測試再以自訂 evaluator 觀察 `simulator_result` 與 `projected_result` 的長度、repeat index 與 output 內容。

## 失敗路徑與例外條件

unknown evaluator、repeat 內收不滿樣本、shared round seed 不一致或 process worker 路徑失效，都屬 collect 主流程回歸。

## 副作用與資源生命週期

會在 `tmp_path/output` 寫出完整 experiment 結果與 summary；fixture 會在每個測試前後重置 evaluator registry。

## 與其他模組的關係

目標模組是 `mkp.experiment` 與 `mkp.experiment.experiment`；它是 `cli.exp` runtime 的核心整合測試。

## 對應函式索引與閱讀順序

1. `_clear_evaluators`
2. `_write_problem_yaml`
3. `_write_solver_yaml`
4. `_config_text`
5. `_project`
6. `test_streaming_scheduler_collects_per_problem_and_discards_failed_rounds`
7. `test_problem_stops_after_collects_is_reached_and_discards_prefetched_rounds`
8. `test_round_seed_is_shared_across_solver_params`
9. `test_repeat_limit_fail_fast_when_problem_cannot_collect_enough_rounds`
10. `test_empty_problem_evaluation_collects_first_available_rounds`
11. `test_run_fails_fast_on_unknown_problem_evaluator`
12. `test_process_worker_path_collects_rounds`
13. `test_experiment_prints_collection_status_lines`
14. `test_experiment_prints_collection_status_every_50_evaluations`

## 核心函式與 helper 說明

### `_clear_evaluators` 與 project 建構 helper

`_clear_evaluators` 先把 evaluator registry 清乾淨，避免測試間彼此污染。`_write_problem_yaml`、`_write_solver_yaml`、`_config_text`、`_project` 則建立最小 experiment project，讓 collect scheduler 測試可以直接控制 problem、solver 與 evaluation config。

### collect scheduler 主流程測試群

`test_streaming_scheduler_collects_per_problem_and_discards_failed_rounds`、`test_problem_stops_after_collects_is_reached_and_discards_prefetched_rounds`、`test_empty_problem_evaluation_collects_first_available_rounds` 描述 collect 規則：候選 round 可以被 evaluator 拒絕、收滿即停、沒有 evaluator 時採第一個可用 round。

### seed 與 evaluator fail-fast 測試群

`test_round_seed_is_shared_across_solver_params` 固定同一 round 內不同 solver 變體共享 seed；`test_repeat_limit_fail_fast_when_problem_cannot_collect_enough_rounds` 與 `test_run_fails_fast_on_unknown_problem_evaluator` 則保護實驗流程在無法收滿樣本或 evaluator 名稱錯誤時要立即中止。

### worker 與狀態輸出測試群

`test_process_worker_path_collects_rounds` 驗證 process worker 路徑和 sequential path 對 collect 行為一致。`test_experiment_prints_collection_status_lines`、`test_experiment_prints_collection_status_every_50_evaluations` 則固定實驗執行中的進度輸出節奏。
