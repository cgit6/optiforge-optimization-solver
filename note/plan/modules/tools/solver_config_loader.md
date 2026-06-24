# `tools/solver_config_loader.py`

## 模組責任

`tools/solver_config_loader.py` 是 solver YAML 的底層載入器。它負責讀檔、驗證 schema，並把多 param-set YAML 正規化成單一 variant config。

## 公開入口/主要類型

- `SolverConfigLoader`
  - `load(...)`
  - `load_all(...)`

## 主要資料結構與資料契約

- solver YAML 必須包含：
  - `solver_id`
  - `solver_class`
  - `stop_condition`
  - `params`
  - `capabilities`
- `stop_condition.type` 目前只允許：
  - `max_iterations`
  - `max_seconds`
- `load(...)` 回傳單一 param set 的 normalized config，會補上 `param_set_index`，並把 `params` 收斂成單一 mapping。

## 資料流與控制流

1. `load(...)` / `load_all(...)` 先定位 `configs/solvers/<solver_id>.yaml`。
2. `_read_yaml(...)` 用 `ruamel.yaml` 讀檔。
3. `_validate_schema(...)` 驗證 top-level schema、stop condition、params list 與 capabilities。
4. `_normalize_config(...)` 依指定 param set index 挑出一組 `params`，回傳單一 variant config。

## 失敗路徑與例外條件

- 檔案不存在會丟 `FileNotFoundError`。
- YAML 格式不是 mapping、缺欄位、`solver_id` 與檔名不符、stop condition 不合法、`params` 不是非空 list，都會失敗。
- `param_set_index` 超界時，`_normalize_config(...)` 會丟 `ValueError`。

## 副作用與資源生命週期

- 主要副作用是讀 `configs/solvers/*.yaml`。
- `_yaml_parse_lock` 用來保護共享 parser，避免多執行緒解析競態。

## 與其他模組的關係

- 上游：`cli.run.support`、`experiment.config`、`engine.configs`。
- 下游：`SolverConfigsSnapshot` 把這裡的輸出轉成執行期快照。

## 對應函式索引與閱讀順序

1. `SolverConfigLoader`
2. `SolverConfigLoader.load`
3. `SolverConfigLoader.load_all`
4. `SolverConfigLoader._read_yaml`
5. `SolverConfigLoader._validate_schema`
6. `SolverConfigLoader._normalize_config`
