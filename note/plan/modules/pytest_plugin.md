# `pytest_plugin.py`

## 模組責任

`pytest_plugin.py` 是 repo 根層級的 pytest 啟動修正器。它解決從專案子目錄執行 `pytest` 時，預設不會自動收集 `<root>/tests` 的問題。

## 公開入口/主要類型

- `pytest_load_initial_conftests(...)`

## 主要資料結構與資料契約

- 這是 pytest hook，不是一般函式 API。
- 重要輸入：
  - `early_config`
  - `parser`
  - `args`
- 它只在「從子目錄啟動、沒有顯式給測試路徑、不是 `--help`/`--version`」的情況下修改 `args`。

## 資料流與控制流

1. 取 `early_config.rootpath` 與 invocation directory。
2. 若目前就是 repo root，直接退出。
3. 若使用者帶了 `--help`、`--version` 或顯式 `file_or_dir`，直接退出。
4. 若 `<root>/tests` 存在，將其插入 `args[0]`，讓 pytest 仍能收集主測試目錄。

## 失敗路徑與例外條件

- 若 `rootpath` 不存在或 pytest 啟動環境沒有提供相關欄位，函式會安靜返回，不主動報錯。
- 如果未來 pytest 的 `early_config` 結構變動，這個 hook 可能失效；目前沒有額外相容層。

## 副作用與資源生命週期

- 直接修改 pytest 啟動參數 `args`。
- 不讀寫 repo 檔案，也不建立長生命週期資源。

## 與其他模組的關係

- 上游：pytest 啟動流程自動載入。
- 下游：所有 `tests/` 模組都間接受益，因為它提高從子目錄執行測試時的收集一致性。

## 對應函式索引與閱讀順序

1. `pytest_load_initial_conftests`
