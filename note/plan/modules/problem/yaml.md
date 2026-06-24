# `problem/yaml.py`

## 模組責任

`problem/yaml.py` 提供 problem YAML loader 共用的最小驗證 helper。它不負責讀檔或建 model，只負責欄位存在性與路徑 identity 一致性。

## 公開入口/主要類型

- `require_fields(...)`
- `validate_identity(...)`

## 主要資料結構與資料契約

- `require_fields(...)` 接受：
  - `data: dict[str, Any]`
  - `fields: tuple[str, ...]`
  - `file_path: Path`
- `validate_identity(...)` 驗證：
  - `problem_id`
  - `dataset`
  - `problem_type`
- 這裡的 `problem_type` 若 YAML 缺欄位，會回退到呼叫端傳入的預期值；其目的是讓 loader 可把「缺欄位」與「值不符」都收斂成一致檢查。

## 資料流與控制流

1. 具體 loader 先把 YAML parse 成 `dict`。
2. 呼叫 `require_fields(...)` 檢查必要欄位是否存在。
3. 再呼叫 `validate_identity(...)` 比對路徑與內容中的 `problem_id`、`dataset`、`problem_type`。
4. 驗證通過後，才由各 problem family 建立 `Problem` model。

## 失敗路徑與例外條件

- 缺少必要欄位時，`require_fields(...)` 丟 `ValueError`。
- identity 任一欄位不一致時，`validate_identity(...)` 丟 `ValueError`。
- 本模組不判斷欄位型別、shape 或數值範圍；這些責任留給具體 problem loader 與 model `__post_init__()`。

## 副作用與資源生命週期

- 無 I/O 副作用。
- 功能刻意保持最小，避免每個 problem family 重新複製錯誤訊息格式。

## 與其他模組的關係

- 上游：[`problem/mkp.py`](mkp.md)、[`problem/tsp.py`](tsp.md) 直接依賴這兩個 helper。
- 下游：它不依賴其他 problem family，只依賴 `Path` 與基礎 mapping 契約。

## 核心函式與 helper 說明

### `require_fields(data, fields, file_path)`

- 目的：以一致錯誤格式檢查 YAML 是否具備必要欄位。
- 角色：它是所有 problem loader 的第一層 schema gate，專注在「欄位存在性」，不處理型別與 shape。

### `validate_identity(data, problem_type, dataset, problem_id, file_path)`

- 目的：確認 YAML 內容中的 identity 與路徑命名一致。
- 失敗路徑：`problem_id`、`dataset`、`problem_type` 任一值不符就丟 `ValueError`。
- 修改風險：若拿掉這層檢查，catalog 掃描與 repository 載入就可能把錯誤檔名或錯誤目錄 silently 當成有效題目。

## 對應函式索引與閱讀順序

1. `require_fields`
2. `validate_identity`
