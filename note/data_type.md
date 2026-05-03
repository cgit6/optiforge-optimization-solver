**不要只是「全部換成 NumPy dtype」；應該先把資料邊界固定，再逐步改 hot loop。**

你的情況建議流程是：

```text
1. 先固定所有輸入 dtype / shape / contiguous layout
2. 保留原本 Python 版作為 reference
3. 把內層計算改成 Numba-friendly loop
4. 再加 @njit
5. 最後才做更激進的配置減少、排序最佳化、平行化
```

---

## 1. 先統一 dtype 是對的，但不要用 `dtype=int`

你現在在 `solve()` 裡是：

```python
np.asarray(problem.values, dtype=int)
np.asarray(problem.weights, dtype=int)
np.asarray(problem.capacities, dtype=int)
```

`dtype=int` 會依平台變成不同寬度，建議改成明確型別：

```python
values = np.ascontiguousarray(problem.values, dtype=np.int64)
weights = np.ascontiguousarray(problem.weights, dtype=np.int64)
capacities = np.ascontiguousarray(problem.capacities, dtype=np.int64)
```

`cp_list` 也建議明確轉：

```python
cp_list = np.ascontiguousarray(cp_list, dtype=np.int64)
```

這一步是合理的第一步。你目前 `values`、`weights`、`capacities` 都是進入 `BSMAV1008Core` 前才轉成 NumPy array，這個邊界很適合繼續保留，只是 dtype 要更明確。

---

## 2. `pop_fit` 應該先改成 `int64`

這個可以很早改，風險低。

你現在初始化時是：

```python
self.pop_fit = np.zeros([self.pop_size], dtype=int)
```

但在 `sort_pop()` 裡又變成：

```python
pop_fit = np.zeros([self.pop_size])
```

後者預設是 `float64`，會把 fitness 從整數轉成浮點。這不利於 Numba，也沒有必要。

建議改成：

```python
pop_fit = np.zeros(self.pop_size, dtype=np.int64)
```

---

## 3. `pop_sol` 不能直接粗暴改成 `int8`

這是你這份程式最容易踩雷的地方。

直覺上 `pop_sol` 是 0/1 解，所以好像可以改成：

```python
pop_sol = np.zeros((pop_size, items), dtype=np.int8)
```

但你目前在 local search 裡有一段會把**連續值**暫時寫進 `self.pop_sol[i, j]`：

```python
self.pop_sol[i, j] = self.Gbest_sol[j] + vb[j] * (
    self.W[i, j] * self.pop_sol[a_idx, j] - self.pop_sol[b_idx, j]
)

if np.random.uniform(0.0, 1.0) < np.abs(np.tanh(self.pop_sol[i, j])):
    self.pop_sol[i, j] = 1
else:
    self.pop_sol[i, j] = 0
```

如果你把 `pop_sol` 直接改成 `int8`，中間的浮點值會被截斷，演算法行為會變。

正確改法是：**中間值用 local float 變數，不要寫回 `pop_sol`；最後只把 0/1 寫回去。**

例如：

```python
if r < p:
    x = Gbest_sol[j] + vb_j * (
        W[i, j] * pop_sol[a_idx, j] - pop_sol[b_idx, j]
    )
else:
    x = vc_j * pop_sol[i, j]

if np.random.random() < abs(np.tanh(x)):
    pop_sol[i, j] = 1
else:
    pop_sol[i, j] = 0
```

這樣 `pop_sol` 才能安全改成：

```python
pop_sol = np.zeros((pop_size, items), dtype=np.int8)
```

這一步要放在「改 code 邏輯」階段，不是單純 dtype 替換階段。

---

## 4. 建議的 dtype 配置

你這個問題可以先定成：

| 資料                             |               建議 dtype | 原因                      |
| ------------------------------ | ---------------------: | ----------------------- |
| `values`                       |             `np.int64` | fitness 加總，避免 overflow  |
| `weights`                      |             `np.int64` | resource consumption 加總 |
| `capacities`                   |             `np.int64` | 與 weights 比較            |
| `cp_list`                      |             `np.int64` | index array             |
| `pop_sol`                      | `np.int8` 或 `np.uint8` | 只存 0/1                  |
| `pop_fit`                      |             `np.int64` | objective value         |
| `W`                            |           `np.float64` | 權重係數                    |
| `a`, `b`, `p`, `vb`, `vc`, `x` |              `float64` | local search 連續值        |
| `resource_consumption`         |             `np.int64` | 多維限制加總                  |

---

## 5. 我會建議你分三個 commit 做

### Commit 1：只整理輸入 dtype，不改演算法邏輯

做這些：

```python
values = np.ascontiguousarray(problem.values, dtype=np.int64)
weights = np.ascontiguousarray(problem.weights, dtype=np.int64)
capacities = np.ascontiguousarray(problem.capacities, dtype=np.int64)
```

並把所有 `dtype=int` 改成 `dtype=np.int64`。

這一步應該不改結果。

---

### Commit 2：修正內部陣列 dtype，但保留 Python 執行

做這些：

```python
self.W = np.zeros((self.pop_size, self.items), dtype=np.float64)
self.pop_fit = np.zeros(self.pop_size, dtype=np.int64)
```

`sort_pop()` 裡也同步修正：

```python
pop_sol = np.zeros((self.pop_size, self.items), dtype=np.int8)
pop_fit = np.zeros(self.pop_size, dtype=np.int64)
```

但 `pop_sol` 要不要在這個 commit 就改成 `int8`，取決於你是否已經把 local search 的中間浮點值改成 local variable。沒有改之前，不要直接改。

---

### Commit 3：改 hot loop 邏輯，準備 Numba

這一階段再做：

* 把 `np.random.choice(list(set(...)))` 改成整數抽樣。
* 把 `np.sum(np.multiply(...))` 改成手寫 loop。
* 把 `np.flip(cp_list)` 改成倒序 index。
* 把 `vb` / `vc` array 改成 scalar random，或至少先移出不必要配置。
* 把 `repair()` 改成純 array + scalar 函式。
* 把 `run()` 的核心抽成 `@njit` 函式。

---

## 6. 關鍵原則

你目前的外層架構可以保留：

```text
ProblemModel / config / SolveResult / linprog / metadata
```

這些維持 Python object 沒問題。

要改的是內層 kernel：

```text
values, weights, capacities, cp_list, pop_sol, pop_fit, W
```

全部變成固定 dtype 的 NumPy array，然後只用 scalar、array indexing、for loop。

所以答案是：

**是，先整理成 NumPy dtype 是正確方向；但不要把它當成獨立完成的效能優化。真正有效的流程是先固定 dtype 與資料邊界，再把會被 Numba 編譯的內層邏輯改成純數值 kernel。**

尤其注意：`pop_sol` 不能在尚未改 local search 中間值邏輯前直接改成 `int8`。這是最需要先處理的正確性風險。
