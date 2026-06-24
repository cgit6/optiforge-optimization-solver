# `tests/test_continuous_to_binary.py`

## 模組責任

`test_continuous_to_binary.py` 驗證 continuous-to-binary transfer function parser 與 Python/Numba flip 行為一致性。

## 公開入口/主要類型

- pytest 自動發現測試
- 主要測試群：`test_parse_ctf_default`、`test_parse_ctf_explicit`、`test_parse_unknown_raises`、`test_flip_matches_numba`

## 主要資料結構與資料契約

`parse_ctf(...)` 必須接受預設與顯式 CTF，拒絕未知 key；Numba helper 的 flip 行為必須與純 Python 版本一致。

## 資料流與控制流

先測 parser，再用固定輸入比對 Python 與 Numba helper 的 binary conversion 結果。

## 失敗路徑與例外條件

未知 CTF key 未拋錯，或 Numba/非 Numba 轉換行為不一致，都代表演算法 helper 漂移。

## 副作用與資源生命週期

純函式測試，無 I/O。

## 與其他模組的關係

目標模組是 `mkp.tools.continuous_to_binary` 與 `mkp.tools.ctf_numba`，它直接保護 solver hot-loop 依賴的轉換函式。

## 對應函式索引與閱讀順序

1. `test_parse_ctf_default`
2. `test_parse_ctf_explicit`
3. `test_parse_unknown_raises`
4. `test_flip_matches_numba`

## 核心函式與 helper 說明

### `test_parse_ctf_default` / `test_parse_ctf_explicit` / `test_parse_unknown_raises`

這組測試固定 `parse_ctf_kind(...)` 的字串解析契約：沒給值時回預設、給明確名稱時回正確 index、未知名稱時 fail-fast。它們保護的是 solver config 到 hot-loop 之間的轉換層。

### `test_flip_matches_numba`

這個參數化測試把 Python `flip_probability(...)` 與 Numba `ctf_flip_probability(...)` 對齊。它的角色不是測數學公式漂亮與否，而是確保 Python/Numba 兩條實作在所有支援的 CTF kind 上數值一致。
