# `cli/exp/mkp_calibration.py`

## 模組責任

`cli/exp/mkp_calibration.py` 是 `cli.exp` evaluator 家族中最複雜的一支。它把一整組 projected variant summaries 視為校準矩陣，驗證 transfer function 與目標參數組合是否達到研究假設。這不是單一 solver 的 pass/fail 檢查，而是對一整批 `bsma`、`bsca`、`bscasma` 組合做完整性檢查、paired comparison、target combo ranking 與 problem-specific margin 檢查。

## 公開入口/主要類型

- 常數與研究契約：
  - `EXPECTED_COMBO_COUNT`
  - `PDEV_TOLERANCE`
  - `BSCA_MARGIN_PDEV`
  - `BRLSMASCA_MARGIN_PDEV`
  - `BSCA_TRANSFER_MAX_AVG_RANK`
  - `EXPECTED_CTFS`
  - `EXPECTED_TRANSFER_CTF`
  - `ALGORITHM_BY_SOLVER_ID`
  - `EXPECTED_ALGORITHM_COUNTS`
  - `CORE_ALGORITHMS`
  - `PAIR_KEYS`
  - `EXPECTED_PAIRS`
  - `TARGET_COMBOS`
  - `TARGET_COMBO_FRONT6_MIN_LEADS`
  - `TARGET_COMBO_GK_MAX_LAGS`
- transfer evaluator：
  - `mkp_transfer_paired_strict_evaluator(...)`
  - `mkp_transfer_core_strict_evaluator(...)`
  - `mkp_transfer_bsca_margin_005_evaluator(...)`
- target combo evaluator：
  - `mkp_target_combo_best_evaluator(...)`
  - `mkp_target_combo_core_strict_evaluator(...)`
  - `mkp_target_combo_bsma_strict_evaluator(...)`
  - `mkp_target_combo_bsca_margin_005_evaluator(...)`
  - `mkp_target_combo_brlsmasca_margin_004_evaluator(...)`
  - `mkp_target_combo_front6_lead_evaluator(...)`
  - `mkp_target_combo_gk_lag_evaluator(...)`
- composite evaluator：
  - `mkp_calibration_evaluator(...)`

## 主要資料結構與資料契約

- `variant_summaries` 必須代表一個完整 calibration combo matrix，而不是任意 solver 子集。
- 每筆 variant 至少要提供：
  - `solver_id`
  - `param_set_index`
  - `params["ctf"]`
  - 視 algorithm 不同而定的 `params["z"]`、`params["a"]`
  - 可比較的 `summary.overall.pdev`
- solver family 會被映射成研究語意中的 algorithm：
  - `bsma_numba -> bsma`
  - `bsca_numba -> bsca`
  - `brlsmasca_rl_numba -> bscasma`
- 完整矩陣契約包括：
  - 總組合數必須是 `45`
  - `bsma` `9` 組、`bsca` `9` 組、`bscasma` `27` 組
  - 每組 `(z)`、`(a)` 或 `(z, a)` pair 都必須對應 `EXPECTED_CTFS` 中三種 transfer function，且每種恰好一筆
- target combo 契約：
  - `bsma` 目標是 `z = 0.08`
  - `bsca` 目標是 `a = 1.5`
  - `bscasma` 目標是 `z = 0.08, a = 2.5`
- special problem 契約：
  - `TARGET_COMBO_FRONT6_MIN_LEADS` 定義前六題 problem 至少要領先 challenger 的 margin
  - `TARGET_COMBO_GK_MAX_LAGS` 定義 GK 題目允許的最大落後值

## 資料流與控制流

1. `_combo_context(...)` 是所有 evaluator 的共同入口：
   - `_summary_failures(...)` 先排除 invalid projected summary。
   - `_combo_from_variant(...)` 把 `VariantSummary` 轉成 calibration combo dict。
   - `_check_combo_count(...)`、`_check_algorithm_counts(...)`、`_check_unknown_algorithms(...)` 建立完整性檢查。
2. transfer family evaluator 會先跑 `_check_pair_completeness(...)`，確保每個參數 pair 都有三個 `ctf` 對照可做 paired comparison。
3. `_check_transfer_paired(...)` 會在每個 algorithm 內：
   - 以 pair 為單位蒐集三個 `ctf` 的 `pdev`
   - 用 `_dense_ranks(...)` 算 pair 內名次
   - 再對所有 pair 做 `avg_pdev` / `avg_rank` 聚合
   - 驗證 `abs_pow_16` 是否為 strict best，或對 `bsca` 套用 margin 規則
4. target combo family evaluator 透過 `_single_target_combo_check(...)`：
   - 依 algorithm 與 `ctf` 分組
   - 為每個 expected option 蒐集唯一對應 variant
   - 比較 target option 的 `avg_pdev` / `avg_rank` 是否為 strict best
5. `_target_margin_check(...)`、`_bsca_transfer_margin_check(...)` 針對 `bsca`、`bscasma` 等家族提供「strict best 或在 margin 內」的判斷。
6. `_target_combo_pdev_margin_checks(...)` 會計算 target 相對 challenger 的 lead / lag，用於 front-six 與 GK 的 problem-specific evaluator。
7. `mkp_calibration_evaluator(...)` 是 composite evaluator，要求 transfer 與 target-combo 兩大主檢查都通過。

## 失敗路徑與例外條件

- projected summaries 有 invalid/infeasible/runtime error 時，所有 calibration evaluator 都會先因 integrity failure 而失敗。
- combo 總數不對、algorithm 計數不對、出現未知 solver family、pair 缺漏或重複時，都會被視為 calibration set incomplete。
- `_single_target_combo_check(...)` 對某個 algorithm 找不到完整 option 集，或出現同一 option 多筆 variant 時，會回傳 `target_option_missing_or_ambiguous`。
- front-six / GK evaluator 若 `problem_id` 不在對應 map 中，會直接 `FAIL`；這代表 evaluator 被套用到錯誤題目集合。
- 本模組所有比較都以 `Pdev` 為核心；若上游 summary 或 param schema 改變，這些研究假設會最先失效。

## 副作用與資源生命週期

- 純計算模組，沒有 I/O、沒有 registry mutation、沒有長生命週期快取。
- 單次呼叫會建立大量 `details` dict，這些 dict 既是決策依據，也是實驗除錯的主要證據。
- 因為每個 evaluator 都重新從 `variant_summaries` 建 combo context，重複呼叫的成本是可預期的 CPU 計算，不涉及外部資源。

## 與其他模組的關係

- 上游：`experiment.experiment` 把 projected round 打包成 `RoundEvalInput`。
- 契約來源：`experiment.evaluation`。
- 註冊入口：`cli/exp/main.py`。
- 研究背景關聯：
  - solver family 定義與參數語意對應到 `note/plan/06_solver_algorithms.md` 中的 `BSMA`、`BSCA`、`BSCASMA` 家族。
  - collect 設定與 baseline/margin 來源寫在 `cli/exp/exp_cfg.yaml`。
- 對下游影響：本模組的 `PASS/FAIL` 直接決定某個 repeat 是否被實驗正式收錄，因此它實際上控制了 calibration dataset 的最終 seed bank 與 summary 內容。

## 核心函式與 helper 說明

### `_combo_context(variant_summaries)`

- 目的：建立所有 calibration evaluator 共用的 combo matrix 與 integrity 檢查結果。
- 控制流：summary 驗證 -> variant 轉 combo dict -> 檢查總數、algorithm 計數與未知 family。
- 角色：這是所有 calibration 規則的共同前置層；沒過這關，後面任何 paired 或 target combo 檢查都沒有意義。

### `_check_pair_completeness(combos)` / `_check_transfer_paired(combos)`

- 目的：驗證每個參數 pair 都具備三個 `ctf` 對照，並判斷 transfer family 是否符合 strict best / margin 規則。
- 在流程中的角色：這一組 helper 負責把 projected variants 轉成研究上的「paired transfer comparison」。

### `_check_target_combos(combos)` / `_single_target_combo_check(...)`

- 目的：針對每個 algorithm 檢查 target parameter combo 是否是 strict best，或至少落在允許 margin 內。
- 注意事項：這裡不只是看單題 `pdev`，而是先聚合成 option-level 平均與排名，再做 target 判定。

### `_target_combo_pdev_margin_checks(...)` / `_target_margin_check(...)`

- 目的：處理 front-six 與 GK 題組的 problem-specific margin 規則。
- 角色：這些 helper 把 calibration 從全域平均規則延伸到特定題目集合的 lead / lag 契約。

### `mkp_transfer_*` / `mkp_target_combo_*` / `mkp_calibration_evaluator(...)`

- 角色：這些 evaluator 不是彼此孤立，而是共用 `_combo_context(...)` 與比較 helper 的不同觀測面。
- 維護建議：新增 calibration rule 時，優先重用現有 combo context 與 pair/target helper，而不是再造一套 variant 解析邏輯。

## 對應函式索引與閱讀順序

1. `EXPECTED_COMBO_COUNT`
2. `EXPECTED_CTFS`
3. `EXPECTED_PAIRS`
4. `TARGET_COMBOS`
5. `mkp_transfer_paired_strict_evaluator`
6. `mkp_transfer_core_strict_evaluator`
7. `mkp_transfer_bsca_margin_005_evaluator`
8. `mkp_target_combo_best_evaluator`
9. `mkp_target_combo_core_strict_evaluator`
10. `mkp_target_combo_bsma_strict_evaluator`
11. `mkp_target_combo_bsca_margin_005_evaluator`
12. `mkp_target_combo_brlsmasca_margin_004_evaluator`
13. `mkp_target_combo_front6_lead_evaluator`
14. `mkp_target_combo_gk_lag_evaluator`
15. `mkp_calibration_evaluator`
16. `_combo_context`
17. `_summary_failures`
18. `_combo_from_variant`
19. `_check_combo_count`
20. `_check_algorithm_counts`
21. `_check_unknown_algorithms`
22. `_check_pair_completeness`
23. `_check_transfer_paired`
24. `_check_target_combos`
25. `_single_target_combo_check`
26. `_bsca_transfer_margin_check`
27. `_bsca_target_margin_check`
28. `_target_combo_pdev_margin_checks`
29. `_target_combo_pdev_margin_check`
30. `_target_margin_check`
31. `_dense_ranks`
32. `_avg`
33. `_algorithm_count`
34. `_matches_target`
35. `_target_label`
36. `_target_algorithm`
37. `_same_value`
