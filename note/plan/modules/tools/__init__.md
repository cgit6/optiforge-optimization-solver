# `tools/__init__.py`

## 模組責任

`tools/__init__.py` 是 `mkp.tools` package 標記檔，表示這一層存放統計、輸出、solver YAML 載入與研究輔助工具。

## 公開入口/主要類型

- package marker

## 主要資料結構與資料契約

- 本檔本身不 re-export 任何工具函式。
- 各工具應由其子模組直接 import，而不是依賴 `mkp.tools` 聚合面。

## 資料流與控制流

- 無控制流；角色僅是 package 邊界。

## 失敗路徑與例外條件

- 若 package 邊界缺失，`mkp.tools.*` 匯入可能異常。

## 副作用與資源生命週期

- 無 I/O、無狀態。

## 與其他模組的關係

- 下游包含 `stat`、`show`、`solver_config_loader`、CTF helper 與研究腳手架工具。

## 對應函式索引與閱讀順序

1. package marker
