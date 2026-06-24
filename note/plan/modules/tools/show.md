# `tools/show.py`

## 模組責任

`tools/show.py` 是正式輸出層。它不重跑 solver，也不重新計算 validation，只把 `MachineResult` / `SimulatorResult` 轉成 `runs.csv`、`runs.json`、`summary.csv`、`summary.json`。

## 公開入口/主要類型

- `write_simulator_result(...)`
- `_summary_meta(...)`
- `_reset_variant_output_dir(...)`
- `_write_runs_csv(...)`
- `_write_runs_json(...)`
- `_write_summary(...)`

## 主要資料結構與資料契約

- 輸出目錄契約：
  `output/<experiment_name>/<solver_id>/param_<index>/`
- 單一 variant 的 run 明細來自 `tools.stat.machine_result_entries(...)`。
- 單一 variant 的 summary 由 `tools.stat.summarize(...)` 產生。
- `variant_metadata` 讓上游將 experiment-specific metadata 混進 `SummaryMeta.experiment`，例如 collect seeds 或 replay 來源。

## 資料流與控制流

1. `write_simulator_result(...)` 逐一走訪 `SimulatorResult.machine_results`。
2. 每個 variant 先轉成 `ResultEntry` bucket。
3. `_reset_variant_output_dir(...)` 先清掉該 variant 舊輸出，再重建目錄。
4. `_write_runs_csv(...)` 與 `_write_runs_json(...)` 輸出逐 run 明細。
5. `_summary_meta(...)` 建立 summary metadata。
6. `_write_summary(...)` 輸出 `summary.json` 與 `summary.csv`。

## 失敗路徑與例外條件

- `experiment_name` 空白時，`write_simulator_result(...)` 直接失敗。
- 若上游傳入無法 JSON 化的 metadata，會在 `_json_safe(...)` 或 `json.dump(...)` 階段暴露問題。
- 每次輸出都會先刪 variant 目錄，因此若目錄中有人工附加檔案，也會被一併移除。

## 副作用與資源生命週期

- 這是檔案系統副作用最重的輸出模組：
  - 刪除既有 variant output dir
  - 建立新目錄
  - 寫 CSV/JSON
- 不持有長期資源；寫完即結束。

## 與其他模組的關係

- 上游：`cli.run.support`、`experiment.experiment`、`cli.replay.main` 都用這個模組落地輸出。
- 依賴：`tools.stat` 提供 `ResultEntry` 與 `SummaryReport`。
- 下游：任何人工檢閱、分析腳本、replay 驗證都以這裡的檔案為輸入。

## 核心函式與 helper 說明

### `write_simulator_result(...)`

- 目的：把 `SimulatorResult` 依 variant 落地成 `runs.csv`、`runs.json`、`summary.csv`、`summary.json`。
- 控制流：
  1. 依 `(solver_id, param_set_index)` 排序 machine results
  2. `machine_result_entries(...)` 產出 runs bucket
  3. `_reset_variant_output_dir(...)` 清舊目錄
  4. 寫 runs CSV/JSON
  5. `_summary_meta(...)` + `summarize(...)` 建 summary
  6. `_write_summary(...)` 寫 summary CSV/JSON
- 最大副作用：每個 variant output dir 都會被整個重建，舊檔會消失。
- 修改風險：這是全專案正式輸出格式的中心入口，CSV 欄位名或資料清洗方式一改，tests、分析腳本、replay 比對都會受影響。

### `_summary_meta(...)`

- 目的：把 `MachineResult` 與上游給的 `variant_metadata` 收斂成 `SummaryMeta`。
- 角色：這裡是 experiment-specific metadata 混入 summary 的唯一正式入口，例如 collect seeds、dataset experiment id、replay 來源。

### `_reset_variant_output_dir(...)`

- 目的：確保每個 variant 輸出目錄是乾淨重建，而不是增量覆寫。
- 風險：若使用者手動把額外分析檔丟進 variant 目錄，也會被這裡刪掉。

### `_write_runs_csv(...)` / `_write_runs_json(...)`

- `_write_runs_csv(...)`：
  - 先把 entries 經 `_entry_to_csv_dict(...)` 扁平成列
  - 若 `entries` 為空，用 `_empty_entry()` 推出穩定欄位順序
- `_write_runs_json(...)`：
  - 保留較接近原始 schema 的 JSON 結構
  - 透過 `_entry_to_json_dict(...)` 做 tuple/list/dict 正規化

### `_write_summary(...)`

- 目的：同時寫 `summary.json` 與 `summary.csv`。
- `summary.json`：保留完整巢狀 schema。
- `summary.csv`：透過 `_summary_to_csv_rows(...)` 壓成一列 overall + 多列 group rows。

### `_entry_to_json_dict(...)` / `_entry_to_csv_dict(...)`

- `_entry_to_json_dict(...)`：`asdict(entry)` 後再走 `_json_safe(...)`。
- `_entry_to_csv_dict(...)`：
  - 把 `metadata` 抽出為 `metadata_json`
  - 其餘欄位用 `_csv_cell(...)` 轉成 CSV 可承載值
- 這兩個 helper 決定 JSON 與 CSV 對同一 run 的表示差異。

### `_summary_to_csv_rows(...)`

- 目的：把 `SummaryReport` 轉成穩定欄位順序的 flat rows。
- 設計：
  - 第一列 `row_type = overall`
  - 其後每題一列 `row_type = group`
  - `meta_json` 每列都帶上，讓 CSV 仍保留 variant/context metadata

### `_empty_entry()` / `_json_safe(...)` / `_csv_cell(...)`

- `_empty_entry()`：在零 run 情況下提供欄位模板，避免 CSV 欄位順序漂移。
- `_json_safe(...)`：把 tuple 遞迴轉成 JSON-safe list，並處理巢狀 dict/list。
- `_csv_cell(...)`：把 tuple/list/dict 轉成 JSON 字串，其他 scalar 保持原值。

## 對應函式索引與閱讀順序

1. `write_simulator_result`
2. `_summary_meta`
3. `_reset_variant_output_dir`
4. `_entry_to_json_dict`
5. `_entry_to_csv_dict`
6. `_write_runs_csv`
7. `_write_runs_json`
8. `_write_summary`
9. `_summary_to_csv_rows`
10. `_empty_entry`
11. `_json_safe`
12. `_csv_cell`
