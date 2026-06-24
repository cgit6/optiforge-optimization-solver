# `converter/converter.py`

## 模組責任

`converter/converter.py` 負責把原始 `.dat/.txt` benchmark 轉成記憶體中的 `ProblemModel` 或正式的 problem YAML。它是 `data/` 到 `configs/problems/` 的主要橋接層。

## 公開入口/主要類型

- `ProblemPayloadConverter`
- `dat_file_path(...)`
- `yaml_file_path(...)`
- `reshape(...)`
- `transformToMomery(...)`
- `transformToYaml(...)`

## 主要資料結構與資料契約

- parser 必須回傳至少包含：
  - `items`
  - `dim`
  - `values`
  - `weights`
  - `capacities`
  - `best_known`
- `yaml_file_path(...)` 目前固定寫到 `configs/problems/mkp/<dataset>/<problem_id>.yaml`，表示這條轉換路徑目前是 MKP 專用。
- `transformToYaml(...)` 會產生 `problem_type: mkp`。

## 資料流與控制流

1. `dat_file_path(...)` 與 `yaml_file_path(...)` 組出來源與目的路徑。
2. `reshape(...)` 呼叫 parser，把 raw payload 轉成 `ProblemModel`。
3. `transformToMomery(...)` 是「只轉成記憶體模型、不寫檔」的包裝入口。
4. `transformToYaml(...)` 會：
   - 讀 raw payload
   - 建立 YAML body
   - 用 `ruamel.yaml` 寫到正式 problem config 目錄
5. `_flow_sequence(...)` 與 `_weights_flow_rows(...)` 控制 YAML 中 list/2D list 的格式。

## 失敗路徑與例外條件

- parser 若回傳缺欄位或型別不相容的 payload，會在 `reshape(...)` 或 YAML 序列化時失敗。
- source raw file 路徑不存在時，錯誤通常由 parser 自己或檔案讀取階段拋出。
- 目前 `reshape(...)` 內有註解指出「返回格式無法兼容所有問題」，表示這個模組仍偏向 MKP 專用。

## 副作用與資源生命週期

- `transformToYaml(...)` 會建立目錄並覆寫輸出 YAML。
- `transformToMomery(...)` 不寫檔，只回傳轉換後的 model。

## 與其他模組的關係

- 上游：`cli.convert` 與 dataset parser registry。
- 下游：`engine.repository` 後續讀的 problem YAML，正是由這裡寫出。
- 依賴：`problem.ProblemModel`、`ruamel.yaml`。

## 對應函式索引與閱讀順序

1. `ProblemPayloadConverter`
2. `_flow_sequence`
3. `_weights_flow_rows`
4. `dat_file_path`
5. `yaml_file_path`
6. `reshape`
7. `transformToMomery`
8. `transformToYaml`
