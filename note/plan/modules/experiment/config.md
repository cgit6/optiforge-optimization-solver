# `experiment/config.py`

## 模組責任

`experiment/config.py` 負責解析 `cli/exp/exp_cfg.yaml`。它不做實驗執行，但負責把 YAML 轉成強型別 `ExperimentConfig`，並在執行前完成 problem 存在性與 solver capability 的 fail-fast 驗證。

## 公開入口/主要類型

- `EvaluationBaseline`
- `EvaluationSpec`
- `ProblemSetting`
- `DatasetSetting`
- `SolverSelection`
- `ExperimentConfig`
- `load_config(...)`

## 主要資料結構與資料契約

- top-level 必要欄位：`experiment_name`、`collects`、`solvers`、`repeat`、`dataset_settings`。
- `SolverSelection` 定義單一 solver 與要跑的 `param_idx` 清單。
- `DatasetSetting` 定義單一 dataset experiment：
  - `experiment_id`
  - `dataset`
  - `problem_settings`
  - `problem_type`
- `ProblemSetting` 定義單一 problem 要套用的 evaluator 集合。
- `EvaluationSpec` 與 `EvaluationBaseline` 保存 evaluator 名稱與可選 baseline 門檻。
- `ExperimentConfig.solver_variants` 會展平成 `(solver_id, param_index)` 序列，供 collect 流程直接使用。

## 資料流與控制流

1. `load_config(...)` 讀 YAML 並呼叫 `_parse_config(...)`。
2. `_parse_config(...)` 驗證 top-level key，讀出 `collects`、`repeat`、solver selections。
3. `_load_solver_configs(...)` 先把指定 solver 的 YAML 全部載入，供後續 capability 檢查。
4. `_validate_solver_param_indices(...)` 檢查 `param_idx` 沒有超界。
5. `_parse_dataset_settings(...)` 逐 dataset 解析。
6. `_parse_dataset_setting(...)` 會透過 `ProblemRepository.read_metadata(...)` 讀 problem metadata，確認同一 dataset setting 中的 problem 不混用不同 type/encoding/direction。
7. `_validate_solver_capabilities(...)` 用 solver YAML 的 capability 檢查所有 solver 是否都能跑該 dataset setting。
8. 全部通過後才建立 `ExperimentConfig`。

## 失敗路徑與例外條件

- YAML 格式不是 mapping、缺 key、多未知 key、型別不符、空 list、重複 solver/param pair、重複 problem id、重複 experiment-id 都會 fail-fast。
- `param_idx` 超出 solver YAML 實際 param set 範圍會丟 `ValueError`。
- dataset setting 中若 problem metadata 混合不同 type/encoding/direction，也會直接拒絕。
- solver capability 與 problem metadata 不相容時，解析配置階段就中止，不會進入 `Experiment.run(...)`。

## 副作用與資源生命週期

- 主要副作用是讀取 experiment YAML、problem YAML metadata、solver YAML。
- 不建立 shared memory，也不觸發 solver 執行。
- 解析完成後回傳不可變 dataclass 組合，供 `experiment.experiment` 長時間持有。

## 與其他模組的關係

- 上游：`cli.exp.main` 與 `experiment.experiment.build(...)` 以這個模組為入口。
- 依賴：`engine.repository`、`problem.registry builder`、`tools.solver_config_loader`。
- 下游：`Experiment.run(...)` 完全依賴 `ExperimentConfig` 與其中的 `DatasetSetting` / `ProblemSetting`。

## 對應函式索引與閱讀順序

1. `EvaluationBaseline`
2. `EvaluationSpec`
3. `ProblemSetting`
4. `DatasetSetting`
5. `SolverSelection`
6. `ExperimentConfig`
7. `load_config`
8. `_read_yaml`
9. `_parse_config`
10. `_parse_solver_selections`
11. `_validate_solver_param_indices`
12. `_parse_dataset_settings`
13. `_parse_dataset_setting`
14. `_parse_problem_settings`
15. `_parse_base_line`
16. `_parse_baseline_entry`
17. `_load_solver_configs`
18. `_solver_capabilities`
19. `_validate_solver_capabilities`
20. `_validate_keys`
21. `_parse_non_empty_string`
22. `_parse_positive_int`
23. `_parse_non_negative_int`
24. `_parse_optional_float`
25. `_validate_optional_float`
26. `_parse_int`
