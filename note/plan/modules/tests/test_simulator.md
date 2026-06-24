# `tests/test_simulator.py`

## 模組責任

`test_simulator.py` 驗證單 task `Simulator` 路徑：solver snapshot 載入、run_task 執行、validation 寫回與 RNG 注入。

## 公開入口/主要類型

- pytest 自動發現測試
- 類型/測試 double：`RecordingSolver`
- 主要 helper：`_offset_rng_factory`、`_write_problem_yaml`、`_write_solver_yaml`、`_build_simulator`

## 主要資料結構與資料契約

`RunTask` 執行後必須回傳帶 `ValidationReport` 的 row；相同 task seed 要可重播，且自訂 RNG factory 必須真的被使用。

## 資料流與控制流

使用 `RecordingSolver`、臨時 repository 與 solver YAML 建 simulator，再測 successful run、seed reproducibility、injected RNG、problem load fail-fast 與 missing solver YAML。

## 失敗路徑與例外條件

problem load 錯誤若不 fail-fast、solver snapshot 若缺 YAML 仍能建出 simulator，後續 batch 路徑也會失真。

## 副作用與資源生命週期

會在 `tmp_path` 寫 problem/solver YAML，可能產生少量 output。

## 與其他模組的關係

目標模組是 `mkp.simulator`、`mkp.engine.bank`、`mkp.engine.repository`、`mkp.engine.configs`、`mkp.machine`、`mkp.rng` 與 `mkp.tools.show`。

## 對應函式索引與閱讀順序

1. `RecordingSolver`
2. `_offset_rng_factory`
3. `_write_problem_yaml`
4. `_write_solver_yaml`
5. `_build_simulator`
6. `test_run_task_success_writes_result_and_returns_validation`
7. `test_run_task_rng_seed_is_reproducible`
8. `test_run_task_uses_injected_rng_factory`
9. `test_run_task_fail_fast_when_problem_load_fails`
10. `test_solver_snapshot_build_fails_when_solver_dir_has_no_yaml`

## 核心函式與 helper 說明

### `RecordingSolver` / `_offset_rng_factory`

`RecordingSolver` 提供可預測的 `SolveResult`，`_offset_rng_factory` 則故意偏移 seed 以測試注入式 RNG 工廠是否真的被 simulator 採用。這兩者一起保護 `Simulator` 對 solver 與 RNG 的介面邊界。

### `_write_problem_yaml` / `_write_solver_yaml` / `_build_simulator`

這組 helper 建立最小 simulator 測試環境，包含 catalog、solver config、registry 與 output root。它們把 setup 集中後，讓各測試專注在單一 runtime 契約。

### `test_run_task_success_writes_result_and_returns_validation`

這是 simulator 單 task 執行的核心測試。它一次驗證 solver 執行、validation 建立、row 寫出，以及 `tools.show` 的輸出欄位是否完整。

### seed / RNG / fail-fast 測試群

`test_run_task_rng_seed_is_reproducible` 與 `test_run_task_uses_injected_rng_factory` 保護 seed 與 RNG 注入語意；`test_run_task_fail_fast_when_problem_load_fails`、`test_solver_snapshot_build_fails_when_solver_dir_has_no_yaml` 則固定兩個常見故障點：problem load 與 solver snapshot。
