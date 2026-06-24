# `engine/configs.py`

## 模組責任

`engine/configs.py` 把 solver YAML 載成執行期快照，避免 solver 在模擬中直接碰檔案系統，也避免多個 task 共享可變 config 物件。

## 公開入口/主要類型

- `SolverConfigsSnapshot`
  - `build(...)`
  - `from_configs(...)`
  - `get(...)`
  - `solver_ids()`
  - `param_set_indices(...)`
  - `keys()`
  - `to_worker_init_dict()`

## 主要資料結構與資料契約

- 內部 key 固定是 `(solver_id, param_set_index)`。
- 每筆 config 至少要有 `solver_id`、`param_set_index`、`solver_class`、`capabilities`、`stop_condition`、`params`。
- 對外所有 `get(...)` 都回傳 deep copy，讓 solver 在執行期加入 `run_seed` 或其他暫時欄位時，不會污染快照。

## 資料流與控制流

1. `build(...)` 依 `ExperimentSpec.solver_ids` 從 `SolverConfigLoader` 載入 solver YAML。
2. 若呼叫端提供 `param_set_indices`，只會載入指定 variant；否則載入該 solver 的所有 param set。
3. 每筆 YAML 都會被複製並存成 `_by_key` tuple。
4. `get(...)` 在執行時提供變異安全的 config 副本。
5. `to_worker_init_dict()` 再把所有 config 轉成可 pickle 的 dict，供 process initializer 使用。

## 失敗路徑與例外條件

- 指定的 solver YAML 不存在、param set index 超界或欄位缺失，會在 loader 或 `from_configs(...)` 驗證時中止。
- `from_configs(...)` 若收到空集合、缺少必要欄位或重複 key，會直接丟 `ValueError`。
- `get(...)` 查不到指定 `(solver_id, param_set_index)` 時會丟 `KeyError`。

## 副作用與資源生命週期

- 主要副作用是讀取 `configs/solvers/*.yaml`。
- 本模組不持有外部資源句柄；生命週期重點是 immutability，避免 solver task 之間互相污染設定。

## 與其他模組的關係

- 上游：`engine.assembly` 建 bundle 時會先建立 snapshot；`cli.replay.main` 也會用 `from_configs(...)` 重建 seed bank 中的 solver variant。
- 下游：`machine.core` 在主行程與子行程都以 snapshot 為唯一 solver config 來源。
- 依賴：`tools.solver_config_loader.SolverConfigLoader`。

## 核心函式與 helper 說明

### `SolverConfigsSnapshot.build(...)`

- 目的：從 `ExperimentSpec.solver_ids` 與 solver root 載入本次執行需要的 solver variants。
- 控制流：
  - 若 `param_set_indices` 沒有限制，整個 solver 的所有 param sets 都載入
  - 若有指定，只載入那幾個 index
  - 每筆 config 在進快照前都做 `deepcopy`
- 資料契約：快照 key 永遠是 `(solver_id, param_set_index)`，而不是單純 `solver_id`。
- 修改風險：如果改成惰性載入，process worker 與 replay 的可重現性會變差，因為 runtime 又會回頭碰檔案系統。

### `SolverConfigsSnapshot.from_configs(...)`

- 目的：把現成 config blobs 收斂成和 `build(...)` 同型的快照。
- 主要呼叫端：`cli.replay`，因為 replay 的 solver config 來自 seed bank，而不是 `configs/solvers/*.yaml` 現場讀檔。
- 重要驗證：
  - `solver_id` 不可空
  - `param_set_index >= 0`
  - key 不可重複
  - `solver_class/capabilities/stop_condition/params` 不可缺

### `get(...)`

- 目的：回傳可安全修改的 config 副本。
- 為什麼一定複製：`Machine.run_task(...)` 會寫入 `run_seed`，solver 也可能在本地 config 上加暫時欄位；如果直接回傳快照原物件，variant 間會互相污染。

### `solver_ids()` / `param_set_indices(...)` / `keys()`

- 角色：純查詢 accessor。
- 用途：
  - `solver_ids()`：讓上游快速知道快照涵蓋哪些 solver
  - `param_set_indices(...)`：`Simulator._build_machines(...)` 據此展開 variant
  - `keys()`：測試與檢查用途較多

### `to_worker_init_dict()`

- 目的：把 tuple-based snapshot 轉成 worker initializer 好 picklable 的 dict。
- 風險：若未來 config 中出現不能 pickle 的 runtime object，這裡會成為第一個爆點；目前文件假設 solver config 仍是純資料。

## 對應函式索引與閱讀順序

1. `SolverConfigsSnapshot.build`
2. `SolverConfigsSnapshot.from_configs`
3. `SolverConfigsSnapshot.get`
4. `SolverConfigsSnapshot.solver_ids`
5. `SolverConfigsSnapshot.param_set_indices`
6. `SolverConfigsSnapshot.keys`
7. `SolverConfigsSnapshot.to_worker_init_dict`
