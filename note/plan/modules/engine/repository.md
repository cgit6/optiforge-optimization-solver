# `engine/repository.py`

## 模組責任

`engine/repository.py` 是 problem YAML 的正式讀取入口。它負責把 `configs/problems/.../*.yaml` 轉成具體 `Problem` model，並以 registry 驗證 problem type、loader 與模型型別的一致性。

## 公開入口/主要類型

- `ProblemRepository`
  - `resolve_path(...)`
  - `load(...)`
  - `read_metadata(...)`

## 主要資料結構與資料契約

- YAML 路徑契約：`<problem_root>/<problem_type>/<dataset>/<problem_id>.yaml`。
- cache key 契約：`(problem_type, dataset, problem_id)`。
- `read_metadata(...)` 只讀取 problem identity、encoding、direction 與 path，不建立完整 `Problem` model。
- `load(...)` 則一定會把 YAML 經 registry loader 轉為 `Problem` 子類別。

## 資料流與控制流

1. `resolve_path(...)` 先把 problem identity 轉成 YAML 路徑。
2. `load(...)` 先查 `_cache`，避免重複 I/O 與重複建模。
3. 若 cache miss，讀 YAML，檢查 `problem_type` 是否與請求一致。
4. 透過 `ProblemRegistry.get(...)` 取得對應 `ProblemTypeSpec`。
5. 呼叫 `spec.loader(...)` 建立 model，接著用 `registry.validate_model(...)` 驗證型別與 identity。
6. 成功後再寫回 `_cache`，避免競態下重複建立不同 instance。
7. `read_metadata(...)` 只做輕量 identity/capability 驗證，供 CLI 與 experiment config fail-fast 使用。

## 失敗路徑與例外條件

- 未提供 `problem_root` 或 `config_root` 會丟 `TypeError`。
- YAML 檔不存在會丟 `FileNotFoundError`。
- YAML 不是 mapping、格式錯誤、problem_id/dataset/problem_type 不一致，會丟 `ValueError`。
- `problem_type` 未註冊或 loader 回傳錯誤 model type，會由 registry 層拋錯。

## 副作用與資源生命週期

- 本模組的副作用主要是檔案讀取與 cache 寫入。
- `_cache_lock` 保護 model cache；`_yaml_parse_lock` 保護 `ruamel.yaml` parser，避免多執行緒解析競態。
- repository 不管理 shared memory；shared memory 生命週期從 `ProblemBank.build(...)` 才開始。

## 與其他模組的關係

- 上游：`cli.run.support.validate_execute_args(...)`、`experiment.config`、`engine.assembly` 都先透過 repository 驗證題目。
- 依賴：`problem.registry`、具體 problem loader，如 `problem.mkp.load_mkp_problem(...)`。
- 下游：`ProblemBank.build(...)` 直接吃 repository 回傳的 `Problem` model。

## 核心函式與 helper 說明

### `resolve_path(...)`

- 目的：把 `(problem_type, dataset, problem_id)` 轉成 canonical YAML 路徑。
- 資料契約：repository 不做搜尋或模糊匹配；只接受 canonical path。
- 架構角色：`read_metadata(...)` 與 `load(...)` 都先走這個 helper，所以路徑規則只有這一個真實來源。

### `load(...)`

- 目的：正式建立 `Problem` model。
- 控制流：
  1. 先查 `_cache`
  2. cache miss 才讀 YAML
  3. 驗 `problem_type`
  4. 取 `ProblemTypeSpec`
  5. 呼叫 `spec.loader(...)`
  6. `registry.validate_model(...)`
  7. 再寫回 `_cache`
- 副作用：檔案讀取與 cache 寫入。
- 重要設計：先在 lock 外讀檔與建模，最後再回 lock 寫入，避免長時間把 cache lock 卡住。
- 修改風險：若把 lock 範圍包太大，平行讀取會退化；若把最後的 second-check 拿掉，競態時可能建立多份同題目 model。

### `read_metadata(...)`

- 目的：提供輕量級 identity/capability 檢查，而不建完整 model。
- 主要用途：`cli.run` compatibility check、`experiment.config` fail-fast 驗證。
- 與 `load(...)` 的差異：
  - `read_metadata(...)` 回傳 dict
  - `load(...)` 回傳 `Problem`
  - `read_metadata(...)` 不進 cache
- 風險：若未來 loader 層的預設 `encoding` / `direction` 規則有變，這裡也要同步更新，否則 metadata 驗證會和實際 model 行為分叉。

### `_read_yaml(...)`

- 目的：統一 `ruamel.yaml` 安全讀取與錯誤訊息格式。
- 副作用：唯一的實際檔案 I/O 發生在這裡。
- 設計重點：`_yaml_parse_lock` 只保護 parser，不保護 repository 整體流程；這讓多執行緒仍可並發做存在檢查與 cache 查詢。

## 對應函式索引與閱讀順序

1. `ProblemRepository`
2. `ProblemRepository.resolve_path`
3. `ProblemRepository.load`
4. `ProblemRepository.read_metadata`
5. `ProblemRepository._read_yaml`
