# `engine/bank.py`

## 模組責任

`engine/bank.py` 負責兩件事：先把 `configs/problems` 掃描成 catalog，再把本次實驗需要的 problem model 轉成 shared memory bank。它是題目資料從「檔案系統」進入「執行期共用記憶體」的橋接層。

## 公開入口/主要類型

- `ProblemCatalogEntry`：單一 YAML 檔在 catalog 中的描述。
- `CatalogSummary`：dataset 與 problem id 的摘要檢視。
- `ProblemWorkerView`：worker process 內部使用的共享題目檢視。
- `configure_problem_bank_worker(...)` / `get_worker_problem_bank()`：process worker initializer API。
- `scanProblemCatalog(...)`：掃描 problem 目錄。
- `validate_catalog_entries(...)`、`validate_spec_problems_in_repository(...)`、`assert_spec_problems_in_catalog(...)`：catalog 與 repository 的防呆檢查。
- `ProblemBank`：主行程持有的題目 bank 與 shared memory 生命週期管理者。

## 主要資料結構與資料契約

- `ProblemCatalogEntry` 以 `(problem_type, dataset, problem_id, filePath)` 識別題目檔。
- `CatalogSummary.problems_by_dataset` 用排序後的 tuple 保存 dataset 與 problem id 清單，供 CLI 和文件摘要層使用。
- `ProblemBank` 內部保存三份東西：
  - `_models`：主行程中的 `Problem` instance。
  - `_shm_blocks`：真正要 close/unlink 的 shared memory handle。
  - `_packs` / `_problem_specs`：傳給 worker initializer 的序列化資料。
- `ProblemWorkerView` 在 worker 端用 `ProblemTypeSpec.attach_shm_pack(...)` 重新掛上 numpy view，並建立 `(problem_type, dataset, problem_id)` 到 `Problem` 的查找表。

## 資料流與控制流

1. `scanProblemCatalog(...)` 先遍歷 `problem_root/<problem_type>/<dataset>/*.yaml`。
2. 只接受 `ProblemRegistry` 已註冊的 `problem_type`；未知資料夾會被跳過。
3. `assert_spec_problems_in_catalog(...)` 檢查 `ExperimentSpec` 中每個 problem id 是否存在。
4. `validate_spec_problems_in_repository(...)` 觸發 repository 真正載入本次實驗題目，確保 YAML 可被解析。
5. `ProblemBank.build(...)` 對本次實驗用到的唯一 problem key 逐一呼叫 `repository.load(...)`。
6. 每個 `Problem` model 再經 `ProblemTypeSpec.make_shm_pack(...)` 轉成 shared memory pack。
7. 主行程執行時直接用 `ProblemBank.get(...)`，worker 則透過 `configure_problem_bank_worker(...)` 建立 `ProblemWorkerView` 後查題。

## 失敗路徑與例外條件

- `problem_root` 不是目錄時，`scanProblemCatalog(...)` 直接失敗。
- `ExperimentSpec` 中的題目不在掃描結果時，`assert_spec_problems_in_catalog(...)` 會丟 `FileNotFoundError`。
- `ProblemBank.get(...)` 或 worker view `get(...)` 查不到題目時，都會丟 `FileNotFoundError`，表示 task 與 bank 的資料契約斷裂。
- 若 `get_worker_problem_bank()` 在 worker initializer 尚未執行前被呼叫，會丟 `RuntimeError`。

## 副作用與資源生命週期

- `ProblemBank.build(...)` 會建立 shared memory block；這些 block 由 `ProblemBank.close()` 統一回收。
- `close()` 會先 `close()` 再 `unlink()`；如果 block 已被其他流程 unlink，會吞掉 `FileNotFoundError`，避免重複回收時流程崩潰。
- worker 端的 `ProblemWorkerView` 只負責 attach shared memory，不負責 unlink；資源真正擁有者仍是主行程的 `ProblemBank`。

## 與其他模組的關係

- 上游：`engine.assembly` 先掃 catalog，再建立 `ProblemBank`。
- 依賴：`engine.repository` 載入 `Problem` model，`problem.registry` 提供 shm pack/attach 行為。
- 下游：`machine.core` 在主行程用 `ProblemBank.get(...)`，在子行程用 `configure_problem_bank_worker(...)` 與 `get_worker_problem_bank()`。

## 核心函式與 helper 說明

### `scanProblemCatalog(...)`

- 目的：把 `configs/problems/<problem_type>/<dataset>/*.yaml` 掃描成實體目錄索引。
- 輸入契約：只接受 registry 已知的 `problem_type`；未知第一層資料夾會被略過，不列入 catalog。
- 輸出契約：
  - `entries` 保留逐檔 `problem_type/dataset/problem_id/filePath`
  - `summary` 則壓成 dataset 視角的快速摘要
- 重要限制：只掃第二層 dataset 目錄下的 `*.yaml`，不遞迴 deeper 子資料夾；這也是 `mkp/tsp/SMALL/*.yaml` 目前不在 active catalog 的原因。
- 修改風險：若改變掃描深度，`assert_spec_problems_in_catalog(...)`、CLI 行為與 dashboard 的資料契約都要一起修。

### `validate_catalog_entries(...)` 與 `validate_spec_problems_in_repository(...)`

- `validate_catalog_entries(...)`：
  - 對全 catalog 做完整 `repository.load(...)`
  - 適合 CI 或維護工具，不適合日常 runtime
- `validate_spec_problems_in_repository(...)`：
  - 只驗證本次 `ExperimentSpec` 真正會用到的題目
  - 是 `engine.build(...)` 的正式路徑
- 兩者差異的設計目的：把「完整題庫健康檢查」和「本次執行 fail-fast」拆開，避免每次都對未使用題目做 I/O。

### `assert_spec_problems_in_catalog(...)`

- 目的：在真正讀 YAML 前，先確認 `ExperimentSpec` 要求的 `(problem_type, dataset, problem_id)` 至少存在於掃描清單。
- 角色：這是最便宜的一層 existence gate；它不驗 schema，只驗實體檔存在且路徑能被 catalog 看見。

### `ProblemWorkerView`

- `__init__(...)`：
  - 依 `problem_specs` 重建 registry
  - 逐 pack attach shared memory
  - 驗證 attach 後 model 型別與 identity
- `get(...)`：
  - 提供 worker 端用的 `(problem_type, dataset, problem_id)` 查找
  - 查不到時丟 `FileNotFoundError`，表示 task 與 bank 的資料契約已斷裂
- 生命週期：worker view 只 attach block，不擁有 unlink 權限。

### `configure_problem_bank_worker(...)` / `get_worker_problem_bank()`

- `configure_problem_bank_worker(...)`：worker initializer 入口，把 process-local 全域 `_worker_problem_view` 設好。
- `get_worker_problem_bank()`：worker task 執行時的查詢入口；若 initializer 沒先跑，這裡會明確丟 `RuntimeError`。

### `ProblemBank.build(...)`

- 目的：為本次 spec 建 shared memory 題庫，而不是為整個 catalog 建 bank。
- 控制流：
  1. 先用 `uniq` 去除重複 problem key
  2. `repository.load(...)` 取得主行程 `Problem`
  3. 由對應 `ProblemTypeSpec.make_shm_pack(...)` 建 pack 與 shared memory
  4. 回傳同時持有 `models`、`packs`、`problem_specs`、`shm_blocks` 的 `ProblemBank`
- 風險：如果題型的 `make_shm_pack(...)` 不可重入或沒有 append 正確的 `shm_blocks`，`close()` 就無法完整回收。

### `ProblemBank.get(...)`

- 目的：主行程路徑的問題查找入口。
- 與 worker 的差異：主行程直接回傳建模後的 `Problem` instance；worker 則拿的是 attach 出來的 view model。

### `ProblemBank.export_worker_packs()` / `export_worker_problem_specs()`

- 角色：兩者是 process initializer 的 serialization 邊界。
- 為什麼分開：worker 不應直接拿主行程 `ProblemBank`；它只需要 pack 與 spec，自己重建 `ProblemWorkerView`。

### `ProblemBank.close()`

- 目的：統一回收 `ProblemBank.build(...)` 建出的 shared memory block。
- 控制流：每個 block 先 `close()` 再 `unlink()`，最後清空 `_shm_blocks`。
- 失敗路徑：`close()` 的一般例外會被吞掉，`unlink()` 的 `FileNotFoundError` 也會被吞掉，因為多次收尾時重複 unlink 是可接受狀況。
- 修改風險：這是 shared memory 泄漏的最後防線；任何改動都要配套檢查 `Simulator.close()`、`Experiment.run()`、`cli.replay` 的收尾路徑。

## 對應函式索引與閱讀順序

1. `ProblemCatalogEntry`
2. `CatalogSummary`
3. `ProblemWorkerView`
4. `configure_problem_bank_worker`
5. `get_worker_problem_bank`
6. `scanProblemCatalog`
7. `validate_catalog_entries`
8. `validate_spec_problems_in_repository`
9. `assert_spec_problems_in_catalog`
10. `ProblemBank.build`
11. `ProblemBank.get`
12. `ProblemBank.export_worker_packs`
13. `ProblemBank.export_worker_problem_specs`
14. `ProblemBank.close`
