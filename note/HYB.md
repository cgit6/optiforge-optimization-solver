# RL_RC_TRAD_HYB 修改方案

## 1. 修改目標

目前算法的主要流程是：

```text
1. 先用 LP/RC item evaluation 產生一條 cp_list。
2. 所有個體都共用同一條 cp_list。
3. 原本 Q-learning 只負責選擇 update action：
   - SMA global
   - SMA local
   - SCA sin
   - SCA cos
4. 產生 binary solution 後，用同一條 cp_list 做 repair / add / drop / swap / restart。
```

這次要改成：

```text
1. 仍保留原本 Q-learning 選擇 update action。
2. 額外新增第二個 Q-learning table：q_order。
3. q_order 讓每個 individual 在每次更新時，動態選擇要用哪一條 item order。
4. 本次正式候選版本為 RL_RC_TRAD_HYB。
```

RL_RC_TRAD_HYB 的 order action 定義：

```text
order action 0 = RC_ONLY
order action 1 = TRAD_ONLY_BEST01
order action 2 = HYB_SCORE
```

重點：

```text
這不是把 RC / TRAD / HYB 三個分數線性平均成一條排序。
而是讓不同 individual 在不同搜尋狀態下自行選擇不同 item order。
```

這個設計的目的：

```text
RC_ONLY、TRAD_ONLY_BEST01、HYB_SCORE 會捕捉不同類型的高價值 item。
固定使用單一 order 容易被該 order 的錯誤排序卡住。
讓 population 中不同個體使用不同 order，可以保留 item preference 的互補性。
```

---

## 2. 與目前算法的差異

### 2.1 目前版本

目前版本等價於：

```python
cp_list = build_lp_rc_order(instance)

for iteration in range(max_iter):
    for row in population:
        state = compute_state(row)
        update_action = select_q_update_action(q_table, individual_id, state)

        apply_sma_or_sca_update(update_action)

        repair(row, cp_list)
        update_q_table(...)
```

### 2.2 新版本

新版本改成：

```python
order_pool = [
    rc_order,
    trad_order,
    hyb_order,
]

for iteration in range(max_iter):
    for row in population:
        state = compute_state(row)

        order_action = select_q_order_action(q_order, individual_id, state)
        selected_order = order_pool[order_action]

        update_action = select_q_update_action(q_table, individual_id, state)

        apply_sma_or_sca_update(update_action)

        repair(row, selected_order)

        reward = compute_reward(...)
        update_q_table(...)
        update_q_order(...)
```

也就是：

```text
原本：
    一個 q_table 控制 update action。
新版本：
    q_table 控制 update action。
    q_order 控制 item order action。
```

---

## 3. 新增參數

在 YAML 的 `params` 中新增：

```yaml
order_switch_enabled: true
order_switch_policy: rl_rc_trad_hyb
order_switch_alpha: null
order_switch_gamma: null
```

建議預設邏輯：

```text
order_switch_alpha = null 時，沿用 alpha。
order_switch_gamma = null 時，沿用 gamma。
```

完整建議設定：

```yaml
params:
  pop_size: 20
  z: 0.01
  a: 2.5
  ctf: abs_pow_16
  alpha: 0.1
  gamma: 0.9

  item_eval_method: lp_rc_ordered
  eval_group_shuffle: false
  eval_group_decimals: 1
  eval_rc_eps: 1.0e-9
  eval_x_eps: 1.0e-9

  repair_passes: 2
  repair_swap_limit: 4
  repair_drop_mode: rank

  mixed_init_enabled: true

  restart_enabled: true
  restart_window: 40
  restart_ratio: 0.25
  restart_strong_p: 0.85
  restart_core_p: 0.50
  restart_weak_p: 0.15

  guided_binary_enabled: false
  local_search_enabled: false
  archive_pr_enabled: false

  order_switch_enabled: true
  order_switch_policy: rl_rc_trad_hyb
  order_switch_alpha: null
  order_switch_gamma: null
```

第一版建議先關掉：

```yaml
guided_binary_enabled: false
local_search_enabled: false
archive_pr_enabled: false
```

原因是目前要驗證的是：

```text
RL 動態選擇 item order 本身是否有效。
```

不要同時加入 GBC / LS / PR，否則不容易判斷改善來源。

---

## 4. 三條 item order 的定義

## 4.1 RC_ONLY

### 目的

`RC_ONLY` 只看 LP relaxation 後的 `reduced_cost`。

### 注意

你目前程式中若已存在 `score_rc_rank` 或 `_score_values_for_method("rc")`，它可能是：

```text
0.5 * reduced_cost + 0.5 * x_lp
```

這不是這裡要的 RC_ONLY。

本版本的 `RC_ONLY` 必須是：

```text
RC_ONLY = robust_minmax(reduced_cost)
```

### 實作

```python
def build_rc_only_order(base_payload: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    reduced_cost = np.asarray(base_payload["reduced_cost"], dtype=np.float64).ravel()
    rc_score = _robust_minmax(reduced_cost)

    item_ids = np.arange(rc_score.size, dtype=np.int64)
    rc_order = np.lexsort((item_ids, -rc_score)).astype(np.int64)

    return np.ascontiguousarray(rc_order), rc_score
```

排序規則：

```text
rc_score 越大越前面。
score 相同時 item id 小的排前面。
```

---

## 4.2 TRAD_ONLY_BEST01

### 目的

`TRAD_ONLY_BEST01` 是傳統 CP 類特徵的低成本組合。它不使用 LP reduced cost 作為主訊號，而是使用：

```text
profit
normalized resource consumption
lightness
low resource pressure
profit / resource ratio
```

### 特徵定義

給定：

```python
values      # shape [items]
weights     # shape [items, dim]
capacities  # shape [dim]
dual_price  # from LP payload
```

先定義 normalized weight：

```python
normw = weights / (capacities[None, :] + 1e-12)
```

計算：

```python
sw = normw.sum(axis=1)   # item 的總相對資源消耗
mw = normw.max(axis=1)   # item 在最吃緊單一維度的相對消耗
```

計算 dual pressure：

```python
dual = base_payload["dual_price"]

if dual.sum() > 1e-12:
    pressure = normw @ (dual / (dual.sum() + 1e-12))
else:
    pressure = sw / dim
```

接著計算六個 normalized feature：

```python
value_score    = _robust_minmax(values)
sum_weight_eff = _robust_minmax(values / (sw + 1e-12))
max_weight_eff = _robust_minmax(values / (mw + 1e-12))
light          = 1.0 - _robust_minmax(sw)
max_light      = 1.0 - _robust_minmax(mw)
low_pressure   = 1.0 - _robust_minmax(pressure)
```

### 權重

固定使用：

```python
TRAD_W = {
    "light": 0.006743546653452455,
    "low_pressure": 0.43597043345859415,
    "max_light": 0.013316182861006512,
    "max_weight_eff": 0.025911361416350264,
    "sum_weight_eff": 0.17836957605680379,
    "value": 0.33968889955379283,
}
```

### score

```python
trad_score = (
    TRAD_W["light"] * light
    + TRAD_W["low_pressure"] * low_pressure
    + TRAD_W["max_light"] * max_light
    + TRAD_W["max_weight_eff"] * max_weight_eff
    + TRAD_W["sum_weight_eff"] * sum_weight_eff
    + TRAD_W["value"] * value_score
)

trad_score = np.clip(trad_score, 0.0, 1.0)
```

### 實作

```python
TRAD_W = {
    "light": 0.006743546653452455,
    "low_pressure": 0.43597043345859415,
    "max_light": 0.013316182861006512,
    "max_weight_eff": 0.025911361416350264,
    "sum_weight_eff": 0.17836957605680379,
    "value": 0.33968889955379283,
}

def build_trad_only_best01_order(
    values: np.ndarray,
    weights: np.ndarray,
    capacities: np.ndarray,
    base_payload: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray]:
    values_f = np.asarray(values, dtype=np.float64).ravel()
    weights_f = np.asarray(weights, dtype=np.float64)
    caps_f = np.asarray(capacities, dtype=np.float64).ravel()

    n = values_f.size
    dim = caps_f.size
    item_ids = np.arange(n, dtype=np.int64)

    normw = weights_f / (caps_f[None, :] + 1.0e-12)
    sw = normw.sum(axis=1)
    mw = normw.max(axis=1)

    dual = np.asarray(base_payload["dual_price"], dtype=np.float64).ravel()
    if dual.sum() > 1.0e-12:
        pressure = normw @ (dual / (dual.sum() + 1.0e-12))
    else:
        pressure = sw / max(float(dim), 1.0)

    value_score = _robust_minmax(values_f)
    sum_weight_eff = _robust_minmax(values_f / (sw + 1.0e-12))
    max_weight_eff = _robust_minmax(values_f / (mw + 1.0e-12))
    light = 1.0 - _robust_minmax(sw)
    max_light = 1.0 - _robust_minmax(mw)
    low_pressure = 1.0 - _robust_minmax(pressure)

    trad_score = (
        TRAD_W["light"] * light
        + TRAD_W["low_pressure"] * low_pressure
        + TRAD_W["max_light"] * max_light
        + TRAD_W["max_weight_eff"] * max_weight_eff
        + TRAD_W["sum_weight_eff"] * sum_weight_eff
        + TRAD_W["value"] * value_score
    )

    trad_score = np.clip(trad_score, 0.0, 1.0)
    trad_order = np.lexsort((item_ids, -trad_score)).astype(np.int64)

    return np.ascontiguousarray(trad_order), trad_score
```

---

## 4.3 HYB_SCORE

### 目的

`HYB_SCORE` 是 LP/dual/reduced-cost/x_lp/core flag 的混合評分。這一條排序介於 RC 視角和 LP/RC baseline 之間。

### 定義

```python
dual_ratio = values / (weights @ dual_price)
reduced_pos = max(reduced_cost, 0)
x_lp = LP relaxation primal solution
core_flag = 1 if bucket == core else 0
```

score：

```python
hyb_score =
    0.35 * robust_minmax(dual_ratio)
  + 0.25 * robust_minmax(reduced_pos)
  + 0.25 * clip(x_lp, 0, 1)
  + 0.15 * core_flag
```

### 實作

如果你現有程式已有 `_score_values_for_method("hyb", ...)`，可以直接包一層：

```python
def build_hyb_order(
    values: np.ndarray,
    weights: np.ndarray,
    capacities: np.ndarray,
    base_payload: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray]:
    raw_score = _score_values_for_method(
        "hyb",
        values,
        weights,
        capacities,
        base_payload,
    )
    hyb_score = _robust_minmax(raw_score)

    item_ids = np.arange(hyb_score.size, dtype=np.int64)
    hyb_order = np.lexsort((item_ids, -hyb_score)).astype(np.int64)

    return np.ascontiguousarray(hyb_order), hyb_score
```

若要手寫：

```python
def build_hyb_order(
    values: np.ndarray,
    weights: np.ndarray,
    capacities: np.ndarray,
    base_payload: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray]:
    values_f = np.asarray(values, dtype=np.float64).ravel()
    weights_f = np.asarray(weights, dtype=np.float64)

    dual_price = np.asarray(base_payload["dual_price"], dtype=np.float64).ravel()
    reduced_cost = np.asarray(base_payload["reduced_cost"], dtype=np.float64).ravel()
    x_lp = np.asarray(base_payload["x_lp"], dtype=np.float64).ravel()
    bucket = np.asarray(base_payload["bucket"], dtype=np.int64).ravel()

    denom = weights_f @ dual_price
    dual_ratio = _safe_ratio_for_score(values_f, denom)
    reduced_pos = np.maximum(reduced_cost, 0.0)
    core_flag = (bucket == 1).astype(np.float64)

    hyb_score = (
        0.35 * _robust_minmax(dual_ratio)
        + 0.25 * _robust_minmax(reduced_pos)
        + 0.25 * np.clip(x_lp, 0.0, 1.0)
        + 0.15 * core_flag
    )

    hyb_score = np.clip(hyb_score, 0.0, 1.0)

    item_ids = np.arange(hyb_score.size, dtype=np.int64)
    hyb_order = np.lexsort((item_ids, -hyb_score)).astype(np.int64)

    return np.ascontiguousarray(hyb_order), hyb_score
```

---

## 5. 建立 order pool

在 `pseudo_utility()` 或 item evaluation 完成後，建立：

```python
rc_order, rc_score = build_rc_only_order(payload)

trad_order, trad_score = build_trad_only_best01_order(
    self.values,
    self.weights,
    self.capacities,
    payload,
)

hyb_order, hyb_score = build_hyb_order(
    self.values,
    self.weights,
    self.capacities,
    payload,
)
```

接著建立：

```python
self.order_pool = np.ascontiguousarray(
    np.vstack([
        rc_order,
        trad_order,
        hyb_order,
    ]).astype(np.int64)
)

self.order_pool_names = [
    "rc_only",
    "trad_only_best01",
    "hyb_score",
]
```

仍保留原本：

```python
self.cp_list = base_order
```

因為：

```text
order_switch_enabled = false 時，必須完全回到原本流程。
```

建議把分數也存進 payload：

```python
self.item_eval_payload["rc_only_score"] = rc_score
self.item_eval_payload["trad_only_best01_score"] = trad_score
self.item_eval_payload["hyb_score"] = hyb_score
self.item_eval_payload["order_pool_names"] = self.order_pool_names
```

---

## 6. 新增 q_order

目前原本有：

```python
q_table = np.zeros([pop_size, 9, 4])
```

代表：

```text
pop_size individuals
9 states
4 update actions
```

新增：

```python
q_order = np.zeros([pop_size, 9, 3], dtype=np.float64)
order_action_counts = np.zeros([pop_size, 3], dtype=np.int64)
```

3 個 order actions：

```text
0 = RC_ONLY
1 = TRAD_ONLY_BEST01
2 = HYB_SCORE
```

---

## 7. 新增 Numba action selector

### 7.1 選 order action

```python
@njit(cache=True)
def _select_q_order_action(
    q_order: np.ndarray,
    individual_id: int,
    state: int,
    order_count: int,
) -> int:
    best_value = q_order[individual_id, state, 0]

    for action in range(1, order_count):
        value = q_order[individual_id, state, action]
        if value > best_value:
            best_value = value

    tie_count = 0
    for action in range(order_count):
        if q_order[individual_id, state, action] == best_value:
            tie_count += 1

    pick = np.random.randint(0, tie_count)
    seen = 0

    for action in range(order_count):
        if q_order[individual_id, state, action] == best_value:
            if seen == pick:
                return action
            seen += 1

    return 0
```

特性：

```text
初始 q_order 全部是 0。
所以一開始三個 order action 會隨機 tie-break。
這可以自然探索 RC / TRAD / HYB。
```

### 7.2 更新 q_order

```python
@njit(cache=True)
def _update_q_order_value(
    q_order: np.ndarray,
    individual_id: int,
    state: int,
    action: int,
    reward: float,
    next_state: int,
    alpha: float,
    gamma: float,
    order_count: int,
) -> None:
    next_max = q_order[individual_id, next_state, 0]

    for a in range(1, order_count):
        if q_order[individual_id, next_state, a] > next_max:
            next_max = q_order[individual_id, next_state, a]

    current = q_order[individual_id, state, action]

    q_order[individual_id, state, action] = (
        current + alpha * (reward + gamma * next_max - current)
    )
```

reward 沿用原本更新 action 的 reward：

```text
reward = +1 if individual_best improved
reward = -1 otherwise
```

不要第一版就做複雜 reward。

---

## 8. 修改 main loop signature

原本主迴圈大致是：

```python
_bscasma_rl_main_loop_numba(
    ...,
    cp_list,
    ...,
    q_table,
    action_counts,
    ...
)
```

改成：

```python
_bscasma_rl_main_loop_numba(
    ...,
    cp_list,                # 保留，用於 disabled fallback
    order_pool,             # shape [3, items]
    q_order,                # shape [pop_size, 9, 3]
    order_action_counts,    # shape [pop_size, 3]
    order_switch_enabled,
    order_switch_alpha,
    order_switch_gamma,
    order_count,
    ...
)
```

如果 `order_switch_enabled == False`：

```python
selected_order = cp_list
```

如果 `order_switch_enabled == True`：

```python
order_action = _select_q_order_action(
    q_order,
    individual_id,
    state,
    order_count,
)

selected_order = order_pool[order_action]
order_action_counts[individual_id, order_action] += 1
```

---

## 9. main loop 內部流程

在每個 row 更新時：

```python
state = _state_for_row(
    pop_sol,
    row,
    gbest_sol,
    pop_size,
    items,
    density,
)
```

然後先選 order：

```python
if order_switch_enabled:
    order_action = _select_q_order_action(
        q_order,
        individual_id,
        state,
        order_count,
    )
    selected_order = order_pool[order_action]
    order_action_counts[individual_id, order_action] += 1
else:
    order_action = -1
    selected_order = cp_list
```

再選原本 update action：

```python
if np.random.random() < z:
    update_action = 0
else:
    update_action = _select_q_action_non_global(
        q_table,
        individual_id,
        state,
    )
```

然後照原本邏輯執行 SMA/SCA update。

最後 repair 時使用：

```python
_repair_bscasma_row_v2_inplace(
    ...,
    selected_order,
    ...
)
```

不是使用原本的 `cp_list`。

---

## 10. 哪些地方要改用 selected_order

以下所有吃 `cp_list` 的地方，都要改成吃 `selected_order`。

### 10.1 Repair v2

原本：

```python
_repair_bscasma_row_v2_inplace(..., cp_list, ...)
```

改成：

```python
_repair_bscasma_row_v2_inplace(..., selected_order, ...)
```

這是最重要的修改。

### 10.2 SMA global row

如果 `_sma_global_row()` 有使用 `cp_list` 掃描 item，也要改成：

```python
_sma_global_row(..., selected_order, ...)
```

### 10.3 Local search

如果 `local_search_enabled=True`：

```python
_local_search_bscasma_row_inplace(..., selected_order, ...)
```

但第一輪建議先關閉 local search。

### 10.4 Path relinking

如果 `archive_pr_enabled=True`：

```python
_path_relink_bscasma_inplace(..., selected_order, ...)
```

但第一輪建議先關閉 PR。

### 10.5 Restart

restart 時也要選 order。

簡化版：

```python
if order_switch_enabled:
    state = _state_for_row(...)
    order_action = _select_q_order_action(q_order, individual_id, state, order_count)
    selected_order = order_pool[order_action]
    order_action_counts[individual_id, order_action] += 1
else:
    selected_order = cp_list

_restart_bscasma_bucket_biased_row_inplace(
    ...,
    selected_order,
    bucket,
    ...
)

_repair_bscasma_row_v2_inplace(
    ...,
    selected_order,
    ...
)
```

注意：

```text
restart 的 bucket 還是使用原本 LP/RC bucket。
但 item 掃描順序使用 selected_order。
```

---

## 11. 原本 update q_table 不要刪

原本的：

```python
_update_q_value(q_table, ...)
```

仍然保留。

新增：

```python
_update_q_order_value(q_order, ...)
```

兩者同時更新。

一個控制：

```text
SMA/SCA update action
```

另一個控制：

```text
item order action
```

---

## 12. reward 定義

在每個 row 更新前，記錄：

```python
old_best = individual_best_fit[individual_id]
```

row 更新與 repair 後，如果：

```python
pop_fit[row] > individual_best_fit[individual_id]
```

則更新 individual best，並：

```python
reward = 1.0
```

否則：

```python
reward = -1.0
```

然後：

```python
next_state = _state_for_row(...)
```

更新：

```python
_update_q_value(
    q_table,
    individual_id,
    state,
    update_action,
    reward,
    next_state,
    alpha,
    gamma,
)

if order_switch_enabled:
    _update_q_order_value(
        q_order,
        individual_id,
        state,
        order_action,
        reward,
        next_state,
        order_switch_alpha,
        order_switch_gamma,
        order_count,
    )
```

---

## 13. 初始化策略

### 13.1 order_switch disabled

如果：

```yaml
order_switch_enabled: false
```

初始化完全沿用原本 `self.cp_list`。

### 13.2 RL_RC_TRAD_HYB enabled

如果：

```yaml
order_switch_enabled: true
order_switch_policy: rl_rc_trad_hyb
```

建議 mixed initialization 中，row 按照 round-robin 使用三條 order：

```python
order_id = row % 3
selected_order = self.order_pool[order_id]
```

也就是：

```text
row 0 使用 RC_ONLY
row 1 使用 TRAD_ONLY_BEST01
row 2 使用 HYB_SCORE
row 3 使用 RC_ONLY
row 4 使用 TRAD_ONLY_BEST01
row 5 使用 HYB_SCORE
...
```

原因：

```text
初始化階段就讓 population 包含三種不同 item preference 的解。
不要讓所有個體一開始都從同一條 order 出發。
```

如果 mixed init 有多種模式：

```text
deterministic greedy
LP rounding
RCL randomized greedy
random greedy
```

則每種模式中的 item 掃描順序都應該改用該 row 的 selected_order。

---

## 14. Core class 新增欄位

在 `BRLSMASCARLRCNumbaCore.__init__()` 新增參數：

```python
order_switch_enabled: bool = False
order_switch_policy: str = "none"
order_switch_alpha: float | None = None
order_switch_gamma: float | None = None
```

內部欄位：

```python
self.order_switch_enabled = bool(order_switch_enabled)
self.order_switch_policy = str(order_switch_policy)

self.order_switch_alpha = (
    float(alpha) if order_switch_alpha is None else float(order_switch_alpha)
)

self.order_switch_gamma = (
    float(gamma) if order_switch_gamma is None else float(order_switch_gamma)
)

self.order_pool = None
self.order_pool_names = []
self.q_order = np.zeros([self.pop_size, 9, 3], dtype=np.float64)
self.order_action_counts = np.zeros([self.pop_size, 3], dtype=np.int64)
```

檢查：

```python
if self.order_switch_enabled:
    if self.order_switch_policy != "rl_rc_trad_hyb":
        raise ValueError(
            "order_switch_enabled=true currently requires order_switch_policy='rl_rc_trad_hyb'"
        )
```

可以額外支援 debug policies：

```text
fixed_rc
fixed_trad
fixed_hyb
```

但正式版本先以 `rl_rc_trad_hyb` 為主。

---

## 15. Solver parser 修改

在 `solve()` 中解析：

```python
order_switch_enabled = _coerce_bool_param(
    raw_params.get("order_switch_enabled", False),
    name="order_switch_enabled",
)

order_switch_policy = str(raw_params.get("order_switch_policy", "none"))

order_switch_alpha_raw = raw_params.get("order_switch_alpha", None)
order_switch_gamma_raw = raw_params.get("order_switch_gamma", None)

order_switch_alpha = (
    None if order_switch_alpha_raw is None else float(order_switch_alpha_raw)
)

order_switch_gamma = (
    None if order_switch_gamma_raw is None else float(order_switch_gamma_raw)
)
```

傳入 core：

```python
core = BRLSMASCARLRCNumbaCore(
    ...,
    order_switch_enabled=order_switch_enabled,
    order_switch_policy=order_switch_policy,
    order_switch_alpha=order_switch_alpha,
    order_switch_gamma=order_switch_gamma,
)
```

---

## 16. Metadata 新增欄位

在 `SolveResult.metadata` 新增：

```python
order_action_counts = np.asarray(core.order_action_counts, dtype=np.int64)
order_totals = order_action_counts.sum(axis=0)
order_total = int(order_totals.sum())

metadata.update({
    "order_switch_enabled": bool(core.order_switch_enabled),
    "order_switch_policy": str(core.order_switch_policy),
    "order_pool_names": list(core.order_pool_names),

    "q_order_nonzero": int(np.count_nonzero(core.q_order)),

    "order_action_counts": order_totals.astype(int).tolist(),
    "order_total_count": order_total,

    "order_rc_count": int(order_totals[0]) if order_totals.size > 0 else 0,
    "order_trad_count": int(order_totals[1]) if order_totals.size > 1 else 0,
    "order_hyb_count": int(order_totals[2]) if order_totals.size > 2 else 0,

    "order_rc_ratio": (
        float(order_totals[0]) / max(float(order_total), 1.0)
        if order_totals.size > 0 else 0.0
    ),
    "order_trad_ratio": (
        float(order_totals[1]) / max(float(order_total), 1.0)
        if order_totals.size > 1 else 0.0
    ),
    "order_hyb_ratio": (
        float(order_totals[2]) / max(float(order_total), 1.0)
        if order_totals.size > 2 else 0.0
    ),
})
```

這些 metadata 是必須的，否則你後面無法檢查 RL 是否真的使用三條 order。

---

## 17. 建議測試項目與通過標準

## 17.1 Unit test：order pool 是 permutation

對任一 instance：

```python
assert order_pool.shape == (3, items)

for oid in range(3):
    assert sorted(order_pool[oid].tolist()) == list(range(items))
```

通過標準：

```text
三條 order 都必須是完整 permutation。
不能有重複 item。
不能漏 item。
```

---

## 17.2 Unit test：RC order 單調

```python
rc_order, rc_score = build_rc_only_order(payload)

for pos in range(items - 1):
    a = rc_order[pos]
    b = rc_order[pos + 1]
    assert rc_score[a] >= rc_score[b] - 1e-12
```

通過標準：

```text
RC_ONLY order 必須按照 rc_score 由大到小。
```

---

## 17.3 Unit test：TRAD order 單調

```python
trad_order, trad_score = build_trad_only_best01_order(...)

for pos in range(items - 1):
    a = trad_order[pos]
    b = trad_order[pos + 1]
    assert trad_score[a] >= trad_score[b] - 1e-12
```

通過標準：

```text
TRAD_ONLY_BEST01 order 必須按照 trad_score 由大到小。
```

---

## 17.4 Unit test：HYB order 單調

```python
hyb_order, hyb_score = build_hyb_order(...)

for pos in range(items - 1):
    a = hyb_order[pos]
    b = hyb_order[pos + 1]
    assert hyb_score[a] >= hyb_score[b] - 1e-12
```

通過標準：

```text
HYB_SCORE order 必須按照 hyb_score 由大到小。
```

---

## 17.5 Regression test：order_switch 關閉時結果不變

設定：

```yaml
order_switch_enabled: false
order_switch_policy: none
```

用同一 instance、同一 seed 跑舊版和新版。

通過標準：

```text
best_objective 完全一致。
best_solution 完全一致。
q_order_nonzero = 0。
order_total_count = 0。
```

這是最重要的 regression test。

如果這個測試失敗，表示你在 disabled 狀態仍然改壞了原本流程。

---

## 17.6 Integration test：q_order 有更新

設定：

```yaml
order_switch_enabled: true
order_switch_policy: rl_rc_trad_hyb
max_iterations: 50
```

跑一題一個 seed。

通過標準：

```text
q_order_nonzero > 0
order_total_count > 0
order_rc_count > 0
order_trad_count > 0
order_hyb_count > 0
```

如果 `q_order_nonzero = 0`，代表沒有更新 q_order。

如果某個 order count 永遠是 0，代表 action selection 或 tie-break 有問題。

---

## 17.7 Behavior test：order 使用比例不能崩掉

在 6 題 × 20 repeats × 500 iterations 下，統計：

```text
order_rc_ratio
order_trad_ratio
order_hyb_ratio
```

通過標準：

```text
每個比例都應該 >= 0.10。
建議合理範圍是 0.20 ~ 0.50。
```

參考預期：

```text
RC    約 33%
TRAD  約 33%
HYB   約 33%
```

不要求完全一樣，但不能有某一條 order 幾乎完全不用。

---

## 17.8 Feasibility test

每次求解後檢查：

```python
usage = weights.T @ best_solution
assert np.all(usage <= capacities)
```

通過標準：

```text
所有輸出 best_solution 都必須 feasible。
```

---

## 18. Benchmark 測試設計

### 18.1 Screening instances

先測以下 6 題：

```text
OR5x100-0.25_1
OR5x100-0.25_2
OR5x100-0.25_3
OR5x100-0.25_4
OR5x100-0.25_5
OR10x100-0.25_4
```

### 18.2 Seeds

```text
1000..1019
```

共 20 repeats。

### 18.3 Stop condition

```yaml
stop_condition:
  type: max_iterations
  max_iterations: 500
```

### 18.4 比較組

至少跑：

```text
BASE_CURRENT
RL_RC_TRAD_HYB
```

建議也跑：

```text
RL_RC_TRAD
RL_RC_TRAD_PRACTICAL
```

但如果只做本次修改驗證，最小比較組是：

```text
BASE_CURRENT
RL_RC_TRAD_HYB
```

### 18.5 指標

每題每方法輸出：

```text
Mean objective
Best objective
Worst objective
Std
PDev = (BKS - Mean objective) / BKS * 100
Hit rate = best_objective == BKS 的比例
order_action_counts
order_action_ratios
q_order_nonzero
runtime
total_obj_eval_count
```

---

## 19. 預期結果

如果本地實作與本規格一致，在 6 題 × 20 repeats × 500 iterations 下，方向應該接近：

```text
BASE_CURRENT mean PDev      ≈ 0.145762%
RL_RC_TRAD_HYB mean PDev    ≈ 0.068189%
```

預期改善：

```text
absolute improvement ≈ 0.077573 percentage points
relative PDev reduction ≈ 53%
```

逐題預期方向：

```text
OR5x100-0.25_1:
    RL_RC_TRAD_HYB 應明顯優於 BASE。

OR5x100-0.25_2:
    RL_RC_TRAD_HYB 應優於 BASE，但 PRACTICAL 版本可能更好。

OR5x100-0.25_3:
    改善可能較小，這題不一定大幅勝出。

OR5x100-0.25_4:
    RL_RC_TRAD_HYB 應明顯優於 BASE。

OR5x100-0.25_5:
    RL_RC_TRAD_HYB 應優於 BASE。

OR10x100-0.25_4:
    RL_RC_TRAD_HYB 應優於 BASE，但 PRACTICAL 版本可能更好。
```

不要要求數字完全一致，因為 Numba 隨機序列、初始化細節、tie-break 細節可能造成差異。

但方向上應該是：

```text
RL_RC_TRAD_HYB 的平均 PDev 明顯低於 BASE_CURRENT。
```

---

## 20. 統計檢定

使用 paired Wilcoxon。

```python
from scipy.stats import wilcoxon

base = df[df.config == "BASE_CURRENT"].set_index(["problem_id", "seed"])["pdev"]
method = df[df.config == "RL_RC_TRAD_HYB"].set_index(["problem_id", "seed"])["pdev"]

common = base.index.intersection(method.index)

stat_two, p_two = wilcoxon(
    method.loc[common],
    base.loc[common],
    alternative="two-sided",
)

stat_less, p_less = wilcoxon(
    method.loc[common],
    base.loc[common],
    alternative="less",
)
```

通過標準：

```text
p_less < 0.05
```

參考預期：

```text
p_less 應遠小於 0.05。
```

---

## 21. Gate 條件

本地正式驗收建議用以下 gate：

```text
1. RL_RC_TRAD_HYB mean PDev < BASE_CURRENT mean PDev。
2. 相對 PDev reduction >= 20%。
3. one-sided Wilcoxon p < 0.05。
4. q_order_nonzero > 0。
5. order_rc_ratio >= 0.10。
6. order_trad_ratio >= 0.10。
7. order_hyb_ratio >= 0.10。
8. 所有輸出 best_solution feasible。
9. order_switch_enabled=false 時，結果必須與原版完全一致。
```

如果 1–8 通過但第 9 點不通過，不能合併，因為代表改動破壞了 baseline。

---

## 22. 常見錯誤

### 錯誤 1：把三條 order 線性平均成一條

錯誤做法：

```python
score = 0.33 * rc_score + 0.33 * trad_score + 0.34 * hyb_score
cp_list = argsort(score)
```

這不是 RL_RC_TRAD_HYB。

正確做法：

```text
保留三條 order。
每個 individual 每次更新時，用 q_order 選其中一條。
```

---

### 錯誤 2：RC_ONLY 用錯公式

錯誤：

```python
rc_score = 0.5 * reduced_cost + 0.5 * x_lp
```

正確：

```python
rc_score = robust_minmax(reduced_cost)
```

---

### 錯誤 3：只在初始化用 selected_order，repair 仍用 cp_list

這樣效果會大幅下降。

正確：

```text
repair / add / drop / swap 必須用 selected_order。
```

---

### 錯誤 4：只更新原本 q_table，忘記更新 q_order

必須同時更新：

```text
q_table  控制 update action
q_order  控制 item order action
```

---

### 錯誤 5：排序 population 後 individual_id 錯亂

你目前 q_table 是以 `individual_id` 為 key，不是以 row index 為 key。

所以 population 排序時：

```text
pop_sol
pop_fit
individual_ids
row_hamming
```

都要一起排序。

q_order 查詢也必須使用：

```python
individual_id = individual_ids[row]
```

不要直接用：

```python
row
```

---

### 錯誤 6：order_switch disabled 時仍使用 order_pool

如果：

```yaml
order_switch_enabled: false
```

必須使用原本的：

```python
self.cp_list
```

不能走 order_pool。

---

## 23. 最小可行修改摘要

最小可行改動如下：

```text
1. 新增 build_rc_only_order。
2. 新增 build_trad_only_best01_order。
3. 新增 build_hyb_order。
4. 在 item evaluation 後建立：
   order_pool = [rc_order, trad_order, hyb_order]
5. 新增 q_order = zeros([pop_size, 9, 3])。
6. 新增 order_action_counts = zeros([pop_size, 3])。
7. 在每個 row 更新前：
   state = compute_state(...)
   order_action = select_q_order_action(...)
   selected_order = order_pool[order_action]
8. 所有 repair / swap / restart / local search / PR 使用 selected_order。
9. 用同一個 reward 更新 q_table 和 q_order。
10. metadata 輸出 q_order_nonzero、order counts、order ratios。
11. 跑 unit tests。
12. 跑 6 題 × 20 repeats × 500 iterations screening。
```

---

## 24. 建議命名

Config 名稱：

```text
RL_RC_TRAD_HYB
```

metadata：

```json
{
  "order_switch_enabled": true,
  "order_switch_policy": "rl_rc_trad_hyb",
  "order_pool_names": ["rc_only", "trad_only_best01", "hyb_score"]
}
```

論文或實驗表可以寫成：

```text
RL-based complementary item-order selection using RC, traditional CP, and hybrid LP-dual score.
```

中文：

```text
基於強化學習的互補物品排序選擇機制。
```
