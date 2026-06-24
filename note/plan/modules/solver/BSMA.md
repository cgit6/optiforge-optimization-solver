# `solver/BSMA.py`

## 模組責任

`solver/BSMA.py` 提供 BSMA 的純 Python 基線實作。它保留與舊版 `old/BSMA.py` 對齊的行為，作為語意基準與驗證對照。

## 公開入口/主要類型

- `_digest_float_prefix(...)`
- `_argsort_pop_fit_desc_deterministic(...)`
- `BSMACore`
- `BSMASolver`

## 主要資料結構與資料契約

- `BSMACore` 保存：
  - problem tensors：`values`、`weights`、`capacities`
  - 演算法狀態：`pop_sol`、`pop_fit`、`W`、`Gbest_sol`、`Gbest_fit`
  - LP 產物：`cp_list`、`linprog_runtime`
- `BSMASolver` 負責把 generic `ProblemModel` 與 solver YAML params 轉成 core 需要的資料。
- `ctf_kind` 由 `tools.continuous_to_binary.parse_ctf_kind(...)` 解析。

## 資料流與控制流

1. `BSMASolver.solve(...)` 驗證 stop condition 與 params。
2. 以 `run_seed` 固定 numpy 全域 RNG。
3. 建立 `BSMACore`，在初始化時用 LP pseudo utility 產生 `cp_list`，再建立初始族群。
4. `BSMACore.run()` 重複執行：
   - 依 fitness 更新 `W`
   - 在 `z_global` 與 `local` 分支間切換
   - 經 CTF 把連續值轉 0/1
   - `repair(...)` 修正違反容量限制的解
   - 排序並更新 global best
5. `BSMASolver` 把最佳解封裝成 `SolveResult`。

## 失敗路徑與例外條件

- 只支援 `stop_condition.type=max_iterations`。
- `pop_size <= 0`、`z` 不在 `(0, 1]`、`max_iter <= 0` 都會失敗。
- `linprog` 若退化仍可能產生 `inf/nan` pseudo utility；模組目前只靠 `np.errstate` 抑制警告，不做更積極修正。

## 副作用與資源生命週期

- 會呼叫 `scipy.optimize.linprog`，並記錄 `linprog_runtime`。
- `BSMASolver.solve(...)` 會重設 numpy 全域 RNG；這是與舊版對齊的重要副作用。
- `_loop_trace` 是除錯摘要鉤子，預設 `None`。

## 與其他模組的關係

- 上游：`solver.registry`、`engine.builders`。
- 下游：`BSMA_numba.py` 直接重用 `_argsort_pop_fit_desc_deterministic(...)` 作為排序契約基準。
- 依賴：`tools.continuous_to_binary`、`engine.models.SolveResult`。

## 核心函式與 helper 說明

### `_argsort_pop_fit_desc_deterministic(pop_fit, pop_size)`

- 目的：提供 Python 與 Numba 共用的決定性排序契約。
- 角色：同值 fitness 時固定由較小列索引在前，避免 NumPy / Numba `argsort` 的 tie-breaking 差異破壞重現性。

### `BSMACore.pseudo_utility()`

- 目的：用 `linprog` 建立 LP-derived `cp_list`，作為初始化與 repair 的共同物品順序。
- 副作用：呼叫 `linprog`，並記錄 `linprog_runtime`。
- 修改風險：這裡的排序一旦改變，初始化族群與 repair 路徑會整體漂移。

### `BSMACore.initial_pop()` / `repair(...)`

- 角色：`initial_pop()` 用 `cp_list` 做隨機 greedy 初始化，`repair(...)` 則把 local/global 更新後的解拉回可行域。
- 注意事項：repair 的兩段流程與舊版對齊，是 Python / Numba 等價驗證的核心之一。

### `BSMACore.run()`

- 目的：執行純 Python BSMA 主循環。
- 控制流：sort -> 更新 `W` -> `z_global` / local 分支 -> CTF 二值化 -> repair -> 再排序 -> 更新 global best。
- 副作用：重設 numpy 全域 RNG，這是與歷史版本對齊的必要條件。

### `BSMASolver.solve(...)`

- 目的：把 generic solver config 轉成 `BSMACore` 可執行參數，並包裝 `SolveResult`。
- 角色：它是 registry 真正呼叫的 adapter，而不是演算法 hot-loop 本體。

## 對應函式索引與閱讀順序

1. `_digest_float_prefix`
2. `_argsort_pop_fit_desc_deterministic`
3. `BSMACore.__init__`
4. `BSMACore.pseudo_utility`
5. `BSMACore.initial_pop`
6. `BSMACore.repair`
7. `BSMACore.sort_pop`
8. `BSMACore.run`
9. `BSMASolver.solve`
