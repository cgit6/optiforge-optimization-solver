# `tools/continuous_to_binary.py`

## 模組責任

`tools/continuous_to_binary.py` 定義 continuous-to-flip（CTF）轉換函式族，負責把連續值轉成與 `Uniform(0, 1)` 比較的標量。這是多個 binary solver 在 Python 層解析 `params["ctf"]` 時的共同契約。

## 公開入口/主要類型

- `CTF_KINDS`
- `CTF_ID_BY_NAME`
- `flip_probability(...)`
- `parse_ctf_kind(...)`

主要 helper：

- `_logistic(...)`
- `_tanh_abs(...)`
- `_sigmoid_s0(...)`
- `_sigmoid_s1(...)`
- `_sigmoid_s2(...)`
- `_sigmoid_s3(...)`
- `_atan_scaled(...)`
- `_tanh_signed(...)`
- `_inv_sqrt_one_plus_x2(...)`
- `_erf_scaled(...)`
- `_abs_pow_16(...)`
- `_abs_pow_17(...)`
- `_abs_pow_2(...)`

## 主要資料結構與資料契約

- `CTF_KINDS` 的順序是正式契約，必須和 [`tools/ctf_numba.py`](ctf_numba.md) 中 `ctf_id` 分支一一對齊。
- `parse_ctf_kind(...)` 回傳 `(kind_name, ctf_id)`，讓 Python adapter 與 Numba hot-loop 可共用同一個選擇結果。
- 若 solver `params` 沒有提供 `ctf`，預設是 `tanh_abs` / `ctf_id = 0`。

## 資料流與控制流

1. solver adapter 從 config `params` 呼叫 `parse_ctf_kind(...)`。
2. Python solver 可直接用 `flip_probability(...)`。
3. Numba solver 則把 `ctf_id` 傳給 `ctf_flip_probability(...)`，避免在 hot-loop 內做字串分派。
4. 各個 `_sigmoid_*`、`_atan_*`、`_abs_pow_*` helper 只承擔數學轉換本身。

## 失敗路徑與例外條件

- `flip_probability(...)` 收到未知 `kind` 會丟 `KeyError`。
- `parse_ctf_kind(...)` 收到空字串或未知名稱會丟 `ValueError`。
- 若有人只改 Python 側順序、沒同步改 Numba 側，系統不一定立刻報錯，但會造成演算法語意漂移；這是本模組最大的維護風險。

## 副作用與資源生命週期

- 無 I/O 副作用。
- 主要是提供純函式數學映射，供 solver 啟動與測試共用。

## 與其他模組的關係

- 上游：`BSMA*`、`BSCA*`、`BSCASMA*` solver adapters 解析 `ctf` 參數。
- 下游：[`tools/ctf_numba.py`](ctf_numba.md) 必須與這裡保持同一順序與數學語意。
- `tests/test_continuous_to_binary.py` 驗證 Python / Numba 對齊。

## 對應函式索引與閱讀順序

1. `CTF_KINDS`
2. `CTF_ID_BY_NAME`
3. `_logistic`
4. 各 `_*` CTF helper
5. `flip_probability`
6. `parse_ctf_kind`
