# `cli/run/__main__.py`

## 模組責任

`cli/run/__main__.py` 是 `python -m mkp.cli.run` 的薄啟動層。

## 公開入口/主要類型

- `main`

## 主要資料結構與資料契約

- 本檔不建立 `ExperimentSpec`，也不碰 bundle / output。
- 真正命令列解析與執行行為都在 `.main` 與 `.support`。

## 資料流與控制流

1. 使用者執行 `python -m mkp.cli.run`。
2. 本檔 import `.main.main`。
3. 直接呼叫 `main()`。

## 失敗路徑與例外條件

- `.main.main` 若拋出錯誤，這一層不攔截。

## 副作用與資源生命週期

- 本檔本身無副作用。

## 與其他模組的關係

- 唯一下游是 `cli/run/main.py`。

## 對應函式索引與閱讀順序

1. `main`
