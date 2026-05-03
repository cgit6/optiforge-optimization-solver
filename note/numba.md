你現在完成的是 **資料入口整理**，但演算法本體還沒有真的 Numba 化。下一步不要急著在 class method 上加 `@njit`；你要做的是把目前 `BSMANumbaCore` 拆成：

```text
Python 外層：
    BSMANumbaSolver
    BSMANumbaCore
    pseudo_utility / linprog
    SolveResult
    debug trace / metadata

Numba 核心：
    initial_pop_numba
    repair_numba
    sort_population_numba
    bsma_kernel
```

你目前的 `BSMANumbaCore` 仍包含 `linprog`、`copy.deepcopy`、`dict` trace、`hashlib` digest、class state mutation，這些都不應該進 Numba kernel。`pseudo_utility()` 裡的 `scipy.optimize.linprog` 也應該繼續留在 Python 層，只把算好的 `cp_list` 傳進 Numba。

---

## 接下來的建議修改順序

### 1. 先建立 reference test，不然後面會失控

在改 Numba 之前，先確保你有一組固定 seed 的對照測試：

```python
result_old = BSMANumbaSolver().solve(problem, config, rng)
result_new = BSMANumbaSolver().solve(problem, config, rng)

assert result_old.best_objective == result_new.best_objective
assert np.array_equal(result_old.best_solution, result_new.best_solution)
```

但要注意：一旦你重寫 random sampling，亂數呼叫順序可能改變，所以「完全相同 solution」不一定永遠合理。第一階段可以先追求完全一致，後面如果為了效能改亂數流程，至少要保證：

```python
assert result_new.feasible
assert result_new.best_objective >= 某個合理門檻
```

---

## 2. 新增 Numba-only helper function，不要先動 class

先加這些純函式：

```python
from numba import njit
import numpy as np


@njit(cache=True)
def _sample_two_indices(pop_size: int, exclude_i: int) -> tuple[int, int]:
    a = np.random.randint(0, pop_size - 1)
    if a >= exclude_i:
        a += 1

    b = np.random.randint(0, pop_size - 1)
    if b >= exclude_i:
        b += 1

    while b == a:
        b = np.random.randint(0, pop_size - 1)
        if b >= exclude_i:
            b += 1

    return a, b
```

這是為了替代你目前最不適合 Numba 的這段：

```python
np.random.choice(list(set(range(0, self.pop_size)) - {i}), 2, replace=False)
```

這段在最內層 loop 裡反覆建立 `set`、`list`，對 Python 慢，對 Numba 也不友善。

---

## 3. 把 fitness 計算改成純 loop

目前你多處使用：

```python
np.sum(np.multiply(self.values, population[i]))
```

或：

```python
np.sum(np.multiply(self.values, self.pop_sol[i]))
```

這可以改成：

```python
@njit(cache=True)
def _fitness(sol: np.ndarray, values: np.ndarray, items: int) -> int:
    total = 0
    for j in range(items):
        if sol[j] == 1:
            total += values[j]
    return total
```

Numba 版通常比較適合這種 scalar loop，而不是在小函式內一直建立中間 array。

---

## 4. 重寫 `repair()` 成 Numba 版本

目前 `repair()` 還有幾個問題：

```python
resource_consumption = np.sum(np.multiply(self.weights.T, trial_sol), axis=1)
for i in np.flip(self.cp_list):
```

`weights.T`、`np.multiply`、`np.sum(axis=1)`、`np.flip` 都不是不能用，但不是最佳的 Numba kernel 形式。建議改成純 loop：

```python
@njit(cache=True)
def _repair_numba(
    trial_sol: np.ndarray,
    trial_fit: int,
    values: np.ndarray,
    weights: np.ndarray,
    capacities: np.ndarray,
    cp_list: np.ndarray,
    resource: np.ndarray,
    items: int,
    dim: int,
) -> int:
    for d in range(dim):
        resource[d] = 0

    for j in range(items):
        if trial_sol[j] == 1:
            for d in range(dim):
                resource[d] += weights[j, d]

    # remove by reversed cp_list
    for pos in range(items - 1, -1, -1):
        over = False
        for d in range(dim):
            if resource[d] > capacities[d]:
                over = True
                break

        if not over:
            break

        j = cp_list[pos]
        if trial_sol[j] == 1:
            trial_sol[j] = 0
            trial_fit -= values[j]
            for d in range(dim):
                resource[d] -= weights[j, d]

    # add by cp_list
    for pos in range(items):
        j = cp_list[pos]

        if trial_sol[j] == 0:
            feasible = True
            for d in range(dim):
                if resource[d] + weights[j, d] > capacities[d]:
                    feasible = False
                    break

            if feasible:
                trial_sol[j] = 1
                trial_fit += values[j]
                for d in range(dim):
                    resource[d] += weights[j, d]
            else:
                break

    return trial_fit
```

這一步是 Numba 化的核心之一。

---

## 5. 修正 `pop_sol` 的 dtype，但要先改 local search 中間值

你現在的 `pop_sol` 預設是 `float64`：

```python
population = np.zeros([self.pop_size, self.items])
```

理論上 solution 是 0/1，所以應該改成：

```python
pop_sol = np.zeros((pop_size, items), dtype=np.int8)
```

但不能直接改，因為你目前 local search 會先把浮點中間值寫進 `self.pop_sol[i, j]`：

```python
self.pop_sol[i, j] = self.Gbest_sol[j] + vb[j] * (...)
...
np.tanh(self.pop_sol[i, j])
```

這會讓 `pop_sol` 暫時不是 0/1。你要改成：

```python
if r < p:
    x = gbest_sol[j] + vb_j * (
        W[i, j] * pop_sol[a_idx, j] - pop_sol[b_idx, j]
    )
else:
    x = vc_j * pop_sol[i, j]

if np.random.random() < abs(np.tanh(x)):
    pop_sol[i, j] = 1
else:
    pop_sol[i, j] = 0
```

也就是：

```text
浮點中間值：x: float64
二元解：pop_sol[i, j]: int8
```

這一步做完後，`pop_sol` 才能安全改成 `int8`。

---

## 6. 重寫初始化族群

目前 `initial_pop()` 是 class method，而且會直接寫 `self.pop_fit`。建議改成 Numba 函式直接回傳 `pop_sol, pop_fit`：

```python
@njit(cache=True)
def _initial_pop_numba(
    pop_size: int,
    items: int,
    dim: int,
    values: np.ndarray,
    weights: np.ndarray,
    capacities: np.ndarray,
    cp_list: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    pop_sol = np.zeros((pop_size, items), dtype=np.int8)
    pop_fit = np.zeros(pop_size, dtype=np.int64)
    resource = np.zeros(dim, dtype=np.int64)

    for i in range(pop_size):
        for d in range(dim):
            resource[d] = 0

        for pos in range(items):
            j = cp_list[pos]

            if np.random.random() < 0.5:
                feasible = True
                for d in range(dim):
                    if resource[d] + weights[j, d] > capacities[d]:
                        feasible = False
                        break

                if feasible:
                    pop_sol[i, j] = 1
                    pop_fit[i] += values[j]
                    for d in range(dim):
                        resource[d] += weights[j, d]

    return pop_sol, pop_fit
```

這會取代目前 `initial_pop()` 裡面的 `np.zeros`、`np.all`、`np.sum(np.multiply(...))` 組合。

---

## 7. 重寫排序，不要每輪配置新陣列

你現在的 `sort_pop()` 每次都：

```python
pop_sol = np.zeros([self.pop_size, self.items])
pop_fit = np.zeros([self.pop_size])
sorted_indices = np.argsort(self.pop_fit)[::-1]
```

而且 `pop_fit = np.zeros([self.pop_size])` 會變成 `float64`。

建議先用 in-place selection sort，因為你的 `pop_size` 預設只有 20：

```python
@njit(cache=True)
def _sort_population_desc(
    pop_sol: np.ndarray,
    pop_fit: np.ndarray,
    pop_size: int,
    items: int,
) -> None:
    for i in range(pop_size - 1):
        best = i
        best_fit = pop_fit[i]

        for k in range(i + 1, pop_size):
            if pop_fit[k] > best_fit:
                best = k
                best_fit = pop_fit[k]

        if best != i:
            tmp_fit = pop_fit[i]
            pop_fit[i] = pop_fit[best]
            pop_fit[best] = tmp_fit

            for j in range(items):
                tmp = pop_sol[i, j]
                pop_sol[i, j] = pop_sol[best, j]
                pop_sol[best, j] = tmp
```

---

## 8. 寫真正的 `bsma_kernel`

最後才把整個 `run()` 內層搬成一個 Numba 函式：

```python
@njit(cache=True)
def _bsma_kernel(
    items: int,
    dim: int,
    glbal_best: int,
    values: np.ndarray,
    weights: np.ndarray,
    capacities: np.ndarray,
    cp_list: np.ndarray,
    seed: int,
    pop_size: int,
    z: float,
    max_iter: int,
) -> tuple[np.ndarray, int]:
    np.random.seed(seed)

    pop_sol, pop_fit = _initial_pop_numba(
        pop_size, items, dim, values, weights, capacities, cp_list
    )

    W = np.zeros((pop_size, items), dtype=np.float64)
    resource = np.zeros(dim, dtype=np.int64)

    _sort_population_desc(pop_sol, pop_fit, pop_size, items)

    gbest_sol = pop_sol[0].copy()
    gbest_fit = pop_fit[0]

    for iteration in range(max_iter):
        worst_fit = pop_fit[pop_size - 1]
        best_fit = pop_fit[0]

        if best_fit - worst_fit > 0:
            s_val = float(best_fit - worst_fit)
        else:
            s_val = 0.0001

        for i in range(pop_size):
            ratio = np.log10((best_fit - pop_fit[i]) / s_val + 1.0)
            for j in range(items):
                rnd = np.random.random()
                if i < pop_size / 2:
                    W[i, j] = 1.0 + rnd * ratio
                else:
                    W[i, j] = 1.0 - rnd * ratio

        a = np.arctanh(-1.0 * ((iteration + 1) / max_iter) + 1.0)
        b = 1.0 - (iteration + 1) / max_iter

        for i in range(pop_size):
            if np.random.random() < z:
                for j in range(items):
                    pop_sol[i, j] = 0

                for d in range(dim):
                    resource[d] = 0

                for pos in range(items):
                    j = cp_list[pos]
                    if np.random.random() < 0.5:
                        feasible = True
                        for d in range(dim):
                            if resource[d] + weights[j, d] > capacities[d]:
                                feasible = False
                                break

                        if feasible:
                            pop_sol[i, j] = 1
                            for d in range(dim):
                                resource[d] += weights[j, d]
            else:
                p = np.tanh(abs(pop_fit[i] - gbest_fit))

                for j in range(items):
                    r = np.random.random()
                    a_idx, b_idx = _sample_two_indices(pop_size, i)

                    vb_j = np.random.uniform(-a, a)
                    vc_j = np.random.uniform(-b, b)

                    if r < p:
                        x = gbest_sol[j] + vb_j * (
                            W[i, j] * pop_sol[a_idx, j] - pop_sol[b_idx, j]
                        )
                    else:
                        x = vc_j * pop_sol[i, j]

                    if np.random.random() < abs(np.tanh(x)):
                        pop_sol[i, j] = 1
                    else:
                        pop_sol[i, j] = 0

            fit = _fitness(pop_sol[i], values, items)
            pop_fit[i] = _repair_numba(
                pop_sol[i],
                fit,
                values,
                weights,
                capacities,
                cp_list,
                resource,
                items,
                dim,
            )

        _sort_population_desc(pop_sol, pop_fit, pop_size, items)

        if pop_fit[0] > gbest_fit:
            gbest_fit = pop_fit[0]
            for j in range(items):
                gbest_sol[j] = pop_sol[0, j]

        if gbest_fit == glbal_best:
            return gbest_sol, gbest_fit

    return gbest_sol, gbest_fit
```

這個 kernel 才是「完全支援 Numba」的目標。

---

## 9. `BSMANumbaCore.run()` 變成薄 wrapper

你的 class 不需要消失，只是不要讓 class 本身進 Numba：

```python
def run(self) -> tuple[np.ndarray, int]:
    seed = 0 if self.seed is None else int(self.seed)

    return _bsma_kernel(
        int(self.items),
        int(self.dim),
        int(self.glbal_best),
        self.values,
        self.weights,
        self.capacities,
        self.cp_list,
        seed,
        int(self.pop_size),
        float(self.z),
        int(self.max_iter),
    )
```

這樣外層仍然保留 `BSMANumbaSolver.solve()`、`SolveResult`、`linprog_runtime`、`metadata` 等架構。你目前 `solve()` 裡建立 `core`、呼叫 `core.run()`、再包成 `SolveResult` 的設計可以繼續保留。

---

## 10. 暫時不要做的事

先不要做：

```python
@njit
class BSMANumbaCore:
    ...
```

也不要急著用：

```python
@njit(parallel=True)
```

原因是你的演算法在更新 `pop_sol[i]` 時會讀 `pop_sol[a_idx]` / `pop_sol[b_idx]`，如果直接平行化 `i` 迴圈，會有資料競態，而且演算法行為會改變。

如果之後要平行化，必須改成雙緩衝：

```text
old_pop_sol -> 只讀
new_pop_sol -> 只寫
```

這屬於下一階段，不是「先讓 Numba 跑起來」的階段。

---

## 最簡潔的 commit 規劃

我會這樣切：

```text
Commit 2:
    新增 Numba helper functions
    _fitness
    _sample_two_indices
    _sort_population_desc
    _repair_numba

Commit 3:
    改 pop_sol 成 int8
    local search 改成 x: float64 中間值
    不再把浮點中間值寫回 pop_sol

Commit 4:
    新增 _initial_pop_numba
    保留舊 initial_pop 作為對照，先不刪

Commit 5:
    新增 _bsma_kernel
    BSMANumbaCore.run() 改成呼叫 _bsma_kernel

Commit 6:
    移除或隔離 _loop_trace / digest / deepcopy
    debug 版本另外保留，不進 Numba kernel

Commit 7:
    benchmark
    比較 Python 版、Numba 第一次呼叫、Numba warm run
```
