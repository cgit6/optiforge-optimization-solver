# `problem/mkp.py`

## 模組責任

`problem/mkp.py` 是目前主流程的核心 problem family。它實作 MKP model、YAML 載入、shared memory pack/attach 與 registry spec。

## 公開入口/主要類型

- `MKPProblem`
- `MKPProblemShmPack`
- `load_mkp_problem(...)`
- `make_mkp_shm_pack(...)`
- `attach_mkp_shm_pack(...)`
- `mkpProblemSpec()`

## 主要資料結構與資料契約

- `MKPProblem` 繼承 `Problem`，並補上：
  - `items`
  - `dim`
  - `values`
  - `weights`
  - `capacities`
- 固定編碼是 `binary`，固定 direction 是 `max`。
- `MKPProblemShmPack` 保存三個 shared memory name、各自 shape，以及 identity 與 `best_known`。
- YAML 必須至少包含 `problem_id`、`dataset`、`items`、`dim`、`best_known`、`values`、`weights`、`capacities`。

## 資料流與控制流

1. `load_mkp_problem(...)` 驗證 YAML 必要欄位與 identity。
2. 建立 `MKPProblem`，在 `__post_init__` 中正規化 values/weights/capacities 並驗證 shape。
3. `ProblemBank.build(...)` 會呼叫 `make_mkp_shm_pack(...)`，將三個 numpy 陣列寫進 shared memory。
4. worker initializer 透過 `attach_mkp_shm_pack(...)` 掛回 read-only numpy view。
5. solver 完成後，`MKPProblem.validate(...)` 會呼叫 `build_validation_report(...)` 重算 feasibility 與 objective。

## 失敗路徑與例外條件

- `items`、`dim` 非正整數，或陣列 shape 與宣告尺寸不符，都會在 model 建立時失敗。
- YAML 缺欄位、identity 不一致、資料型別不合法，會由 `load_mkp_problem(...)` 包成 `ValueError`。
- `make_mkp_shm_pack(...)` 收到非 `MKPProblem` 會丟 `TypeError`。
- `fitness(...)`、`violates_constraints(...)` 若收到長度錯誤的 solution，會視情況丟錯或判定 infeasible。

## 副作用與資源生命週期

- `make_mkp_shm_pack(...)` 會建立三個 shared memory block，分別保存 values、weights、capacities。
- `attach_mkp_shm_pack(...)` 只 attach，不 unlink；真正的釋放責任仍在 `ProblemBank.close()`。
- 建立出的 numpy view 都會被設成 read-only，避免 worker 誤改共享題目資料。

## 與其他模組的關係

- 上游：`ProblemRepository` 用 `load_mkp_problem(...)` 載 YAML。
- 中游：`ProblemBank` 用 shm pack/attach API 做跨 process 傳遞。
- 下游：所有 MKP solver 依賴 `MKPProblem` 的 `values/weights/capacities` 結構。
- 依賴：`problem.validation`、`problem.yaml`、`problem.interface`。

## 核心函式與 helper 說明

### `MKPProblem.__post_init__()`

- 目的：把 MKP 的核心結構 `values`、`weights`、`capacities` 正規化並驗證 shape。
- 控制流：先跑 `Problem.__post_init__()`，再驗 `items`/`dim`，接著用 `as_int_array(...)`、`as_int_matrix(...)` 做陣列正規化，最後把 arrays 設成 read-only。
- 失敗路徑：shape 與 `items`/`dim` 宣告不符、`best_known` 缺失或非法，都會在這裡直接失敗。
- 修改風險：這裡的 shape 契約一旦改動，solver、shared memory pack 與資料轉換腳本都會連鎖受影響。

### `MKPProblem.fitness(solution)`

- 目的：依二元選擇向量重算總價值。
- 資料契約：`solution` 長度必須等於 `items`；它不自行修補 shape，而是把錯誤視為呼叫端問題。
- 在演算法中的角色：validation 會用它重算 solver 回報 objective，作為 `objective_valid` 的依據。

### `MKPProblem.violates_constraints(solution)`

- 目的：判定解是否超過任一容量限制。
- 行為特性：對 shape 錯誤採保守策略，直接視為 infeasible，而不是嘗試部分計算。
- 在演算法中的角色：這是所有 MKP solver 的共同 feasibility 定義。

### `load_mkp_problem(...)`

- 目的：把單一 MKP YAML 載成 `MKPProblem`。
- 控制流：`require_fields(...)` -> `validate_identity(...)` -> 建立 `MKPProblem`，並把型別/值錯誤包成帶檔名的 `ValueError`。
- 修改風險：錯誤訊息格式會直接影響 CLI、tests 與資料整理腳本的可診斷性。

### `make_mkp_shm_pack(problem, shm_blocks)`

- 目的：把 `values`、`weights`、`capacities` 三個核心陣列搬進 shared memory。
- 副作用：建立三個 shared memory block，並把 block 物件 append 到外部 `shm_blocks`，由 `ProblemBank.close()` 集中釋放。
- 在流程中的角色：這是主進程題目資料進入多進程執行環境的關鍵轉換點。

### `attach_mkp_shm_pack(pack, shm_handles)`

- 目的：在 worker 端依 pack metadata 重建只讀 `MKPProblem`。
- 控制流：依 shm name attach block、建立 numpy view、設為 read-only，再重建完整 model。
- 風險：如果 attach 路徑與 pack 路徑 shape/dtype 不一致，錯誤會在 worker 啟動時才浮出。

### `mkpProblemSpec()`

- 角色：把 loader、required fields、shared memory pack/attach、model type 綁成 `mkp` 的單一 `ProblemTypeSpec`。
- 維護建議：新增 MKP 相關 YAML 欄位時，這裡與 `load_mkp_problem(...)` 必須同步調整。

## 對應函式索引與閱讀順序

1. `MKPProblem`
2. `MKPProblem.fitness`
3. `MKPProblem.violates_constraints`
4. `MKPProblem.validate`
5. `MKPProblemShmPack`
6. `load_mkp_problem`
7. `make_mkp_shm_pack`
8. `attach_mkp_shm_pack`
9. `mkpProblemSpec`
