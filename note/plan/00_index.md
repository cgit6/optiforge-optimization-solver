# OptiForge Optimization Solver 文件索引

本目錄是專案的正式說明文件區。文件以程式碼現況為準，既有 `note/*.md` 與 `log/*.md` 會被引用或摘要，但不在這裡直接覆寫。

## 閱讀路線

1. 維護者先讀 `11_dashboard.md`，確認目前文件品質、缺口、優先補強順序與最近一次重評結果。
2. 建立系統心智模型時，讀 `01_system_architecture.md` 與 `02_execution_flows.md`。
3. 要調整設定或資料，讀 `03_data_and_config.md`。
4. 要找模組責任，讀 `04_module_guide.md`。
5. 要查每個 class/function/private helper，讀 `05_api_reference.md` 或 `inventory/function_coverage_checklist.md`。
6. 要改 solver，讀 `06_solver_algorithms.md` 與 `10_maintenance_playbooks.md`。
7. 要改實驗搜尋/evaluator，讀 `07_experiment_and_evaluation.md`。
8. 要確認測試或歷史腳本，讀 `08_validation_and_tests.md` 與 `09_legacy_old.md`。

## 文件地圖

| File | Purpose |
|---|---|
| `00_index.md` | 本索引與維護規則。 |
| `01_system_architecture.md` | 系統分層、核心資料契約、主資料流。 |
| `02_execution_flows.md` | `cli.run`、`cli.exp`、`cli.convert`、`cli.replay` 流程。 |
| `03_data_and_config.md` | problem YAML、solver YAML、exp cfg、data/output 格式。 |
| `04_module_guide.md` | 每個目錄/模組責任、依賴與輸出。 |
| `05_api_reference.md` | 全量 class/function/private helper 參考。 |
| `06_solver_algorithms.md` | solver 與 Numba core 的演算法視角說明。 |
| `07_experiment_and_evaluation.md` | experiment collection、evaluator、seed bank。 |
| `08_validation_and_tests.md` | tests/valid 覆蓋範圍與驗證方式。 |
| `09_legacy_old.md` | `old/` 與 notebook 歷史資料。 |
| `10_maintenance_playbooks.md` | 新增 solver/problem/evaluator/config 的操作手冊。 |
| `11_dashboard.md` | 文件品質看板、分數、缺口、重評規則與更新紀錄。 |
| `inventory/` | 靜態掃描清單、coverage checklist、設定與資料集索引。 |

## 掃描摘要

- Python 檔案數：`136`
- Python 總行數：`32254`
- Class 數：`130`
- Function/method 數：`1191`
- Solver config 數：`10`
- Problem YAML 數：`337`
- Raw data 檔案數：`511`
- 既有 note/log 檔案數：`31`

## 維護規則

- 新功能合併後，先更新 `inventory/` 與 `05_api_reference.md`，再更新敘述文件。
- 任何 `note/plan` 正式介紹文件更新後，都必須同步重評並更新 `11_dashboard.md`。
- 文件中若描述到程式碼行為，以目前程式碼為準；若既有筆記不同，標記「既有筆記差異」。
- 大型 benchmark 資料只記錄格式、目錄、檔案數與轉換關係，不複製完整資料內容。
- `old/` 是歷史參考，不應被文件描述成目前主流程。
