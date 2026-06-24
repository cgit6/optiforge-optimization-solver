# `problem/interface.py`

## 模組責任

`problem/interface.py` 定義所有 problem model 的抽象介面與共用正規化 helper。它把 solver 可假設的最低契約固定下來。

## 公開入口/主要類型

- `as_int_array(...)`
- `as_int_matrix(...)`
- `normalize_best_known(...)`
- `Problem` 抽象基底類別

## 主要資料結構與資料契約

- `Problem` 至少要提供 `problem_id`、`dataset`、`best_known`、`problem_type`、`encoding`、`direction`。
- `fitness(solution)`：根據 problem 自己的編碼規則回算 objective。
- `violates_constraints(solution)`：回答解是否違反限制。
- `validate(solve_result)`：把 solver 回傳結果轉成 `ValidationReport`。
- `as_int_array` / `as_int_matrix` 把 numpy/list 正規化成 `int64`、C-contiguous、固定維度陣列，讓 shared memory 與 Numba 路徑都能穩定使用。

## 資料流與控制流

1. 具體 problem 實作在 `__post_init__` 時先呼叫 `Problem.__post_init__()`，完成 identity 與 direction 正規化。
2. 子類別再用 `as_int_array(...)`、`as_int_matrix(...)` 正規化內部數值矩陣。
3. solver 執行完後，problem 子類別實作 `validate(...)`，通常會轉呼叫 `problem.validation.build_validation_report(...)`。

## 失敗路徑與例外條件

- `problem_id`、`dataset`、`problem_type`、`encoding` 為空字串會直接失敗。
- `direction` 不是 `max` / `min` 或維度不正確時，會在正規化階段中止。
- `as_int_array(...)` / `as_int_matrix(...)` 維度不符合時，會丟 `ValueError`。
- `normalize_best_known(...)` 會拒絕空值、非正數或不合法的型別組合。

## 副作用與資源生命週期

- 無檔案或 shared memory 副作用。
- 副作用主要是將 numpy 陣列轉為連續記憶體表示，這對 solver hot path 與 shm attach 都很重要。

## 與其他模組的關係

- 上游：`problem.registry` 要求所有 `model_type` 都必須繼承 `Problem`。
- 下游：`problem.mkp.MKPProblem` 與其他 problem 類別都實作這個介面。
- `problem.validation` 提供 `ValidationReport` 與 direction/objective 正規化函式。

## 核心函式與 helper 說明

### `as_int_array(name, data)`

- 目的：把 1D 整數資料正規化成 `np.int64`、C-contiguous 陣列。
- 失敗路徑：輸入不是一維資料時丟 `ValueError`。
- 在流程中的角色：MKP/TSP 類 problem 在建模與 shared memory attach 時都依賴它維持穩定記憶體布局。

### `as_int_matrix(name, data)`

- 目的：把 2D 整數資料正規化成 `np.int64` 連續矩陣。
- 角色：它是 `weights`、`distance_matrix` 這類核心數值矩陣的共同入口，避免每個題型各自重寫 shape 與 dtype 處理。

### `normalize_best_known(value, allow_none)`

- 目的：把 `best_known` 收斂成與 objective 契約一致的 scalar 或 tuple 表示。
- 控制流：先透過 `normalize_objective_value(...)` 正規化，再檢查是否允許 `None`、是否為正值，以及是否可安全收斂成整數。
- 修改風險：如果這裡放寬非正值或 `None` 規則，下游 `best_known_status_and_gap(...)` 的語意也會跟著變。

### `Problem.__post_init__()`

- 目的：驗證 problem identity 欄位不可為空，並正規化 `direction`。
- 資料契約：所有具體 problem class 都必須先呼叫這個基底驗證，再檢查自己的 shape/數值條件。
- 角色：它定義了所有 solver 可以假設的最小 problem metadata 契約。

## 對應函式索引與閱讀順序

1. `as_int_array`
2. `as_int_matrix`
3. `normalize_best_known`
4. `Problem`
5. `Problem.fitness`
6. `Problem.violates_constraints`
7. `Problem.validate`
