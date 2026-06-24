# `valid/stage1_validation.py`

## 模組責任

`valid/stage1_validation.py` 是 refactor 專用的 stage-1 驗證腳本。它會用一小組 smoke scenario 同時跑舊版腳本與新 CLI 路徑，檢查 baseline objective、refactor 可重現性與差異分類，角色介於研究驗證與遷移驗收之間。

## 公開入口/主要類型

- 主要資料型別：`ValidationScenario`、`ComparableResult`
- 主要入口：`build_smoke_scenarios()`、`run_stage1_validation(...)`
- 主要 helper：`ensure_problem_yaml(...)`、`run_refactor_once(...)`、`check_refactor_reproducible(...)`、`run_old_script(...)`、`classify_diff(...)`

## 主要資料結構與資料契約

- `ValidationScenario` 定義 dataset/problem/solver/seeds。
- `ComparableResult` 只保留 old/new 可直接比較的欄位：`best_objective`、`feasible`、`stop_reason`、`seed`。
- old baseline 目前透過舊腳本輸出的 CSV 與 log 收集；new path 則直接呼叫 `cli.run.main`。
- 同一 seed 下 `run_refactor_once(...)` 必須可重播，否則 refactor 本身就不穩定。

## 資料流與控制流

1. `build_smoke_scenarios()` 準備最小 scenario 集。
2. `ensure_problem_yaml(...)` 確保 raw dataset 已轉成標準 problem YAML。
3. `run_old_script(...)` 以 subprocess 包裝 legacy 腳本，收集 stdout/stderr。
4. `collect_old_baseline_best_objective(...)` 從舊版 output CSV 萃取 baseline objective。
5. `run_refactor_once(...)` 與 `check_refactor_reproducible(...)` 跑新 CLI 路徑並檢查同 seed 穩定性。
6. `classify_diff(...)` 對 baseline / refactor 結果分類。
7. `run_stage1_validation(...)` 統籌整批 scenario，寫出 baseline log 與比較結果。

## 失敗路徑與例外條件

- 舊腳本 timeout、problem YAML 轉換失敗、baseline CSV 找不到、refactor 結果不穩定都屬重要失敗訊號。
- baseline 缺失不一定是例外，但會被分類為 `baseline_missing`，表示目前無法完成嚴格比對。

## 副作用與資源生命週期

- 會在 `output/stage1_validation/<run_id>/` 下建立 baseline/refactor 子目錄、log 與比較結果。
- 會呼叫舊版腳本 subprocess，也會觸發新 CLI 的正式 output 寫出。

## 與其他模組的關係

- 上游依賴 `cli.convert` / `converter` 來確保 YAML 存在。
- 新路徑依賴 `cli.run.main`；舊路徑依賴 `old/main1weish.py` 等 legacy script。
- `tests/test_stage1_validation.py` 只測它的 helper；真正的舊新對照驗收由本腳本完成。

## 對應函式索引與閱讀順序

1. `_resolve_app_entry`
2. `ValidationScenario`
3. `ComparableResult`
4. `build_smoke_scenarios`
5. `ensure_problem_yaml`
6. `run_refactor_once`
7. `check_refactor_reproducible`
8. `run_old_script`
9. `collect_old_baseline_best_objective`
10. `classify_diff`
11. `run_stage1_validation`

## 核心函式與 helper 說明

### `_resolve_app_entry` / `ValidationScenario` / `ComparableResult`

`_resolve_app_entry` 讓 stage1 validation 可注入真實 CLI 或測試 stub；`ValidationScenario` 與 `ComparableResult` 則定義 smoke scenario 與可比較輸出的最小資料面。

### `build_smoke_scenarios` / `ensure_problem_yaml`

前者提供最小 smoke 測試矩陣，後者在跑 refactor 路徑前先把 raw dataset 轉成標準 problem YAML。這組函式把「題目可被新 CLI 讀取」變成顯式前置條件。

### `run_refactor_once` / `check_refactor_reproducible`

這兩個函式是新流程驗證核心。`run_refactor_once` 直接呼叫 `cli.run.main` 並抽取可比較輸出，`check_refactor_reproducible` 則檢查同 seed 連跑兩次是否一致。

### `run_old_script` / `collect_old_baseline_best_objective` / `classify_diff` / `run_stage1_validation`

這組函式負責 legacy 路徑：執行舊腳本、收集 baseline、分類差異，最後寫出 stage1 對照結果。它們是舊版與新版之間最後一層整體驗收工具。
