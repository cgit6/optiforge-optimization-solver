# `solver/__init__.py`

## 模組責任

`solver/__init__.py` 目前只作為 package 標記與高層語意註記，告知 `solver/` 目錄承載演算法實作與註冊表。

## 公開入口/主要類型

- 無明確 re-export API。

## 主要資料結構與資料契約

- 上游通常直接 import 具體 solver 模組或 `solver.registry`，而不是從 `solver.__init__` 取符號。
- 這個檔案的契約主要是 package 存在與語意說明，而非對外 API。

## 資料流與控制流

1. Python import `solver.*` 時先辨識此 package。
2. 具體控制流在各 solver 模組與 `solver.registry` 中發生。

## 失敗路徑與例外條件

- 幾乎沒有業務邏輯；錯誤多半來自子模組 import 或 solver builder 註冊。

## 副作用與資源生命週期

- 無副作用。

## 與其他模組的關係

- 上游：`engine.builders`、`machine.core`、測試模組。
- 下游：`solver/` 內所有具體演算法檔。

## 對應函式索引與閱讀順序

1. package docstring
2. [`solver/registry.py`](registry.md)
3. 各具體 solver 模組
