# `tools/mkp_score_scaffold.py`

## 模組責任

`tools/mkp_score_scaffold.py` 是 MKP score-layer 的隨機候選 + repair scaffold。它不跑完整 metaheuristic，而是用 solver 內部的 LP/RC payload 與多種 score 排序規則，評估不同 score family 在純 repair 場景下的上限與傾向。

## 公開入口/主要類型

- `ScaffoldSummary`
- `lagrangian_multipliers(...)`
- `build_score_variants(...)`
- `run_problem(...)`
- `main(...)`

主要 helper：

- `_normalize(...)`
- `_safe_ratio(...)`
- `_batch_repair_rank_objectives(...)`
- `_batch_repair_weight_objectives(...)`
- `_problem_repository()`
- `_parse_problem_specs(...)`

## 主要資料結構與資料契約

- `DEFAULT_PROBLEMS` 每筆是 `(dataset, problem_id, qpso_mean)`。
- `build_score_variants(...)` 產出 `dict[str, tuple[score, order]]`，包含：
  - `CURRENT-RANK`
  - `CND-rank` / `CND-weight`
  - `DUAL-rank` / `DUAL-weight`
  - `RC-rank` / `RC-weight`
  - `HYB-rank` / `HYB-weight`
  - `LAG-rank` / `LAG-weight`
- `ScaffoldSummary` 收斂單一 `(variant, problem_id)` 的統計值與對 QPSO 的正向缺口。

## 資料流與控制流

1. `build_score_variants(...)` 先呼叫 solver 內部 `_build_lp_rc_item_eval_payload(...)` 取得 LP、reduced cost、bucket、base order 等中介資料。
2. `_normalize(...)`、`_safe_ratio(...)`、`lagrangian_multipliers(...)` 建出多組 score。
3. `run_problem(...)` 對每個 variant、每個 seed 生成隨機二值候選：
  - `*-rank` 走 `_batch_repair_rank_objectives(...)`
  - `*-weight` 走 `_batch_repair_weight_objectives(...)`
4. 取每個 seed repaired candidates 的最佳 objective，再彙總成 `ScaffoldSummary`。
5. `main(...)` 逐 problem 執行，輸出 `summary.json` 與簡單 ranking。

## 失敗路徑與例外條件

- 本工具只適用 MKP；若 problem model 不具備 `values/weights/capacities/items`，在 payload 建立或 Numba repair 階段會失敗。
- `best_known` 或傳入 `qpso_mean` 不合理，會直接扭曲 `pdev` / `positive_qpso_gap`。
- `problem` 自訂格式若不是 `dataset:problem_id:qpso_mean`，`_parse_problem_specs(...)` 會在拆字串時失敗。

## 副作用與資源生命週期

- 會讀 problem YAML。
- 會觸發 Numba compile/cache，因為兩個 batch repair helper 是 `@njit(cache=True)`。
- 會寫 `output/mkp_score_scaffold/summary.json` 或自訂輸出路徑。
- 這是研究分析工具，不直接回流到 runtime CLI。

## 與其他模組的關係

- 依賴 [`solver/BSCASMA_rl_rc_numba.py`](../solver/BSCASMA_rl_rc_numba.md) 的 `_build_lp_rc_item_eval_payload(...)`，因此與 solver 內部結構高度耦合。
- 與 [`tools/mkp_item_eval_experiment.py`](mkp_item_eval_experiment.md) 相比，它刻意抽掉完整 solver 搜尋，只保留 score + repair 層。
- 與 [`tools/mkp_rc_feature_ablation.py`](mkp_rc_feature_ablation.md) 一起構成演算法分析鏈：前者看 feature gate，這裡看 scoring scaffold。

## 對應函式索引與閱讀順序

1. `ScaffoldSummary`
2. `_normalize`
3. `_safe_ratio`
4. `lagrangian_multipliers`
5. `build_score_variants`
6. `_batch_repair_rank_objectives`
7. `_batch_repair_weight_objectives`
8. `run_problem`
9. `_problem_repository`
10. `_parse_problem_specs`
11. `main`
