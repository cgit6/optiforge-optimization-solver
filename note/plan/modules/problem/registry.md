# `problem/registry.py`

## 模組責任

`problem/registry.py` 是 problem type 的註冊中心。它把 YAML loader、shared memory packer/attacher、model type、encoding 與 direction 等靜態定義綁在一起。

## 公開入口/主要類型

- `ProblemShmPack` protocol
- `ProblemTypeSpec`
- `ProblemRegistry`
- `registryFromSpecs(...)`

## 主要資料結構與資料契約

- `ProblemTypeSpec` 是單一 problem type 的完整定義：
  - `problem_type`
  - `encoding`
  - `direction`
  - `model_type`
  - `loader`
  - `yaml_required_fields`
  - `make_shm_pack`
  - `attach_shm_pack`
- `ProblemShmPack` protocol 表示「可以被 worker attach 回 `Problem` model 的序列化包」。

## 資料流與控制流

1. 啟動時先建立 `ProblemRegistry`。
2. 每個 problem family 用 `register(...)` 註冊一個 `ProblemTypeSpec`。
3. `ProblemRepository.load(...)` 用 registry 找 loader。
4. `ProblemBank.build(...)` 用 registry 找 `make_shm_pack(...)`。
5. worker initializer 則用 registry 找 `attach_shm_pack(...)`，把 pack 重建為 `Problem`。

## 失敗路徑與例外條件

- 重複註冊同一個 `problem_type` 會失敗。
- `model_type` 不是 `Problem` 子類別會丟 `TypeError`。
- `get(...)` 查詢未註冊類型會丟 `KeyError`。
- `validate_model(...)` 會檢查 loader 回傳型別與 `model.problem_type`；不一致時直接中止。

## 副作用與資源生命週期

- 無外部資源副作用。
- registry 主要保存靜態型別資訊，生命週期通常與本次進程相同。

## 與其他模組的關係

- 上游：`problem.__init__` 或 builder 函式會建立 registry。
- 下游：`engine.repository`、`engine.bank`、worker shared memory attach 全部依賴這裡的 spec。
- 與 `problem.interface` 緊密耦合，因為 registry 以 `Problem` 為型別邊界。

## 核心函式與 helper 說明

### `ProblemRegistry.register(spec)`

- 目的：把某個題型的 loader、shared memory pack/attach、方向與編碼契約註冊成單一 `ProblemTypeSpec`。
- 控制流：檢查 `problem_type` 非空、不可重複、`model_type` 必須繼承 `Problem`，最後把 `direction` 正規化後存入 registry。
- 失敗路徑：重複註冊會丟 `ValueError`；`model_type` 不合法時丟 `TypeError`。
- 修改風險：這裡是 runtime 題型清單的中心；若放寬驗證，錯誤會延後到 repository 或 worker attach。

### `ProblemRegistry.get(problem_type)`

- 目的：取回某個題型的完整規格。
- 角色：`ProblemRepository`、`ProblemBank`、worker initializer 都用它找到對應 loader 或 shm attacher。
- 失敗路徑：未註冊題型直接丟 `KeyError`，避免 fallback 到錯誤 loader。

### `ProblemRegistry.validate_model(model, problem_type)`

- 目的：確認 loader 回傳的 model 同時符合 registry 中宣告的 `model_type` 與 `problem_type`。
- 在流程中的角色：它是 YAML 載入與 typed runtime model 之間的最後一道型別防線。

### `registryFromSpecs(specs)`

- 目的：從既有 `ProblemTypeSpec` 序列重建一份新 registry。
- 主要用途：多出現在 shared memory worker attach 路徑，讓子進程不用重跑外部 builder 掃描也能得到一致的題型註冊表。

## 對應函式索引與閱讀順序

1. `ProblemShmPack`
2. `ProblemTypeSpec`
3. `ProblemRegistry.register`
4. `ProblemRegistry.get`
5. `ProblemRegistry.validate_model`
6. `ProblemRegistry.list_problem_types`
7. `ProblemRegistry.specs`
8. `registryFromSpecs`
