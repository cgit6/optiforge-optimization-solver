# `converter/__init__.py`

## 模組責任

`converter/__init__.py` 是資料轉換子系統的封裝入口，重新匯出 converter registry 與 raw-data 轉 YAML 的主要函式。

## 公開入口/主要類型

- `ProblemPayloadConverter`
- `dat_file_path(...)`
- `reshape(...)`
- `transformToMomery(...)`
- `transformToYaml(...)`
- `yaml_file_path(...)`
- `getConverter(...)`
- `listConverters()`
- `register(...)`

## 主要資料結構與資料契約

- package-level API 讓 `cli.convert` 只需要 import `converter` 就能取得轉換與 registry 能力。
- 對外仍保留目前拼字 `transformToMomery(...)`，文件需如實記錄，不自行更名。

## 資料流與控制流

1. `cli.convert` 或其他上游 import 這個 package。
2. `converter.__init__` 把 `converter.py` 與 `register.py` 的 API 對外暴露。
3. 呼叫端可先 `getConverter(...)` 拿 parser，再走 `transformToYaml(...)` 或 `transformToMomery(...)`。

## 失敗路徑與例外條件

- 本模組本身不做驗證；錯誤主要來自實際轉換與 registry 子模組。

## 副作用與資源生命週期

- 無直接副作用。
- 生命週期重點是維持 package 匯出面的一致性。

## 與其他模組的關係

- 上游：`cli.convert`。
- 下游：`converter.converter` 與 `converter.register`。

## 對應函式索引與閱讀順序

1. `ProblemPayloadConverter`
2. `dat_file_path`
3. `reshape`
4. `transformToMomery`
5. `transformToYaml`
6. `yaml_file_path`
7. `getConverter`
8. `listConverters`
9. `register`
