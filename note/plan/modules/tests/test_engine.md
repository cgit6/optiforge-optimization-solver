# `tests/test_engine.py`

## 模組責任

`test_engine.py` 驗證 `Engine.build(...)` 與 `SimulationBundle` 的整合責任，包括 catalog 掃描、problem load、bundle 拆分與顯式 seed strategy 要求。

## 公開入口/主要類型

- pytest 自動發現測試
- 主要 helper：`_write_problem_yaml`、`_write_solver_yaml`
- 主要測試群：bundle 建立、multi-solver split、seed strategy 強制、catalog/problem YAML fail-fast、worker curriculum cache

## 主要資料結構與資料契約

只有 spec 內實際用到的 problem 必須成功載入；未使用 catalog 檔可壞但不可污染 build；bundle 產出的 simulators 必須可跑且 solver snapshot 正確。

## 資料流與控制流

helpers 先寫 problem/solver YAML，再走 `Engine.build(...)`；測試依序檢查 runnable bundle、`new_simulators()`、seed strategy 強制、invalid YAML 選擇性失敗與 worker curriculum cache 行為。

## 失敗路徑與例外條件

experiment problem YAML 無效、unknown best-known、catalog 缺題或未提供顯式 seed strategy 都必須 fail-fast。

## 副作用與資源生命週期

使用 `tmp_path` 建立臨時 repository/solver config，可能寫出少量 output。

## 與其他模組的關係

目標模組是 `mkp.engine`、`mkp.engine.repository`、`mkp.engine.models`、`mkp.rng` 與 `mkp.tools.show`。

## 對應函式索引與閱讀順序

1. `_write_problem_yaml`
2. `_write_solver_yaml`
3. `test_engine_build_returns_bundle_with_runnable_simulator`
4. `test_bundle_new_simulators_splits_multi_solver_spec`
5. `test_engine_build_requires_explicit_seed_strategy`
6. `test_engine_build_fails_when_experiment_problem_yaml_is_invalid`
7. `test_engine_build_succeeds_when_unused_catalog_yaml_is_invalid`
8. `test_engine_build_fails_when_experiment_problem_has_unknown_best_known`
9. `test_engine_build_fails_when_experiment_problem_not_in_catalog`
10. `test_worker_curriculum_does_not_call_problem_repository_load_after_engine_build`

## 核心函式與 helper 說明

### `_write_problem_yaml` / `_write_solver_yaml`

這兩個 helper 建立最小 catalog 與 solver config，讓 `Engine.build(...)` 的測試聚焦在組裝邏輯，而不是外部檔案雜訊。它們也是多個 CLI/engine 測試共用的基礎治具。

### `test_engine_build_returns_bundle_with_runnable_simulator`

這是 engine 主鏈的 smoke test。它驗證 build 後拿到的 `SimulationBundle` 不只是靜態資料，而是真的能產出 simulator、跑 sequential path，並寫出結果檔。

### `test_bundle_new_simulators_splits_multi_solver_spec`

這個測試固定 bundle 拆分語意：當 spec 含多個 solver 或 param set 時，`new_simulators()` 必須依變體拆成獨立 simulator，而不是在同一實例裡混跑多組設定。

### build fail-fast 與 cache 邊界測試群

`test_engine_build_requires_explicit_seed_strategy`、`test_engine_build_fails_when_experiment_problem_yaml_is_invalid`、`test_engine_build_succeeds_when_unused_catalog_yaml_is_invalid`、`test_engine_build_fails_when_experiment_problem_has_unknown_best_known`、`test_engine_build_fails_when_experiment_problem_not_in_catalog` 共同描述 engine 的載入邊界。`test_worker_curriculum_does_not_call_problem_repository_load_after_engine_build` 則補上 cache 契約，避免 worker runtime 再回頭碰 repository。
