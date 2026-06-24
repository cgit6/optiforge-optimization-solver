# `cli/replay/__init__.py`

## 模組責任

`cli/replay/__init__.py` 是 `cli.replay` package 的對外匯出面，把 replay CLI 常用入口集中暴露。

## 公開入口/主要類型

- `build_parser`
- `parser`
- `main`

## 主要資料結構與資料契約

- 這一層不重新定義 replay 的資料契約。
- `build_parser` / `parser` / `main` 都直接來自 `cli/replay/main.py`。

## 資料流與控制流

1. 上游 import `mkp.cli.replay`。
2. package 重新暴露 parser 與 main。
3. 真正的 seed bank 讀取、group replay 與 output 寫出仍在 `.main`。

## 失敗路徑與例外條件

- 若 `.main` 中符號改名，這一層 import 會立即失敗。

## 副作用與資源生命週期

- 無直接副作用。

## 與其他模組的關係

- 上游：外部程式、tests、CLI 啟動層。
- 下游：`cli/replay/main.py`。

## 對應函式索引與閱讀順序

1. `build_parser`
2. `parser`
3. `main`
4. `__all__`
