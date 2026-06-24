# `problem/tsp.py`

## 模組責任

`problem/tsp.py` 實作 TSP 題型的 model、YAML loader、shared memory pack/attach 與 registry spec。它讓同一套 engine 能在 MKP 之外再支援 permutation/min 題型。

## 公開入口/主要類型

- `TSPProblem`
- `TSPProblemShmPack`
- `load_tsp_problem(...)`
- `make_tsp_shm_pack(...)`
- `attach_tsp_shm_pack(...)`
- `tspProblemSpec()`

## 主要資料結構與資料契約

- `TSPProblem` 繼承 `Problem`，固定：
  - `problem_type = "tsp"`
  - `encoding = "permutation"`
  - `direction = "min"`
- 主要欄位：
  - `n_cities`
  - `distance_matrix`
  - `coords`（可選）
  - `best_known`
- YAML 必填欄位：
  - `problem_id`
  - `dataset`
  - `problem_type`
  - `n_cities`
  - `distance_matrix`
- `TSPProblemShmPack` 只保存 `distance_matrix` 的 shared memory metadata，不保存 `coords`。

## 資料流與控制流

1. `load_tsp_problem(...)` 先驗證必填欄位與 identity。
2. `TSPProblem.__post_init__()` 驗證矩陣 shape、對角線為零、矩陣對稱，並把 arrays 設成 read-only。
3. `make_tsp_shm_pack(...)` 把 `distance_matrix` 複製到 shared memory，供 `ProblemBank` 跨 process 傳遞。
4. worker 透過 `attach_tsp_shm_pack(...)` 掛回 read-only matrix，再建成 `TSPProblem`。
5. solver 完成後，`validate(...)` 會把 `best_solution` 視為城市 permutation 交給 `build_validation_report(...)`。

## 失敗路徑與例外條件

- `n_cities <= 1`、矩陣 shape 錯誤、對角線非零、非對稱矩陣、`coords` shape 不符，都會在 model 建立階段失敗。
- YAML identity、資料型別或欄位不合法時，`load_tsp_problem(...)` 會包成 `ValueError`。
- `make_tsp_shm_pack(...)` 收到非 `TSPProblem` 時會丟 `TypeError`。
- `fitness(...)` 收到非 permutation 的解時會丟 `ValueError`。

## 副作用與資源生命週期

- `make_tsp_shm_pack(...)` 會建立一個 shared memory block 保存 `distance_matrix`。
- `attach_tsp_shm_pack(...)` 只 attach，不 unlink；真正釋放仍由 `ProblemBank.close()` 負責。
- `coords` 不進 shared memory，代表 worker attach 後的 `TSPProblem` 不會保留原始座標；若後續演算法需要 `coords`，目前契約不足。

## 與其他模組的關係

- 上游：`ProblemRepository` 依 registry spec 載入 `tsp` YAML。
- 中游：`ProblemBank` 使用 shm pack/attach API。
- 下游：`tests/test_tsp_problem_type.py` 驗證 repository、bank、simulator 與 output 鏈是否能接受 permutation/min 題型。
- 依賴：[`problem/interface.py`](interface.md)、[`problem/validation.py`](validation.md)、[`problem/yaml.py`](yaml.md)。

## 核心函式與 helper 說明

### `TSPProblem.__post_init__()`

- 目的：驗證 `distance_matrix` 與可選 `coords` 的 shape/對稱性，並固化 TSP 的 `permutation`/`min` 契約。
- 控制流：先跑 `Problem.__post_init__()`，再驗 `n_cities > 1`、距離矩陣是方陣且對角線為零、矩陣對稱，最後把 arrays 設成 read-only。
- 修改風險：如果這裡放寬非對稱矩陣，solver 與驗證都會從 symmetric TSP 轉成更寬鬆的問題定義。

### `TSPProblem.fitness(solution)`

- 目的：把城市 permutation 重算成巡迴路徑總長。
- 失敗路徑：解不是合法 permutation 時直接丟 `ValueError`。
- 在演算法中的角色：validation 依靠它重算 objective，確保 solver 回報值與實際 tour 成本一致。

### `TSPProblem.violates_constraints(solution)`

- 目的：檢查解是否完整覆蓋每個城市且不重複。
- 行為特性：它不做 repair，也不接受部分 permutation；任何重複或缺漏都視為 infeasible。

### `load_tsp_problem(...)`

- 目的：把 TSP YAML 載成 `TSPProblem`。
- 控制流：必要欄位檢查、identity 驗證、建模、包裝錯誤訊息。
- 注意事項：`coords` 是可選欄位，但進入 worker shared memory 路徑後不會被保留。

### `make_tsp_shm_pack(problem, shm_blocks)`

- 目的：把 `distance_matrix` 複製到 shared memory，供 worker 共用。
- 副作用：建立一個 shared memory block，並把 block 物件登記到 `shm_blocks`。
- 風險：目前只序列化距離矩陣，不序列化 `coords`；任何需要原始座標的 solver/分析工具都不能依賴 worker attach 後的 problem。

### `attach_tsp_shm_pack(pack, shm_handles)`

- 目的：在 worker 端重建只含距離矩陣的 `TSPProblem`。
- 資料契約：attach 出來的 problem 仍保留 `best_known`、identity 與方向資訊，但 `coords` 會是 `None`。

### `tspProblemSpec()`

- 角色：宣告 `tsp` 題型在 registry 中的完整接點。
- 維護建議：若未來支援 ATSP 或額外欄位，這裡的 `encoding`、`direction` 與 required fields 要一起審視。

## 對應函式索引與閱讀順序

1. `TSPProblem`
2. `TSPProblem.fitness`
3. `TSPProblem.violates_constraints`
4. `TSPProblem.validate`
5. `TSPProblemShmPack`
6. `load_tsp_problem`
7. `make_tsp_shm_pack`
8. `attach_tsp_shm_pack`
9. `tspProblemSpec`
