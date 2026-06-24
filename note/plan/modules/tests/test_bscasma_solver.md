# `tests/test_bscasma_solver.py`

## 模組責任

`test_bscasma_solver.py` 是 `BSCASMA` 家族最深的回歸測試檔，覆蓋 Python 基線、Numba 測試版、RL 版、RL+RC 版，以及多個進階 helper/feature flag 的行為契約。

## 公開入口/主要類型

- pytest 自動發現測試
- 主要 helper：`_build_problem`、`_build_config`、`_build_numba_config`
- 主要測試群：base/numba solve、RL metadata、RC helper、feature flags、repair v2、restart、group shuffle、local search、path relinking

## 主要資料結構與資料契約

測試以合成 MKP problem 與多組 config 驗證：solver metadata 必須完整、same-seed 結果必須穩定、`cp_list`/score payload/dual price/group shuffle/repair v2/local search/path relinking 等輔助機制必須輸出有限且可重播的結果。

## 資料流與控制流

先檢查 registry 與基本 solve 契約，再逐層往 `rl_numba`、`rl_rc_numba` 的 feature flags、初始化策略、restart、guided probability、archive/path relinking、repair 變體與 cache 行為推進。

## 失敗路徑與例外條件

任何非法 repair/restart/remaining strategy/init 參數都必須被拒絕；高風險 helper 若破壞 feasibility、完整排列、seeded determinism 或 metadata，一律視為 regression。

## 副作用與資源生命週期

純 solver 單元/整合測試，無檔案 I/O；但會觸發大量 hot-loop helper 與 metadata 路徑。

## 與其他模組的關係

目標模組橫跨 `mkp.solver.BSCASMA`、`BSCASMA_test_numba`、`BSCASMA_rl_numba`、`BSCASMA_rl_rc_numba`，並與 `BSMA_numba`、`BSCA_numba` repair/score helper 做交叉比對。

## 對應函式索引與閱讀順序

1. `_build_problem`
2. `_build_config`
3. `_build_numba_config`
4. `test_bscasma_solver_can_be_created_by_registry`
5. `test_bscasma_numba_solvers_can_be_created_by_registry`
6. `test_bscasma_solver_returns_valid_solve_result`
7. `test_bscasma_reproducibility_same_seed_same_result`
8. `test_bscasma_reproducibility_different_seed_can_differ`
9. `test_bscasma_stop_condition_max_iterations_reached`
10. `test_bscasma_params_pop_size_from_config_affects_evaluation_count`
11. `test_bscasma_rejects_invalid_params`
12. `test_bscasma_rl_numba_returns_valid_solve_result_and_metadata`
13. `test_bscasma_rl_numba_reproducibility_same_seed_same_result`
14. `test_bscasma_rl_numba_z_one_forces_global_action_gate`
15. `test_bscasma_rl_rc_numba_returns_valid_solve_result_and_metadata`
16. `test_bscasma_rl_rc_numba_reproducibility_same_seed_same_result`
17. `test_bscasma_rl_rc_numba_cp_list_is_complete_permutation`
18. `test_bscasma_rl_rc_core_score_cp_payload_builds_complete_order`
19. `test_bscasma_rl_rc_freq_gated_v2_payload_is_reproducible_with_seed`
20. `test_bscasma_rl_rc_item_eval_methods_solve_and_report_metadata`
21. `test_bscasma_rl_rc_numba_default_cp_list_is_ordered_and_seed_independent`
22. `test_bscasma_rl_rc_dual_price_matches_legacy_dual_formulation`
23. `test_bscasma_rl_rc_group_shuffle_is_seeded_and_stays_inside_groups`
24. `test_bscasma_rl_rc_numba_explicit_group_shuffle_uses_group_method`
25. `test_bscasma_rl_rc_initial_pop_does_not_keep_rejected_item_resource`
26. `test_bscasma_rl_rc_default_init_flags_match_implicit_defaults`
27. `test_bscasma_rl_rc_mixed_init_is_feasible_binary_and_reproducible`
28. `test_bscasma_rl_rc_restart_triggers_after_stagnation_and_keeps_best_feasible`
29. `test_bscasma_rl_rc_guided_probability_is_finite_and_clipped`
30. `test_bscasma_rl_rc_local_search_improves_toy_solution_and_keeps_feasible`
31. `test_bscasma_rl_rc_archive_path_relink_improves_without_downgrading_best`
32. `test_bscasma_rl_rc_new_feature_flags_are_reproducible_and_report_metadata`
33. `test_bscasma_rl_rc_repair_v2_default_matches_current_repair`
34. `test_bscasma_rl_rc_repair_v2_repairs_infeasible_solution`
35. `test_bscasma_rl_rc_repair_v2_can_improve_with_bounded_swap`
36. `test_bscasma_rl_rc_numba_rejects_invalid_repair_params`
37. `test_bscasma_rl_rc_numba_rejects_invalid_init_restart_params`
38. `test_bscasma_rl_rc_numba_rejects_invalid_remaining_strategy_params`
39. `test_bscasma_test_numba_uses_new_solver_id`
40. `test_bscasma_test_numba_reproducibility_same_seed_same_result`
41. `test_bscasma_rl_incremental_density_matches_full_density`
42. `test_numba_cp_list_caches_are_per_solver_core`
43. `test_bscasma_local_repair_matches_bsca_repair`
44. `test_bscasma_rl_numba_rejects_invalid_params`

## 核心函式與 helper 說明

### `_build_problem` / `_build_config` / `_build_numba_config`

這組 helper 提供整個 `BSCASMA` 家族共用的真實 problem 與 config 基底，覆蓋純 Python、RL Numba、RC Numba 與 test-numba 變體。因為這個檔案同時在驗證多個 solver id，所以 config builder 的欄位相容性非常重要。

### registry、基本求解與 deterministic 基線

前段的 `test_bscasma_*_can_be_created_by_registry`、`test_bscasma_solver_returns_valid_solve_result`、`test_bscasma_reproducibility_*`、`test_bscasma_stop_condition_max_iterations_reached`、`test_bscasma_params_pop_size_from_config_affects_evaluation_count`、`test_bscasma_rejects_invalid_params` 描述主 solver 家族的基礎契約。

### RL / RC metadata、cp-list 與 item-eval payload 測試群

中段從 `test_bscasma_rl_numba_returns_valid_solve_result_and_metadata` 到 `test_bscasma_rl_rc_item_eval_methods_solve_and_report_metadata`，再到 `test_bscasma_rl_rc_numba_default_cp_list_is_ordered_and_seed_independent`、`test_bscasma_rl_rc_dual_price_matches_legacy_dual_formulation`、`test_bscasma_rl_rc_group_shuffle_is_seeded_and_stays_inside_groups`，主要在保護 RL/RC 變體的 metadata、candidate permutation、payload builder 與 dual-price / group-shuffle 支鏈。

### restart、repair、local-search、archive 與 density 測試群

後段的 `test_bscasma_rl_rc_restart_triggers_after_stagnation_and_keeps_best_feasible`、`test_bscasma_rl_rc_guided_probability_is_finite_and_clipped`、`test_bscasma_rl_rc_local_search_improves_toy_solution_and_keeps_feasible`、`test_bscasma_rl_rc_archive_path_relink_improves_without_downgrading_best`、`test_bscasma_rl_rc_repair_v2_*`、`test_bscasma_rl_incremental_density_matches_full_density`、`test_bscasma_local_repair_matches_bsca_repair`，固定了最容易在 hot-loop 調整時出錯的 helper 語意。

### cache / solver id / 參數驗證測試群

`test_numba_cp_list_caches_are_per_solver_core`、`test_bscasma_test_numba_uses_new_solver_id`、`test_bscasma_rl_numba_rejects_invalid_params` 與多個 `rejects_invalid_*` 案例一起保護 cache 隔離、命名一致性與新 feature flag 的參數驗證。
