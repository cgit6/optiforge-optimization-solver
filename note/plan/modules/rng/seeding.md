# `rng/seeding.py`

## 模組責任

`rng/seeding.py` 提供最底層的 deterministic seed 派生函式。它把 `(base_seed, problem identity, repeat_index)` 轉成穩定的 32-bit task seed。

## 公開入口/主要類型

- `TASK_SEED_VERSION`
- `validate_base_seed(...)`
- `stable_task_seed(...)`

## 主要資料結構與資料契約

- `TASK_SEED_VERSION` 參與 hash payload，代表目前 task seed 規格版本。
- `stable_task_seed(...)` 的輸入欄位固定為：
  - `base_seed`
  - `problem_type`
  - `dataset`
  - `problem_id`
  - `repeat_index`
- 輸出會被限制在 `np.int32` 最大值範圍內。

## 資料流與控制流

1. 上游先用 `validate_base_seed(...)` 確認 seed 非負。
2. `stable_task_seed(...)` 建立排序固定的 JSON payload。
3. 用 `blake2b(digest_size=8)` 計算 hash。
4. 轉成 little-endian unsigned int，再映射到 `int32` 範圍。

## 失敗路徑與例外條件

- `base_seed < 0` 時直接丟 `ValueError`。
- 其餘欄位型別若不合預期，多半會在上游 context 或 JSON 序列化前就被限制。

## 副作用與資源生命週期

- 無 I/O 副作用。
- 重要副作用是：只要 `TASK_SEED_VERSION` 或 payload 欄位集合改變，所有歷史 task seed 都會重算，這會影響 replay 與實驗可重現性。

## 與其他模組的關係

- 上游：`rng.strategy.DerivedPerProblemSeedStrategy`。
- 下游：`machine.core` 取得的 `RunTask.task_seed` 最終來源就是這裡。

## 對應函式索引與閱讀順序

1. `TASK_SEED_VERSION`
2. `validate_base_seed`
3. `stable_task_seed`
