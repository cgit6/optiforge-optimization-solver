# `tests/test_mkp_score_scaffold.py`

## 模組責任

`test_mkp_score_scaffold.py` 驗證 `mkp_score_scaffold` 的分數排序腳手架、repair/objective 路徑與重現性。

## 公開入口/主要類型

- pytest 自動發現測試
- 主要 helper：`_problem`
- 主要測試群：finite complete orders、rank/weight repair、run_problem reproducibility、lagrangian multipliers

## 主要資料結構與資料契約

score scaffold 產生的 variant 順序必須完整且有限；repair 產生的解必須能計算 objective；同 seed 的 problem run 應可重播。

## 資料流與控制流

先建 toy problem，再驗證 scaffold variants、rank/weight repair、`run_problem` 重現性與拉格朗日乘子有限性。

## 失敗路徑與例外條件

非有限分數、缺項排序、無法計算 objective 或 multiplier 發散都屬研究工具 regression。

## 副作用與資源生命週期

純計算與少量 repository load，無長生命週期副作用。

## 與其他模組的關係

目標模組是 `mkp.tools.mkp_score_scaffold`、`mkp.engine.repository` 與 `mkp.problem`。

## 對應函式索引與閱讀順序

1. `_problem`
2. `test_score_scaffold_variants_are_finite_and_complete_orders`
3. `test_score_scaffold_rank_and_weight_repair_return_objectives`
4. `test_score_scaffold_run_problem_is_reproducible`
5. `test_lagrangian_multipliers_are_finite`

## 核心函式與 helper 說明

### `_problem`

這個 helper 直接從正式 repository 載入 `WEISH/weish01`，讓 score scaffold 測試基於真實 problem，而不是人造小題。

### `test_score_scaffold_variants_are_finite_and_complete_orders`

這個案例驗證 `build_score_variants(...)` 產出的 score 與 order 都是完整可用的：分數要有限，排序必須覆蓋所有 item 且不重複。

### `test_score_scaffold_rank_and_weight_repair_return_objectives`

這個測試直接鎖定兩條 batch repair helper 的輸出形狀與基本可行性。它保護的是研究腳手架 helper，而不是 solver 主路徑。

### `test_score_scaffold_run_problem_is_reproducible` / `test_lagrangian_multipliers_are_finite`

前者保護整體 scaffold 在同 seed 下的可重現性，後者則固定 `lagrangian_multipliers(...)` 的數值穩定性與非負約束。
