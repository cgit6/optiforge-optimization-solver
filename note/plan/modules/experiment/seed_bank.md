# `experiment/seed_bank.py`

## 模組責任

`experiment/seed_bank.py` 管理 `seed_bank.json` 的格式、讀寫與查詢。它讓 `cli.exp` 產生的可重播 run seed 能被 `cli.replay` 重新消費。

## 公開入口/主要類型

- `variant_key(...)`
- `solver_config_snapshot(...)`
- `problem_seed_entry(...)`
- `build_seed_bank(...)`
- `write_seed_bank(...)`
- `load_seed_bank(...)`
- `validate_seed_bank(...)`
- `matching_problem_entries(...)`
- `variant_config(...)`

## 主要資料結構與資料契約

- `variant_key(...)` 固定把 variant 表示成 `solver_id:param_set_index` 字串。
- `solver_config_snapshot(...)` 從 solver config 擷取可重播所需欄位，避免把執行期污染欄位原封不動寫回。
- `problem_seed_entry(...)` 描述單一 problem 的 collected repeat index、run seeds 與可用 variant keys。
- seed bank payload 主要包含：
  - `source`
  - `variants`
  - `problems`

## 資料流與控制流

1. `Experiment._record_seed_bank_problem(...)` 先為每個機器 variant 建立 snapshot 與 problem entry。
2. `build_seed_bank(...)` 把 source、variants、problems 組成正式 payload。
3. `write_seed_bank(...)` 寫成 JSON。
4. `load_seed_bank(...)` 讀檔後立即呼叫 `validate_seed_bank(...)`。
5. `cli.replay` 用 `variant_config(...)` 取某個 variant 的 config，再用 `matching_problem_entries(...)` 找可重播題目。

## 失敗路徑與例外條件

- seed bank JSON 不是 mapping、欄位結構錯誤、缺少必要鍵、problem entry 與 variant 對不上，都應在 `validate_seed_bank(...)` 失敗。
- `variant_config(...)` 查不到指定 variant 會丟 `KeyError`。
- `solver_config_snapshot(...)` 若輸入 config 結構不符合 solver config 契約，會在後續 replay snapshot 建立時暴露問題。

## 副作用與資源生命週期

- 主要副作用是 JSON 讀寫。
- 不持有長期資源；讀寫完畢後就交還 payload 給 `experiment.experiment` 或 `cli.replay`。

## 與其他模組的關係

- 上游：`experiment.experiment` 寫 seed bank。
- 下游：`cli.replay.main` 讀 seed bank 並重建 `RunTask`。
- 與 `engine.configs.SolverConfigsSnapshot.from_configs(...)` 相連，因為 replay 最終要把 variant config 還原成快照。

## 對應函式索引與閱讀順序

1. `variant_key`
2. `solver_config_snapshot`
3. `problem_seed_entry`
4. `build_seed_bank`
5. `write_seed_bank`
6. `load_seed_bank`
7. `validate_seed_bank`
8. `matching_problem_entries`
9. `variant_config`
10. `_json_safe`
