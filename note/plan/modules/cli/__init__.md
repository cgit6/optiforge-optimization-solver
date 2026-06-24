# `cli/__init__.py`

## 模組責任

`cli/__init__.py` 是 `mkp.cli` package 標記檔，只負責宣告這一層是命令列子套件。

## 公開入口/主要類型

- package marker

## 主要資料結構與資料契約

- 本檔不定義 CLI parser 或命令。
- 真正的入口在 `cli.run`、`cli.exp`、`cli.convert`、`cli.replay`。

## 資料流與控制流

- 無控制流；角色僅是 package 邊界。

## 失敗路徑與例外條件

- 若 package 邊界不存在，`mkp.cli.*` 匯入與 `python -m mkp.cli.*` 解析都可能異常。

## 副作用與資源生命週期

- 無 I/O、無執行期狀態。

## 與其他模組的關係

- 下游是四個實際 CLI 子命令 package：`run`、`exp`、`convert`、`replay`。

## 對應函式索引與閱讀順序

1. package marker
