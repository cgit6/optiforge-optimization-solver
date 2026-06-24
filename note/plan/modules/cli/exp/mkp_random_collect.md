# `cli/exp/mkp_random_collect.py`

## 模組責任

`cli/exp/mkp_random_collect.py` 提供 deterministic 的 repeat 節流 evaluator。它的目的不是比較 solver 表現，而是在 collect 過程中為每個 problem 只挑部分 repeat，讓實驗覆蓋保持分散，同時避免每次執行都因隨機抽樣而改變收集結果。

## 公開入口/主要類型

- `MIN_REPEAT_INTERVAL`
- `MAX_REPEAT_INTERVAL`
- `mkp_random_collect_every_n_5_20_evaluator(...)`

## 主要資料結構與資料契約

- 輸入使用的欄位很少：
  - `dataset_setting.dataset`
  - `problem_id`
  - `repeat_index`
- evaluator 不檢查 `variant_summaries`、`candidate_result` 或 baseline；它完全不關心 solver 品質，只關心 repeat 是否落在被選中的位置。
- 區間長度固定在 `[5, 20]` 之間，但每個 `(dataset, problem_id)` 會用穩定雜湊得到不同 interval。
- 每個 interval block 只允許一個 selected offset，因此單一 block 最多收一筆 repeat。

## 資料流與控制流

1. `_problem_interval(...)` 以 `(dataset, problem_id)` 經 `_stable_int(...)` 映射成 `[5, 20]` 的穩定 interval。
2. 用 `repeat_index // interval` 算出當前 block index。
3. `_selected_block_offset(...)` 再用 `(dataset, problem_id, interval, block_index)` 算出這個 block 被選中的 offset。
4. evaluator 只在 `repeat_index % interval == selected_offset` 時回傳 `PASS`。
5. 回傳的 `details` 會明確寫出 interval、block、selected offset 與被接受的 repeat index，方便重現與除錯。

## 失敗路徑與例外條件

- 這個模組沒有業務型失敗分支；不符合抽樣位置時只是正常回傳 `FAIL`。
- 它不檢查 dataset/problem 是否存在於 repository，因為這些驗證已在 `experiment.config` 和 collect 主流程完成。
- 若上游提供的 `dataset` 或 `problem_id` 不穩定，輸出也會跟著改變；這是 deterministic hash evaluator 的隱含契約。

## 副作用與資源生命週期

- 純函式模組，唯一外部依賴是 `hashlib.blake2b`。
- 沒有全域快取，也沒有跨回合狀態；相同 `dataset/problem_id/repeat_index` 一定得到相同判決。

## 與其他模組的關係

- 上游：`experiment.experiment._evaluate_candidate_round(...)`。
- 配置來源：`exp_cfg.yaml` 只要選到這個 evaluator 名稱，就會把 collect acceptance 改成節流模式。
- 與其他 evaluator 的角色差異：
  - `mkp_base*` / `mkp_qpso` / `mkp_calibration` 依表現指標接受或拒絕。
  - 本模組只做 deterministic sampling，不評估品質。

## 核心函式與 helper 說明

### `mkp_random_collect_every_n_5_20_evaluator(input_data)`

- 目的：用 deterministic hash 規則在每個 repeat block 中只放行一筆。
- 控制流：先算 problem-specific interval，再算當前 block 的 selected offset，最後比對 `repeat_index % interval`。
- 角色：它調節 collect 密度，而不是評估 solver 品質。

### `_problem_interval(...)` / `_selected_block_offset(...)`

- 目的：把 `(dataset, problem_id, block)` 映射成穩定的 interval 與選取 offset。
- 維護意義：這些 helper 保證相同題目在不同執行批次會得到相同的抽樣位置。

### `_stable_int(*parts)`

- 角色：整個 deterministic sampling 規則的根。
- 注意事項：只要 hash payload 拼接規則不變，抽樣結果就可重現；若改了字串拼法，舊 seed bank 的收集邏輯也會一起漂移。

## 對應函式索引與閱讀順序

1. `MIN_REPEAT_INTERVAL`
2. `MAX_REPEAT_INTERVAL`
3. `mkp_random_collect_every_n_5_20_evaluator`
4. `_problem_interval`
5. `_selected_block_offset`
6. `_stable_int`
