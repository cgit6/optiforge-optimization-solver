# Solver Helper Inventory

列出 `solver/` 下 class/function/method，包含 Numba hot-loop helper。詳細說明見 `../05_api_reference.md`。

| Solver File | Kind | API | Line | Decorators |
|---|---|---|---:|---|
| `solver/BSCA.py` | class | `BSCACore` | 18 |  |
| `solver/BSCA.py` | method | `BSCACore.__init__` | 21 |  |
| `solver/BSCA.py` | method | `BSCACore.pseudo_utility` | 65 |  |
| `solver/BSCA.py` | method | `BSCACore.initial_pop` | 78 |  |
| `solver/BSCA.py` | method | `BSCACore.repair` | 90 |  |
| `solver/BSCA.py` | method | `BSCACore.sort_pop` | 109 |  |
| `solver/BSCA.py` | method | `BSCACore.run` | 118 |  |
| `solver/BSCA.py` | class | `BSCASolver` | 166 | dataclass |
| `solver/BSCA.py` | method | `BSCASolver.solve` | 169 |  |
| `solver/BSCASMA.py` | class | `BRLSMASCATestCore` | 18 |  |
| `solver/BSCASMA.py` | method | `BRLSMASCATestCore.__init__` | 26 |  |
| `solver/BSCASMA.py` | method | `BRLSMASCATestCore.init_best_method` | 98 |  |
| `solver/BSCASMA.py` | method | `BRLSMASCATestCore.pseudo_utility` | 105 |  |
| `solver/BSCASMA.py` | method | `BRLSMASCATestCore.initial_pop` | 119 |  |
| `solver/BSCASMA.py` | method | `BRLSMASCATestCore.repair` | 134 |  |
| `solver/BSCASMA.py` | method | `BRLSMASCATestCore.sort_pop` | 153 |  |
| `solver/BSCASMA.py` | method | `BRLSMASCATestCore.policy` | 172 |  |
| `solver/BSCASMA.py` | method | `BRLSMASCATestCore.update_sma_weight` | 180 |  |
| `solver/BSCASMA.py` | method | `BRLSMASCATestCore.sma_global` | 198 |  |
| `solver/BSCASMA.py` | method | `BRLSMASCATestCore.sma_local` | 209 |  |
| `solver/BSCASMA.py` | method | `BRLSMASCATestCore.sca_sin` | 236 |  |
| `solver/BSCASMA.py` | method | `BRLSMASCATestCore.sca_cos` | 252 |  |
| `solver/BSCASMA.py` | method | `BRLSMASCATestCore.update_prob` | 268 |  |
| `solver/BSCASMA.py` | method | `BRLSMASCATestCore.run` | 286 |  |
| `solver/BSCASMA.py` | class | `BRLSMASCATestSolver` | 337 | dataclass |
| `solver/BSCASMA.py` | method | `BRLSMASCATestSolver.solve` | 340 |  |
| `solver/BSCASMA_rl_numba.py` | function | `_cp_list_cache_key` | 27 |  |
| `solver/BSCASMA_rl_numba.py` | function | `_sort_bscasma_rl_desc_deterministic_inplace` | 40 | njit |
| `solver/BSCASMA_rl_numba.py` | function | `_update_sma_weight_inplace` | 83 | njit |
| `solver/BSCASMA_rl_numba.py` | function | `_ctf_flip_probability_fast` | 101 | njit |
| `solver/BSCASMA_rl_numba.py` | function | `_repair_bscasma_row_inplace` | 115 | njit |
| `solver/BSCASMA_rl_numba.py` | function | `_state_bin` | 171 | njit |
| `solver/BSCASMA_rl_numba.py` | function | `_init_ones_count` | 180 | njit |
| `solver/BSCASMA_rl_numba.py` | function | `_init_density_state` | 190 | njit |
| `solver/BSCASMA_rl_numba.py` | function | `_copy_row_bits` | 215 | njit |
| `solver/BSCASMA_rl_numba.py` | function | `_update_density_state_for_row` | 221 | njit |
| `solver/BSCASMA_rl_numba.py` | function | `_population_density_from_counts` | 274 | njit |
| `solver/BSCASMA_rl_numba.py` | function | `_state_for_row` | 294 | njit |
| `solver/BSCASMA_rl_numba.py` | function | `_select_q_action_non_global` | 313 | njit |
| `solver/BSCASMA_rl_numba.py` | function | `_update_q_value` | 334 | njit |
| `solver/BSCASMA_rl_numba.py` | function | `_map_position_excluding` | 353 | njit |
| `solver/BSCASMA_rl_numba.py` | function | `_select_two_distinct_indices_excluding` | 360 | njit |
| `solver/BSCASMA_rl_numba.py` | function | `_sma_global_row` | 372 | njit |
| `solver/BSCASMA_rl_numba.py` | function | `_sma_local_row` | 401 | njit |
| `solver/BSCASMA_rl_numba.py` | function | `_sca_sin_row` | 435 | njit |
| `solver/BSCASMA_rl_numba.py` | function | `_sca_cos_row` | 459 | njit |
| `solver/BSCASMA_rl_numba.py` | function | `_bscasma_rl_main_loop_numba` | 483 | njit |
| `solver/BSCASMA_rl_numba.py` | class | `BRLSMASCARLNumbaCore` | 623 |  |
| `solver/BSCASMA_rl_numba.py` | method | `BRLSMASCARLNumbaCore.__init__` | 626 |  |
| `solver/BSCASMA_rl_numba.py` | method | `BRLSMASCARLNumbaCore.pseudo_utility` | 691 |  |
| `solver/BSCASMA_rl_numba.py` | method | `BRLSMASCARLNumbaCore.initial_pop` | 715 |  |
| `solver/BSCASMA_rl_numba.py` | method | `BRLSMASCARLNumbaCore.sort_pop_with_ids` | 728 |  |
| `solver/BSCASMA_rl_numba.py` | method | `BRLSMASCARLNumbaCore.run` | 740 |  |
| `solver/BSCASMA_rl_numba.py` | class | `BRLSMASCARLNumbaSolver` | 818 | dataclass |
| `solver/BSCASMA_rl_numba.py` | method | `BRLSMASCARLNumbaSolver.solve` | 819 |  |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_cp_list_cache_key` | 27 |  |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_item_eval_cache_key` | 39 |  |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_coerce_bool_param` | 62 |  |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_safe_efficiency` | 76 |  |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_sort_items_by_bucket_efficiency` | 85 |  |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_efficiency_group_count` | 90 |  |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_shuffle_efficiency_groups` | 108 |  |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_dual_efficiency_fallback` | 132 |  |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_build_lp_rc_item_eval_payload` | 167 |  |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_robust_minmax` | 227 |  |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_clean_efficiency_for_score` | 247 |  |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_bucket_score` | 258 |  |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_build_core_score_cp_payload` | 266 |  |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_repair_solution_by_order` | 306 |  |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_greedy_solution_by_order` | 341 |  |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_randomized_probe_solution` | 368 |  |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_freq_samples_and_rho` | 401 |  |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_build_freq_gated_v2_payload` | 418 |  |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_normalize_score` | 597 |  |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_safe_ratio_for_score` | 601 |  |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_lagrangian_multipliers_lite` | 609 |  |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_score_values_for_method` | 640 |  |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_build_named_score_cp_payload` | 679 |  |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_build_frequency_cp_payload` | 707 |  |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_solve_lp_bound_with_fixed_item` | 836 |  |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_build_sbl_lite_cp_payload` | 857 |  |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_parse_named_score_item_eval_method` | 921 |  |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_is_supported_item_eval_method` | 928 |  |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_sort_bscasma_rl_desc_deterministic_inplace` | 934 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_update_sma_weight_inplace` | 977 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_ctf_flip_probability_fast` | 995 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_clip01` | 1009 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_clip_symmetric_half` | 1018 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_guided_bucket_bias` | 1027 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_guided_probability` | 1036 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_init_row_resource_from_bits` | 1056 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_resource_excluding_item_inplace` | 1073 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_guided_slack_score` | 1086 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_set_guided_binary_bit_and_update_resource` | 1103 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_repair_bscasma_row_inplace` | 1120 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_repair_bscasma_row_dynamic_drop_inplace` | 1176 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_repair_bscasma_swap_once_inplace` | 1254 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_repair_bscasma_row_v2_inplace` | 1293 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_copy_row_to_work` | 1387 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_restore_work_to_row` | 1393 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_local_search_bscasma_row_inplace` | 1407 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_restart_bscasma_bucket_biased_row_inplace` | 1518 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_archive_hamming_distance` | 1566 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_archive_contains_vector` | 1582 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_archive_add_vector` | 1601 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_archive_add_row` | 1630 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_archive_select_donor` | 1655 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_path_relink_bscasma_inplace` | 1679 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_state_bin` | 1779 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_init_ones_count` | 1788 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_init_density_state` | 1798 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_copy_row_bits` | 1823 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_update_density_state_for_row` | 1829 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_population_density_from_counts` | 1882 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_state_for_row` | 1902 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_select_q_action_non_global` | 1921 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_update_q_value` | 1942 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_map_position_excluding` | 1961 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_select_two_distinct_indices_excluding` | 1968 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_sma_global_row` | 1980 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_sma_local_row` | 2009 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_sca_sin_row` | 2065 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_sca_cos_row` | 2111 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | function | `_bscasma_rl_main_loop_numba` | 2157 | njit |
| `solver/BSCASMA_rl_rc_numba.py` | class | `BRLSMASCARLRCNumbaCore` | 2585 |  |
| `solver/BSCASMA_rl_rc_numba.py` | method | `BRLSMASCARLRCNumbaCore.__init__` | 2588 |  |
| `solver/BSCASMA_rl_rc_numba.py` | method | `BRLSMASCARLRCNumbaCore.pseudo_utility` | 2870 |  |
| `solver/BSCASMA_rl_rc_numba.py` | method | `BRLSMASCARLRCNumbaCore._finish_initial_row` | 3061 |  |
| `solver/BSCASMA_rl_rc_numba.py` | method | `BRLSMASCARLRCNumbaCore._fill_initial_random_greedy_row` | 3066 |  |
| `solver/BSCASMA_rl_rc_numba.py` | method | `BRLSMASCARLRCNumbaCore._fill_initial_deterministic_greedy_row` | 3075 |  |
| `solver/BSCASMA_rl_rc_numba.py` | method | `BRLSMASCARLRCNumbaCore._fill_initial_lp_rounding_row` | 3083 |  |
| `solver/BSCASMA_rl_rc_numba.py` | method | `BRLSMASCARLRCNumbaCore._fill_initial_rcl_greedy_row` | 3093 |  |
| `solver/BSCASMA_rl_rc_numba.py` | method | `BRLSMASCARLRCNumbaCore.initial_pop` | 3107 |  |
| `solver/BSCASMA_rl_rc_numba.py` | method | `BRLSMASCARLRCNumbaCore.sort_pop_with_ids` | 3137 |  |
| `solver/BSCASMA_rl_rc_numba.py` | method | `BRLSMASCARLRCNumbaCore.run` | 3149 |  |
| `solver/BSCASMA_rl_rc_numba.py` | class | `BRLSMASCARLRCNumbaSolver` | 3306 | dataclass |
| `solver/BSCASMA_rl_rc_numba.py` | method | `BRLSMASCARLRCNumbaSolver.solve` | 3307 |  |
| `solver/BSCASMA_test_numba.py` | function | `_cp_list_cache_key` | 27 |  |
| `solver/BSCASMA_test_numba.py` | function | `_sort_bscasma_desc_deterministic_inplace` | 40 | njit |
| `solver/BSCASMA_test_numba.py` | function | `_update_sma_weight_inplace` | 79 | njit |
| `solver/BSCASMA_test_numba.py` | function | `_ctf_flip_probability_fast` | 97 | njit |
| `solver/BSCASMA_test_numba.py` | function | `_repair_bscasma_row_inplace` | 111 | njit |
| `solver/BSCASMA_test_numba.py` | function | `_policy_action` | 167 | njit |
| `solver/BSCASMA_test_numba.py` | function | `_map_position_excluding` | 179 | njit |
| `solver/BSCASMA_test_numba.py` | function | `_select_two_distinct_indices_excluding` | 186 | njit |
| `solver/BSCASMA_test_numba.py` | function | `_sma_global_row` | 198 | njit |
| `solver/BSCASMA_test_numba.py` | function | `_sma_local_row` | 227 | njit |
| `solver/BSCASMA_test_numba.py` | function | `_sca_sin_row` | 261 | njit |
| `solver/BSCASMA_test_numba.py` | function | `_sca_cos_row` | 285 | njit |
| `solver/BSCASMA_test_numba.py` | function | `_bscasma_test_main_loop_numba` | 309 | njit |
| `solver/BSCASMA_test_numba.py` | class | `BRLSMASCATestNumbaCore` | 416 |  |
| `solver/BSCASMA_test_numba.py` | method | `BRLSMASCATestNumbaCore.__init__` | 419 |  |
| `solver/BSCASMA_test_numba.py` | method | `BRLSMASCATestNumbaCore.init_best_method` | 475 |  |
| `solver/BSCASMA_test_numba.py` | method | `BRLSMASCATestNumbaCore.pseudo_utility` | 490 |  |
| `solver/BSCASMA_test_numba.py` | method | `BRLSMASCATestNumbaCore.initial_pop` | 514 |  |
| `solver/BSCASMA_test_numba.py` | method | `BRLSMASCATestNumbaCore.sort_pop_with_ids` | 527 |  |
| `solver/BSCASMA_test_numba.py` | method | `BRLSMASCATestNumbaCore.run` | 539 |  |
| `solver/BSCASMA_test_numba.py` | class | `BRLSMASCATestNumbaSolver` | 598 | dataclass |
| `solver/BSCASMA_test_numba.py` | method | `BRLSMASCATestNumbaSolver.solve` | 599 |  |
| `solver/BSCA_numba.py` | function | `_cp_list_cache_key` | 29 |  |
| `solver/BSCA_numba.py` | function | `_ctf_flip_probability_fast` | 42 | njit |
| `solver/BSCA_numba.py` | function | `_repair_bsca_row_inplace` | 56 | njit |
| `solver/BSCA_numba.py` | function | `_bsca_main_loop_numba` | 113 | njit |
| `solver/BSCA_numba.py` | class | `BSCANumbaCore` | 182 |  |
| `solver/BSCA_numba.py` | method | `BSCANumbaCore.__init__` | 187 |  |
| `solver/BSCA_numba.py` | method | `BSCANumbaCore.pseudo_utility` | 229 |  |
| `solver/BSCA_numba.py` | method | `BSCANumbaCore.initial_pop` | 252 |  |
| `solver/BSCA_numba.py` | method | `BSCANumbaCore.sort_pop` | 264 |  |
| `solver/BSCA_numba.py` | method | `BSCANumbaCore.run` | 273 |  |
| `solver/BSCA_numba.py` | class | `BSCANumbaSolver` | 322 | dataclass |
| `solver/BSCA_numba.py` | method | `BSCANumbaSolver.solve` | 325 |  |
| `solver/BSCA_rc_numba.py` | function | `_bsca_rc_main_loop_numba` | 33 | njit |
| `solver/BSCA_rc_numba.py` | class | `BSCARCNumbaCore` | 177 |  |
| `solver/BSCA_rc_numba.py` | method | `BSCARCNumbaCore.__init__` | 180 |  |
| `solver/BSCA_rc_numba.py` | method | `BSCARCNumbaCore.pseudo_utility` | 277 |  |
| `solver/BSCA_rc_numba.py` | method | `BSCARCNumbaCore._finish_initial_row` | 320 |  |
| `solver/BSCA_rc_numba.py` | method | `BSCARCNumbaCore._fill_initial_random_greedy_row` | 323 |  |
| `solver/BSCA_rc_numba.py` | method | `BSCARCNumbaCore._fill_initial_deterministic_greedy_row` | 332 |  |
| `solver/BSCA_rc_numba.py` | method | `BSCARCNumbaCore._fill_initial_lp_rounding_row` | 340 |  |
| `solver/BSCA_rc_numba.py` | method | `BSCARCNumbaCore._fill_initial_rcl_greedy_row` | 350 |  |
| `solver/BSCA_rc_numba.py` | method | `BSCARCNumbaCore.initial_pop` | 363 |  |
| `solver/BSCA_rc_numba.py` | method | `BSCARCNumbaCore.sort_pop` | 394 |  |
| `solver/BSCA_rc_numba.py` | method | `BSCARCNumbaCore.run` | 403 |  |
| `solver/BSCA_rc_numba.py` | class | `BSCARCNumbaSolver` | 467 | dataclass |
| `solver/BSCA_rc_numba.py` | method | `BSCARCNumbaSolver.solve` | 468 |  |
| `solver/BSMA.py` | function | `_digest_float_prefix` | 20 |  |
| `solver/BSMA.py` | function | `_argsort_pop_fit_desc_deterministic` | 25 |  |
| `solver/BSMA.py` | class | `BSMACore` | 44 |  |
| `solver/BSMA.py` | method | `BSMACore.__init__` | 47 |  |
| `solver/BSMA.py` | method | `BSMACore.pseudo_utility` | 98 |  |
| `solver/BSMA.py` | method | `BSMACore.initial_pop` | 113 |  |
| `solver/BSMA.py` | method | `BSMACore.repair` | 126 |  |
| `solver/BSMA.py` | method | `BSMACore.sort_pop` | 148 |  |
| `solver/BSMA.py` | method | `BSMACore.run` | 158 |  |
| `solver/BSMA.py` | class | `BSMASolver` | 243 | dataclass |
| `solver/BSMA.py` | method | `BSMASolver.solve` | 246 |  |
| `solver/BSMA_numba.py` | function | `_cp_list_cache_key` | 32 |  |
| `solver/BSMA_numba.py` | function | `_expect_mkp_problem_tensors` | 45 |  |
| `solver/BSMA_numba.py` | function | `_ctf_flip_probability_fast` | 60 | njit |
| `solver/BSMA_numba.py` | function | `_repair_row_inplace` | 75 | njit |
| `solver/BSMA_numba.py` | function | `_sort_pop_desc_deterministic_inplace` | 134 | njit |
| `solver/BSMA_numba.py` | function | `_map_position_excluding` | 171 | njit |
| `solver/BSMA_numba.py` | function | `_select_two_distinct_indices_excluding` | 178 | njit |
| `solver/BSMA_numba.py` | function | `_bsma_main_loop_numba` | 190 | njit |
| `solver/BSMA_numba.py` | class | `BSMANumbaCore` | 299 |  |
| `solver/BSMA_numba.py` | method | `BSMANumbaCore.__init__` | 304 |  |
| `solver/BSMA_numba.py` | method | `BSMANumbaCore.pseudo_utility` | 348 |  |
| `solver/BSMA_numba.py` | method | `BSMANumbaCore.initial_pop` | 371 |  |
| `solver/BSMA_numba.py` | method | `BSMANumbaCore.sort_pop` | 383 |  |
| `solver/BSMA_numba.py` | method | `BSMANumbaCore.run` | 392 |  |
| `solver/BSMA_numba.py` | class | `BSMANumbaSolver` | 444 | dataclass |
| `solver/BSMA_numba.py` | method | `BSMANumbaSolver.solve` | 447 |  |
| `solver/BSMA_rc_numba.py` | function | `_bsma_rc_global_row` | 34 | njit |
| `solver/BSMA_rc_numba.py` | function | `_bsma_rc_main_loop_numba` | 63 | njit |
| `solver/BSMA_rc_numba.py` | class | `BSMARCNumbaCore` | 226 |  |
| `solver/BSMA_rc_numba.py` | method | `BSMARCNumbaCore.__init__` | 229 |  |
| `solver/BSMA_rc_numba.py` | method | `BSMARCNumbaCore.pseudo_utility` | 327 |  |
| `solver/BSMA_rc_numba.py` | method | `BSMARCNumbaCore._finish_initial_row` | 370 |  |
| `solver/BSMA_rc_numba.py` | method | `BSMARCNumbaCore._fill_initial_random_greedy_row` | 373 |  |
| `solver/BSMA_rc_numba.py` | method | `BSMARCNumbaCore._fill_initial_deterministic_greedy_row` | 382 |  |
| `solver/BSMA_rc_numba.py` | method | `BSMARCNumbaCore._fill_initial_lp_rounding_row` | 390 |  |
| `solver/BSMA_rc_numba.py` | method | `BSMARCNumbaCore._fill_initial_rcl_greedy_row` | 400 |  |
| `solver/BSMA_rc_numba.py` | method | `BSMARCNumbaCore.initial_pop` | 413 |  |
| `solver/BSMA_rc_numba.py` | method | `BSMARCNumbaCore.sort_pop` | 444 |  |
| `solver/BSMA_rc_numba.py` | method | `BSMARCNumbaCore.run` | 453 |  |
| `solver/BSMA_rc_numba.py` | class | `BSMARCNumbaSolver` | 519 | dataclass |
| `solver/BSMA_rc_numba.py` | method | `BSMARCNumbaSolver.solve` | 520 |  |
| `solver/registry.py` | class | `Solver` | 12 |  |
| `solver/registry.py` | method | `Solver.solve` | 13 |  |
| `solver/registry.py` | class | `SolverRegistry` | 20 |  |
| `solver/registry.py` | method | `SolverRegistry.__init__` | 23 |  |
| `solver/registry.py` | method | `SolverRegistry.register` | 27 |  |
| `solver/registry.py` | method | `SolverRegistry.get` | 34 |  |
| `solver/registry.py` | method | `SolverRegistry.create` | 40 |  |
| `solver/registry.py` | class | `StubMaxIterationsSolver` | 45 | dataclass |
| `solver/registry.py` | method | `StubMaxIterationsSolver.solve` | 48 |  |
