# `converter/register.py`

## 模組責任

`converter/register.py` 管理 raw benchmark parser 的註冊表。它讓 `cli.convert` 能用字串 key 選擇對應的 dataset parser。

## 公開入口/主要類型

- `ConverterFn`
- `register(...)`
- `getConverter(...)`
- `listConverters()`

## 主要資料結構與資料契約

- `ConverterFn` 是 `Callable[[Path], dict[str, Any]]`。
- `_CONVERTERS` 是模組內部全域表，key 為 converter 名稱。
- `register(name)` 回傳 decorator，供 parser 定義時直接註冊。

## 資料流與控制流

1. dataset parser 模組在 import 時呼叫 `@register("...")`。
2. `cli.convert` 根據 CLI 參數呼叫 `getConverter(name)`。
3. converter 取得 parser 後，再交給 `transformToYaml(...)` 或 `reshape(...)`。

## 失敗路徑與例外條件

- 空字串名稱不能註冊。
- 重複註冊同名 converter 會失敗。
- `getConverter(...)` 查不到名稱時會丟 `KeyError`。

## 副作用與資源生命週期

- 主要副作用是改寫模組內部全域 `_CONVERTERS`。
- 生命週期與進程相同；通常在 CLI 啟動時隨 import 完成註冊。

## 與其他模組的關係

- 上游：`cli.convert.register` 或 dataset parser 定義檔。
- 下游：`converter.converter` 與 `cli.convert.main` 會用這個 registry 選 parser。

## 對應函式索引與閱讀順序

1. `ConverterFn`
2. `register`
3. `getConverter`
4. `listConverters`
