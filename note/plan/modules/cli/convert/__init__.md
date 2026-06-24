# `cli/convert/__init__.py`

## 模組責任

`cli/convert/__init__.py` 是 `cli.convert` package 的對外匯出面。它把 converter CLI 主入口、converter registry 入口與內建 parser 名稱集中暴露。

## 公開入口/主要類型

- `build`
- `main`
- `getConverter`
- `listConverters`
- `register`
- `parseWeish`、`parseWeing`、`parsePb`、`parsePet`、`parseSent`、`parseHp`、`parseCb`、`parseGk`

## 主要資料結構與資料契約

- `register` 其實是從 `converter` package 重新匯出的 registry decorator。
- `parse*` 系列函式不是 CLI parser，而是 raw benchmark parser。
- `__all__` 是 `mkp.cli.convert` 對外承諾的 package API。

## 資料流與控制流

1. 上游 import `mkp.cli.convert`。
2. package 把 `.main` 的 CLI 入口與 `.register` 的 dataset parser 重新匯出。
3. 外部可直接使用這一層存取 converter registry 與 parser 函式。

## 失敗路徑與例外條件

- 若 `converter` registry 或 `.register` 內 parser 名稱漂移，這一層 import 會直接失敗。

## 副作用與資源生命週期

- import 時會觸發 `cli/convert/register.py`，因此也會完成內建 converter 的註冊。

## 與其他模組的關係

- 上游：CLI 呼叫端、tests、研究腳本可直接使用這層 package API。
- 下游：`cli/convert/main.py`、`cli/convert/register.py`、`converter/__init__.py`。

## 對應函式索引與閱讀順序

1. `build`
2. `main`
3. package-level parser exports
4. `__all__`
