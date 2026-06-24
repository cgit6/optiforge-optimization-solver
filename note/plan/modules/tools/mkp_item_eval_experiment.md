# `tools/mkp_item_eval_experiment.py`

## 模組責任

`tools/mkp_item_eval_experiment.py` 是 MKP item-evaluation 變體的批次比較工具。它用固定基底 solver `brlsmasca_rl_rc_numba` 的 param set `20`，在多個 OR dataset/問題/seed 上比較不同 item scoring 或 feature toggle 的效果，並輸出可續跑的 `runs.jsonl` 與彙總排名。

## 公開入口/主要類型

- `ItemEvalSummary`
- `sample_or_problems(...)`
- `run_experiment(...)`
- `main(...)`

主要內部 helper：

- `_problem_repository()`
- `_solver_registry()`
- `_or_datasets(...)`
- `_parse_problem_specs(...)`
- `_base_config(...)`
- `_row_key(...)`
- `_load_existing_rows(...)`
- `_run_variant(...)`
- `_worker_init(...)`
- `_run_variant_task(...)`
- `_summaries(...)`
- `_row_pdev(...)`
- `_wilcoxon_less_p(...)`
- `_ranking(...)`

## 主要資料結構與資料契約

- `ITEM_EVAL_VARIANTS` 是實驗矩陣的正式來源；每個 variant 都是覆寫 `config["params"]` 的 patch。
- `BASELINE_VARIANTS = ("BASE",)`，所有 delta 與 ranking 都以它為基準。
- 輸出資料：
  - `runs.jsonl`：每個 `(dataset, problem_id, variant, seed)` 一列
  - `summary.json`：`selected_problems`、`seeds`、`variants`、`summaries`、`ranking`
- `ItemEvalSummary` 把單一 `(dataset, problem_id, variant)` 的統計值與 baseline 差值收斂成 dataclass。

## 資料流與控制流

1. `_problem_repository()`、`_solver_registry()` 建立標準 problem/solver 入口。
2. `run_experiment(...)` 先選題：
  - 若有 `--problem`，用 `_parse_problem_specs(...)`
  - 否則用 `sample_or_problems(...)` 從 OR datasets 隨機抽樣
3. `_load_existing_rows(...)` 讀取既有 `runs.jsonl`，跳過已完成組合，支援續跑。
4. 依 `workers` 決定走單程序或 `ProcessPoolExecutor`：
  - worker 啟動時用 `_worker_init(...)` 載 problem repository 與 solver registry
  - `_run_variant_task(...)` 再依 task 載 problem 並呼叫 `_run_variant(...)`
5. 完成後 `_summaries(...)` 統計 mean/std/pdev/delta，`_ranking(...)` 再加上 Wilcoxon 檢定與 strict gate 排序。
6. 最後寫出 `summary.json`，並回傳同一份 payload。

## 失敗路徑與例外條件

- `--problem` 若不是 `DATASET:PROBLEM_ID` 格式，`_parse_problem_specs(...)` 會丟 `ValueError`。
- 任一 problem YAML、solver config 或 solver 執行失敗，整個批次會中斷；本工具沒有 per-task try/continue。
- `best_known` 缺失或不合理時，`pdev` 計算會連帶失真。
- `wilcoxon(...)` 在資料不足或全零差異時會回傳 `None` 或 `1.0`，ranking 會保留這些不確定性。

## 副作用與資源生命週期

- 會建立 `output_root`、附加寫入 `runs.jsonl`、覆寫 `summary.json`。
- 多 worker 模式會啟動 `ProcessPoolExecutor`，每個 worker 都會建立自己的 repository 與 registry。
- 這不是 runtime 主流程的一部分，而是演算法研究/比較工具。

## 與其他模組的關係

- 依賴 [`engine/builders.py`](../engine/builders.md) 與 [`problem/builders.py`](../problem/builders.md) 建立標準 registry。
- 依賴 [`tools/solver_config_loader.py`](solver_config_loader.md) 讀 `brlsmasca_rl_rc_numba` param set `20`。
- 與 [`tools/mkp_score_scaffold.py`](mkp_score_scaffold.md)、[`tools/mkp_rc_feature_ablation.py`](mkp_rc_feature_ablation.md) 共同構成 MKP 演算法分析支援鏈，但焦點是「完整 solver 變體比較」，不是隨機 scaffold。

## 對應函式索引與閱讀順序

1. `ITEM_EVAL_VARIANTS`
2. `ItemEvalSummary`
3. `_problem_repository`
4. `_solver_registry`
5. `sample_or_problems`
6. `_base_config`
7. `_run_variant`
8. `_worker_init`
9. `_run_variant_task`
10. `_summaries`
11. `_wilcoxon_less_p`
12. `_ranking`
13. `run_experiment`
14. `main`
