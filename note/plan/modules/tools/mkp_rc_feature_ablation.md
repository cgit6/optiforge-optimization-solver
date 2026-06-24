# `tools/mkp_rc_feature_ablation.py`

## 模組責任

`tools/mkp_rc_feature_ablation.py` 是 `brlsmasca_rl_rc_numba` 功能開關的 ablation 工具。它固定從 param set `20` 出發，逐一切換 guided binary、local search、archive/path relinking 等功能，再用 `cli/exp/exp_cfg.yaml` 內的 QPSO baseline mean 做 guard 與排名。

## 公開入口/主要類型

- `AblationSummary`
- `summarize_rows(...)`
- `run_ablation(...)`
- `main(...)`

主要內部 helper：

- `_problem_repository()`
- `_solver_registry()`
- `_load_qpso_means(...)`
- `_load_base_config(...)`
- `_run_one(...)`
- `_parse_problems(...)`

## 主要資料結構與資料契約

- `DEFAULT_GUARD_PROBLEMS` 是預設守門問題集合。
- `VARIANT_OVERRIDES` 定義每個 ablation variant 對 solver `params` 的 patch。
- `_load_qpso_means(...)` 假設 `cli/exp/exp_cfg.yaml` 的 `dataset_settings[].problems[].base_line[]` 結構存在，且 `name == "qpso"`。
- `AblationSummary` 收斂單一 `(variant, problem_id)` 的統計值與相對 QPSO gap。

## 資料流與控制流

1. `_load_qpso_means(...)` 先從 `cli/exp/exp_cfg.yaml` 萃取 baseline mean。
2. `run_ablation(...)` 建立標準 repository 與 solver registry。
3. 對每個 problem、每個 variant、每個 seed 呼叫 `_run_one(...)`。
4. `summarize_rows(...)` 依 variant 聚合 mean/std/pdev/feasible rate。
5. `run_ablation(...)` 再計算：
  - `combined_positive_qpso_gap`
  - 相對 `BASE` 的 guard 指標
  - ranking
6. `main(...)` 解析 CLI，寫出 `output_root/summary.json`，並在 stdout 印前幾名。

## 失敗路徑與例外條件

- `exp_cfg.yaml` 若結構改動、缺 QPSO baseline 或 problem id 不存在，ablation 會在 baseline 載入或查表時失敗。
- `_parse_problems(...)` 對自訂 `dataset:problem_id` 格式沒有額外防呆；格式錯誤會直接在 `split(":")` 或後續 load 階段失敗。
- solver 執行失敗時，整個 ablation 中斷。

## 副作用與資源生命週期

- 會讀：
  - `configs/problems/...`
  - `configs/solvers/brlsmasca_rl_rc_numba.yaml`
  - `cli/exp/exp_cfg.yaml`
- 會寫 `output/mkp_rc_feature_ablation/summary.json` 或自訂輸出路徑。
- 目前是單程序迴圈，沒有 pool/shared memory 管理邏輯。

## 與其他模組的關係

- 依賴 [`engine/builders.py`](../engine/builders.md) 建 solver registry。
- 依賴 [`tools/solver_config_loader.py`](solver_config_loader.md) 取得基底 solver config。
- 與 [`cli/exp/exp_cfg.yaml`](../../cli/exp/main.md) 的關係不是執行 collect，而是借用其中的 QPSO baseline 資料。
- 與 [`tools/mkp_item_eval_experiment.py`](mkp_item_eval_experiment.md) 同屬研究工具，但這裡比較的是 feature gate，不是 item score family。

## 對應函式索引與閱讀順序

1. `DEFAULT_GUARD_PROBLEMS`
2. `VARIANT_OVERRIDES`
3. `AblationSummary`
4. `_load_qpso_means`
5. `_load_base_config`
6. `_run_one`
7. `summarize_rows`
8. `run_ablation`
9. `_parse_problems`
10. `main`
