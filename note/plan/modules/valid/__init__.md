# `valid/__init__.py`

## 模組責任

`valid/__init__.py` 是 `mkp.valid` package 的標記檔，讓 population trace、equivalence、benchmark、stage1 validation 這些研究驗證腳本可以用套件路徑被匯入與 `python -m` 執行。

## 公開入口/主要類型

- package marker

## 主要資料結構與資料契約

本檔本身不定義資料模型；它的主要契約是讓 `tests/test_stage1_validation.py` 與各種 `mkp.valid.*` 執行路徑能穩定解析 package。

## 資料流與控制流

無控制流；角色僅是 Python import system 的 package 邊界。

## 失敗路徑與例外條件

若 package 標記不存在，`mkp.valid.*` 的模組匯入與 `python -m mkp.valid...` 路徑可能失敗。

## 副作用與資源生命週期

無 I/O、無狀態。

## 與其他模組的關係

它是 `valid/` 研究驗證腳本與 `tests/test_stage1_validation.py` 的共同 package 基礎。

## 對應函式索引與閱讀順序

1. package marker

## 核心函式與 helper 說明

### package marker

`valid/__init__.py` 沒有本地函式、class 或 CLI 入口；它的唯一責任是把 `valid/` 宣告成可匯入 package，讓 `mkp.valid.*` 模組、研究驗證腳本與對應測試可以走穩定的匯入路徑。
