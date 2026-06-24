# `tools/ctf_numba.py`

## 模組責任

`tools/ctf_numba.py` 提供 Numba hot-loop 專用的 scalar CTF 分派函式。它存在的理由是把 Python 字串選擇轉成整數 `ctf_id`，讓主迴圈保持 `nopython`。

## 公開入口/主要類型

- `ctf_flip_probability(...)`

## 主要資料結構與資料契約

- `ctf_id` 的語意完全對齊 [`tools/continuous_to_binary.py`](continuous_to_binary.md)：
  - `0 = tanh_abs`
  - `1 = sigmoid_s0`
  - `...`
  - `11 = abs_pow_2`
- 回傳值必須與 Python 側 `flip_probability(...)` 對同一 `ctf_id` 的結果一致。

## 資料流與控制流

1. solver adapter 先在 Python 側把 `ctf` 名稱轉成 `ctf_id`。
2. Numba main loop 在 row update 或 bit sampling 時呼叫 `ctf_flip_probability(ctf_id, x)`。
3. 函式用 `if ctf_id == ...` 的靜態分支完成數學映射，避免字典查表或 Python callback。

## 失敗路徑與例外條件

- 這裡不主動對未知 `ctf_id` 報錯；無效 id 會回退到 `abs(tanh(x))`。
- 因此真正的輸入驗證責任在 Python 側 `parse_ctf_kind(...)`，而不是這個 Numba helper。
- 若 Python / Numba 兩側公式不同步，錯誤會表現為 solver 行為漂移，而不是明確例外。

## 副作用與資源生命週期

- `@njit(cache=True)` 會觸發 Numba compile/cache 行為。
- 無檔案 I/O 或其他外部副作用。

## 與其他模組的關係

- 上游：Numba solver core。
- 下游：無；它是 hot-loop 最底層 helper。
- 架構上必須與 [`tools/continuous_to_binary.py`](continuous_to_binary.md) 成對維護。

## 對應函式索引與閱讀順序

1. `ctf_flip_probability`
