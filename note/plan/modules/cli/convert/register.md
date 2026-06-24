# `cli/convert/register.py`

## 模組責任

`cli/convert/register.py` 定義各 raw benchmark parser，並在 import 時把它們註冊到 converter registry。它處理的是「題庫原始數字格式 -> 統一 problem payload」的轉換，不直接寫 YAML。

## 公開入口/主要類型

- `parseWeish(...)`
- `parseWeing(...)`
- `parsePb(...)`
- `parsePet(...)`
- `parseSent(...)`
- `parseHp(...)`
- `parseCb(...)`
- `parseGk(...)`

其餘 helper 也是本模組邏輯主體：

- `_read_numbers(...)`
- `_optional_best_known(...)`
- `_parse_flat_problem(...)`

## 主要資料結構與資料契約

- WEISH / WEING / PB / PET / SENT / HP / CB 共用 `_parse_flat_problem(...)` 契約：
  - header: `items`, `dim`, `best_known`
  - body: `values`, dimension-major `weights`, `capacities`
- `parseGk(...)` 使用不同格式：
  - header 只有 `items`, `dim`
  - 每個 item 一列 `value + dim 個 weights`
  - 不提供 `best_known`
- 所有 parser 最終都回傳統一 mapping：
  - `items`
  - `dim`
  - `best_known`
  - `values`
  - `weights`
  - `capacities`

## 資料流與控制流

1. `_read_numbers(...)` 先把 raw 檔全部拆成數字序列，並把 `float` 形式數字壓回 `int`。
2. `_parse_flat_problem(...)` 依固定長度公式切片 header、values、weights、capacities，再把 dimension-major 權重轉成 item-major。
3. 各 `parse*` 函式只負責指定 dataset name 或 GK 特有切片邏輯。
4. 模組尾端用 `register("...")(parseXxx)` 做 import-time 註冊。

## 失敗路徑與例外條件

- raw 檔不存在時，`_read_numbers(...)` 會丟 `FileNotFoundError`。
- 檔案內有非數字內容時丟 `ValueError`。
- header 長度不足、總長度不符、values/weights/capacities 切片尺寸不符，都會丟 `ValueError`。
- `parseGk(...)` 與 flat family 的資料排列不同，若誤用 converter key，通常會在長度檢查階段失敗。

## 副作用與資源生命週期

- 主要副作用是讀取 raw benchmark 檔。
- import 本模組時會修改 converter registry；這是必要的啟動副作用。
- 本模組不建立 `ProblemModel`、不寫 shared memory、也不直接寫 YAML。

## 與其他模組的關係

- 上游：[`cli/convert/main.py`](main.md) 透過 `getConverter(...)` 取用這裡註冊的 parser。
- 下游：[`converter/register.py`](../../converter/register.md) 保存 registry；[`converter/converter.py`](../../converter/converter.md) 會拿 parser 輸出繼續寫 YAML。
- `parseGk(...)`、`_parse_flat_problem(...)` 共同承擔 `data/` 到 `configs/problems/` 之間最前段的 schema 收斂責任。

## 對應函式索引與閱讀順序

1. `_read_numbers`
2. `_optional_best_known`
3. `_parse_flat_problem`
4. `parseWeish`
5. `parseWeing`
6. `parsePb`
7. `parsePet`
8. `parseSent`
9. `parseHp`
10. `parseCb`
11. `parseGk`
12. import-time `register(...)` 呼叫
