# `cli/convert/__main__.py`

## 模組責任

`cli/convert/__main__.py` 是 `python -m mkp.cli.convert` 的薄啟動層，只負責把模組執行導到 `cli/convert/main.py::main()`。

## 公開入口/主要類型

- `main`

## 主要資料結構與資料契約

- 本檔不定義 CLI schema。
- 它假設真正的命令列解析與轉檔流程完全由 `.main` 處理。

## 資料流與控制流

1. 使用者執行 `python -m mkp.cli.convert`。
2. Python 進入本檔。
3. 本檔 import `.main.main` 並直接呼叫。

## 失敗路徑與例外條件

- `.main.main` 若拋出例外，這一層不攔截。

## 副作用與資源生命週期

- 本檔本身無副作用；所有 I/O 都在 `.main`。

## 與其他模組的關係

- 唯一下游是 `cli/convert/main.py`。

## 對應函式索引與閱讀順序

1. `main`
