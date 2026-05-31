# 物品評估 / CP 值方法實驗整理

## 1. 目的與背景

本文件整理目前針對 MKP solver 中「物品評估方法」做過的所有實驗項目。這裡的物品評估主要指：如何產生 `cp_list`，也就是 item 的優先順序。`cp_list` 在目前 solver 中會影響：

- initialization：初始解建構時 item 的嘗試順序；
- repair：不可行解修復時低順位 item 優先被移除；
- add/improvement：可行解改善時高順位 item 優先被加入；
- bounded swap：嘗試用高順位 item 替換低順位 item；
- restart：停滯重啟時依 bucket / CP order biased 加入 item；
- guided binary conversion, GBC：若啟用，item 的 LP / score 訊號也會影響二值化機率。

目前正式保留下來的 baseline 是：

```yaml
z: 0.01
a: 2.5
ctf: abs_pow_16
repair_passes: 2
repair_swap_limit: 4
mixed_init_enabled: true
restart_enabled: true
restart_window: 40
restart_ratio: 0.25
```

也就是：

```text
LP/RC order + deterministic order + Repair 2.0 + mixed init + restart + swap=4
```

本系列實驗的核心問題是：

> 如果能更準確估計 item 是否應該進入高品質解，solver 是否能在 500 次迭代內更接近甚至追平 QPSO*？

前面的 ORACLE_CP ablation 顯示：如果 `cp_list` 直接由最佳解產生，solver 可以在 500 iterations 內穩定達到 BKS。因此目前瓶頸很可能不是主搜尋框架完全無效，而是 item preference / CP 排序還不夠接近 optimal item structure。

---

## 2. 評估指標與實驗設定

### 2.1 PDev

所有結果使用文獻一致的 PDev：

```text
PDev = (BKS - Mean objective) / BKS × 100%
```

其中：

- BKS：該 instance 的 best-known solution；
- Mean objective：多個 seeds 下 best objective 的平均；
- PDev 越低越好；
- PDev = 0 表示平均結果等於 BKS。

### 2.2 實驗層級

目前已完成的測試主要分成四輪：

| 輪次 | 目的 | 題目數 | Seeds | Iterations | 備註 |
|---|---:|---:|---:|---:|---|
| Oracle CP ablation | 驗證 CP 是否為關鍵瓶頸 | 3 | 20 | 500 | 用最佳解產生 CP |
| 第一輪 screening | 測多種新 CP 方法 | 3 | 5 | 500 | 粗篩方向 |
| 第二輪 gated screening | 測 gated 版本 | 5 | 10 | 500 | 檢查穩定性 |
| 第三輪 V2 screening | 測 dim-aware 版本 | 5 | 5 | 500 | 檢查 FREQ 修正版 |

目前這些都應視為 **screening pilot**，不是完整 formal benchmark。尚未完成完整 CB × 20 seeds × 5000 iterations 的 formal 結論。

---

## 3. Baseline：LP/RC Order

### 3.1 方法邏輯

原本正式 baseline 的 item evaluation 流程是：

```text
1. 解 LP relaxation：
   max p^T x
   s.t. W^T x <= capacity
        0 <= x_j <= 1

2. 取得：
   x_lp[j]
   dual_price[i]
   weighted_cost[j] = Σ_i dual_price[i] * weight[j,i]
   efficiency[j] = profit[j] / weighted_cost[j]
   reduced_cost[j] = profit[j] - weighted_cost[j]

3. 依 x_lp / reduced_cost 分 bucket：
   bucket = 0: strong-take
   bucket = 1: core
   bucket = 2: weak-take

4. 排序：
   bucket 小的優先；
   同 bucket 內 efficiency 高的優先。
```

### 3.2 與早期算法差異

早期較接近單純 pseudo-utility / efficiency 排序，而 LP/RC order 加入了：

- LP primal solution `x_lp`；
- dual price / shadow price；
- reduced cost；
- strong/core/weak bucket。

因此它比單純 `profit / weighted resource` 更完整。

### 3.3 表現

LP/RC order 是目前正式 baseline。它比早期 pseudo-utility 更穩，也支撐後續 Repair 2.0、mixed init、restart 的改善。

但 Oracle CP 實驗顯示，LP/RC order 和真正 optimal item order 仍有差距，因此還有改進空間。

### 3.4 目前結論

```text
保留。作為所有新方法的 baseline。
```

---

## 4. Deterministic Order 與 Group Shuffle

### 4.1 Deterministic Order

`eval_group_shuffle = false` 時，`cp_list` 是 deterministic：

```text
bucket priority + efficiency descending + item_id tie-breaker
```

### 4.2 Group Shuffle

Group shuffle 的想法是：如果多個 item 的 bucket 和 rounded efficiency 相同，則在 group 內 shuffle，增加多樣性。

流程：

```text
1. 依 bucket + rounded efficiency 找到等價 group。
2. 對每個 group 內部做 random shuffle。
3. 產生略有變動的 cp_list。
```

### 4.3 與 baseline 差異

- baseline：完全 deterministic；
- group shuffle：在局部相同分數區塊中加入隨機性。

### 4.4 表現

先前測試顯示 group shuffle 沒有穩定改善，反而會破壞 LP/RC order 的穩定性。

### 4.5 目前結論

```text
Deterministic order 保留。
Group shuffle 不保留。
```

---

## 5. Dynamic Weight Drop

### 5.1 方法邏輯

原本 repair drop 是依 `cp_list` 從後往前刪 item。Dynamic weight drop 改成根據目前超載 constraint 動態計算 item 的 drop merit。

概念：

```text
如果某 item 價值低，而且對目前超載的 constraints 負擔大，則優先刪掉。
```

可能的 drop score：

```text
drop_score[j] = low_value_score[j] × overload_contribution[j]
```

### 5.2 與 baseline 差異

- baseline：固定依 cp_list 刪；
- dynamic weight drop：每次 repair 根據目前 resource violation 動態選刪除 item。

### 5.3 表現

測試結果不穩，部分題目退步。原因可能是動態 drop 太局部，容易為了修復當前超載而丟掉其實對最終解重要的 item。

### 5.4 目前結論

```text
不保留。
```

---

## 6. Score Scaffold：CND / DUAL / RC / HYB / LAG × Rank / Weight

### 6.1 方法邏輯

Score scaffold 是一個診斷型實驗，用來比較不同 item score 訊號：

| Score | 意義 |
|---|---|
| CND | constraint normalized density / resource 消耗型分數 |
| DUAL | LP dual price weighted efficiency |
| RC | reduced-cost based score |
| HYB | hybrid score，混合多個訊號 |
| LAG | Lagrangian-style score |

同時比較兩種使用方式：

| 使用方式 | 意義 |
|---|---|
| rank | 只用 score 排序 |
| weight | score 直接作為機率或強度權重 |

### 6.2 與 baseline 差異

baseline 主要是 `bucket + efficiency`。Score scaffold 測試的是：如果改用其他數學分數，或者把 score 當連續權重而非排序，是否會更好。

### 6.3 表現

結果中 `HYB-rank` 最好，但在 OR10x500 上 PDev 退步約 `0.0279%`，超過原先設定的 `0.02%` regression gate。

### 6.4 目前結論

```text
不帶回正式 solver。
保留為診斷結果。
```

---

## 7. Guided Binary Conversion, GBC

### 7.1 方法邏輯

GBC 不是單純改 `cp_list`，而是改 continuous-to-binary 的機率。

原本二值化大致是：

```text
p = CTF(continuous_value)
bit = 1 if random() < p else 0
```

GBC 改成：

```text
p = CTF(continuous_value)
p += λ_lp     × (x_lp[j] - 0.5)
p += λ_bucket × bucket_bias[j]
p += λ_slack  × slack_score[j]
p = clip(p, 0, 1)
```

其中：

```text
bucket_bias = +1 for strong,
               0 for core,
              -1 for weak.
```

### 7.2 與 baseline 差異

baseline 中 LP/RC 訊號主要透過 `cp_list` 影響 repair / initialization。GBC 則讓 LP 訊號也直接影響每次 SMA/SCA 更新後的二值化。

### 7.3 表現

Reduced pilot 顯示 GBC 有明顯改善，例如 combined QPSO gap 從 `109.8` 降到 `73.17`。但 formal benchmark 尚未完整完成。

在後續測試中也觀察到：GBC 有時改善 BASE，但沒有穩定證明超過 QPSO*。

### 7.4 目前結論

```text
有潛力。
尚未正式寫入 param_20。
適合作為 CORE_SCORE_CP 後續組合候選。
```

---

## 8. FULL：GBC + Refined LS + Archive PR

### 8.1 方法邏輯

FULL 是把三個功能一起打開：

```text
FULL = GBC + refined local search + archive path relinking
```

其中：

- GBC：guided binary conversion；
- LS：new best 附近做受 budget / cooldown 限制的 add/drop local search；
- PR：保留 elite archive，對 gbest 與 archive donor 做 path relinking。

### 8.2 與 baseline 差異

baseline 主要依靠主迴圈 + repair + restart。FULL 額外加入 intensification 與 elite combination。

### 8.3 表現

Reduced pilot 中 FULL 和 GBC 幾乎打平，沒有明顯超過單獨 GBC。PR 的單獨改善也很小。

### 8.4 目前結論

```text
不優先保留。
LS / PR 的邊際收益不明顯。
```

---

## 9. ORACLE_CP

### 9.1 方法邏輯

ORACLE_CP 是診斷用方法，不是正式可用算法。

流程：

```text
1. 用已知最佳解取得 x*_j。
2. 把 x*_j = 1 的 item 全部排前面。
3. 把 x*_j = 0 的 item 全部排後面。
4. 同一群內保留原本 LP/RC order。
5. 用這個 cp_list 跑 solver。
```

### 9.2 與 baseline 差異

baseline 是從 LP/RC 估 item preference；ORACLE_CP 是直接從最佳解反推 item preference。

### 9.3 表現

3 個 guard 題、20 seeds、500 iterations：

| problem_id | BASE PDev | ORACLE_CP PDev | ORACLE hit |
|---|---:|---:|---:|
| OR5x100-0.25_2 | 0.1397% | 0.0000% | 20/20 |
| OR5x100-0.25_4 | 0.1313% | 0.0000% | 20/20 |
| OR10x100-0.25_4 | 0.2174% | 0.0000% | 20/20 |

### 9.4 目前結論

```text
證明 item evaluation 是關鍵瓶頸。
只作 diagnostic，不可正式使用。
```

---

## 10. CORE_SCORE_CP

### 10.1 方法邏輯

CORE_SCORE_CP 是目前最穩的新 CP 方法。它把 LP relaxation 的多個訊號合成一個連續分數：

```text
core_score[j]
  = 0.40 × x_lp_score[j]
  + 0.25 × reduced_cost_score[j]
  + 0.20 × efficiency_score[j]
  + 0.15 × bucket_score[j]
```

其中：

| 分數 | 意義 |
|---|---|
| x_lp_score | LP relaxation 中 item 被選的程度 |
| reduced_cost_score | item 的邊際價值 |
| efficiency_score | profit / dual-weighted resource cost |
| bucket_score | strong/core/weak 分層 |

排序：

```text
core_score 高者排前面。
同分時 efficiency 高者排前面。
再同分時 item_id 小者排前面。
```

### 10.2 與 baseline 差異

baseline 是：

```text
先看 bucket，再看 efficiency。
```

CORE_SCORE_CP 是：

```text
把 x_lp、reduced cost、efficiency、bucket 合成一個連續 score。
```

因此它比 baseline 更細緻，不會只因為 bucket 相同就完全依賴 efficiency。

### 10.3 表現

第一輪 3 題 × 5 seeds × 500 iterations：

| Method | Avg PDev |
|---|---:|
| BASE_LP_RC | 0.20240% |
| CORE_SCORE_CP | 0.15224% |

第二輪 5 題 × 10 seeds：

| Method | Avg PDev | Hit Rate |
|---|---:|---:|
| CORE_SCORE_CP | 0.092272% | 21/50 |

第三輪 5 題 × 5 seeds：

| Method | Avg PDev |
|---|---:|
| CORE_SCORE_CP | 0.096690% |
| FREQ_GATED_V2 | 0.104082% |
| FREQ_GATED_V2_GBC | 0.123710% |

### 10.4 目前結論

```text
目前最可靠的新 CP 方法。
建議進入下一輪 formal：BASE_PARAM_20 vs CORE_SCORE_CP vs CORE_SCORE_CP + GBC。
```

---

## 11. FREQ_CP

### 11.1 方法邏輯

FREQ_CP 的想法是：不要只解一次 LP，而是多次 perturb profit，再用 probing solutions 估計 item 在高品質解中出現的頻率。

流程：

```text
1. 重複 R 次：
   a. 對 profit 加小擾動。
   b. 解 perturbed LP。
   c. 用 perturbed score 建 feasible solution。
   d. repair + swap。
   e. 記錄 solution 和 objective。

2. 對每個 item 計算 inclusion frequency：
   freq[j] = item j 在高品質 probing solutions 中被選到的比例。

3. 依 freq[j] 排序產生 cp_list。
```

### 11.2 與 baseline 差異

baseline 是單次 LP/RC 的靜態排序。FREQ_CP 嘗試估計：

```text
item j 出現在近似最佳解族中的機率。
```

### 11.3 表現

第一輪 3 題 × 5 seeds：

| Method | Avg PDev | 判斷 |
|---|---:|---|
| FREQ_CP | 0.17343% | 小題好，大一點題目退步 |

逐題上，FREQ_CP 在 OR5x100 題目表現很好，但在 OR10x100-0.25_4 上退步明顯。

### 11.4 目前結論

```text
方向有潛力，但原始版本不穩。
不直接保留。
```

---

## 12. FREQ_CP_GBC

### 12.1 方法邏輯

FREQ_CP_GBC 是在 FREQ_CP 的 CP order 上再啟用 GBC。

也就是：

```text
cp_list 用 freq score 排序；
binary conversion 也使用 guided probability。
```

### 12.2 與 baseline 差異

baseline 只用 LP/RC order；FREQ_CP_GBC 同時改：

- `cp_list`；
- 二值化機率。

### 12.3 表現

第一輪 3 題 × 5 seeds：

| Method | Avg PDev | 判斷 |
|---|---:|---|
| FREQ_CP_GBC | 0.13843% | 平均最好，但不穩 |

它是該輪平均最好的方法，但在 OR10x100-0.25_4 上退步，沒有穩定追平 QPSO*。

### 12.4 目前結論

```text
不直接保留。
說明 frequency + guidance 有潛力，但需要 gate 與 conservative blending。
```

---

## 13. ELITE_FREQ_CP

### 13.1 方法邏輯

ELITE_FREQ_CP 用 elite candidate solutions 的 item 出現頻率來更新 CP。

流程：

```text
1. 產生多個 candidate / probing solutions。
2. 選出 objective 較好的 elite solutions。
3. 對每個 item 計算 elite inclusion frequency。
4. 依 frequency 排序或與 core score 混合。
```

### 13.2 與 baseline 差異

baseline 從 LP/RC 推 item value；ELITE_FREQ_CP 從搜尋得到的高品質解反推 item value。

### 13.3 表現

第一輪 3 題 × 5 seeds：

| Method | Avg PDev | 判斷 |
|---|---:|---|
| ELITE_FREQ_CP | 0.14195% | 有單題亮點，但不穩 |

例如它曾在 OR5x100-0.25_4 達到 0.000% PDev，但在其他題不穩。

### 13.4 目前結論

```text
有潛力，但原始 elite gate 太弱。
不直接保留。
```

---

## 14. SBL_LITE_CP

### 14.1 方法邏輯

SBL_LITE_CP 是 strong-branching / bound-loss 的輕量版。

完整 strong-branching 的概念是：

```text
對每個 item j：
    測試固定 x_j = 0 後 LP upper bound 下降多少；
    測試固定 x_j = 1 後 LP upper bound 下降多少。

如果固定 x_j = 0 讓 upper bound 大幅下降，代表 item j 很可能該選。
```

輕量版沒有對所有 item 做完整 2n 次 LP，而是只對候選核心 item 做部分測試或近似。

### 14.2 與 baseline 差異

baseline 使用一次 LP 的 local reduced-cost 訊號；SBL 類方法測試 item 固定後整體 LP bound 的變化，更接近 exact solver 的 branching score。

### 14.3 表現

第一輪：

| Method | Avg PDev | 判斷 |
|---|---:|---|
| SBL_LITE_CP | 0.19382% | 成本高，效果普通 |

### 14.4 目前結論

```text
不優先。
除非未來做完整 core-only strong branching，否則暫停。
```

---

## 15. ELITE_FREQ_GATED

### 15.1 方法邏輯

ELITE_FREQ_GATED 是 ELITE_FREQ_CP 的 gated 版本，試圖避免低品質 elite 污染 CP order。

基本流程：

```text
1. 產生 candidate solutions。
2. 只保留達到品質門檻的 elite。
3. 計算 elite inclusion frequency。
4. 若 elite 不足或品質不夠，fallback 到 CORE_SCORE_CP。
```

### 15.2 與 baseline 差異

baseline 不使用搜尋過程中的解分布。ELITE_FREQ_GATED 嘗試用 elite 解反向學 item preference。

### 15.3 表現

第二輪 5 題 × 10 seeds：

| Method | Avg PDev | Hit Rate |
|---|---:|---:|
| ELITE_FREQ_GATED | 0.159652% | 4/50 |
| CORE_SCORE_CP | 0.092272% | 21/50 |
| FREQ_GATED | 0.078376% | 26/50 |

ELITE_FREQ_GATED 是該輪最差。

### 15.4 目前結論

```text
不保留。
目前 gate 仍不足以防止 elite frequency 污染排序。
```

---

## 16. FREQ_GATED

### 16.1 方法邏輯

FREQ_GATED 是 FREQ_CP 的 gated 版本。

它加入 gate，例如：

```text
1. probing best 必須比 core greedy 好；
2. elite probing solutions 數量不能太少；
3. frequency score 不能太平；
4. top-k item 和 core_score 不能偏離太多。
```

如果 gate 不通過，fallback 到 CORE_SCORE_CP。

### 16.2 與 baseline 差異

baseline 只靠一次 LP/RC。FREQ_GATED 嘗試用多次 probing 建立 item inclusion probability，但用 gate 控制風險。

### 16.3 表現

第二輪 5 題 × 10 seeds：

| Method | Avg PDev | Hit Rate | 判斷 |
|---|---:|---:|---|
| FREQ_GATED | 0.078376% | 26/50 | 平均最好，但仍不穩 |
| CORE_SCORE_CP | 0.092272% | 21/50 | 穩定 fallback |

FREQ_GATED 在平均上最好，也在部分 OR5x100 題目追平 QPSO*。但在 OR10x100-0.25_4 上退步。

### 16.4 目前結論

```text
有潛力，但不能直接正式保留。
需要 dim-aware 修正。
```

---

## 17. FREQ_GATED_V2

### 17.1 方法邏輯

FREQ_GATED_V2 是 FREQ_GATED 的 dim-aware 修正版。

核心公式：

```text
score[j] = rho × core_score[j] + (1 - rho) × freq_score[j]
```

其中 rho 依 constraint dimension 調整：

```text
dim = 5  → rho = 0.50, samples = 16
dim = 10 → rho = 0.70, samples = 32
dim = 30 → rho = 0.75, samples = 48
```

意思是：

```text
dim 越大，越不完全相信 frequency probing，越偏向保守 core_score。
```

### 17.2 與 FREQ_GATED 差異

FREQ_GATED 對不同 dim 使用較一致的 frequency 邏輯；V2 會依 dim 調整：

- probing 次數；
- core_score / freq_score blending ratio。

### 17.3 表現

第三輪 5 題 × 5 seeds：

| Method | Avg PDev |
|---|---:|
| CORE_SCORE_CP | 0.096690% |
| FREQ_GATED_V2 | 0.104082% |
| FREQ_GATED_V2_GBC | 0.123710% |

V2 沒有修好不穩定問題。它在 OR5x100-0.25_4 表現很好，但在 OR5x100-0.25_2、OR5x100-0.25_3、OR10x100-0.25_4 不如 CORE_SCORE_CP。

### 17.4 目前結論

```text
暫不保留。
方向可研究，但目前不如 CORE_SCORE_CP 穩。
```

---

## 18. FREQ_GATED_V2_GBC

### 18.1 方法邏輯

FREQ_GATED_V2_GBC 是：

```text
FREQ_GATED_V2 + guided binary conversion
```

實作上：

```text
1. 用 FREQ_GATED_V2 的 blended_score 產生 cp_list。
2. 把 blended_score 當作 x_lp-like guide。
3. 在 binary conversion 時加入 score bias。
```

### 18.2 與 FREQ_GATED_V2 差異

FREQ_GATED_V2 只改 `cp_list`。V2_GBC 同時改：

- `cp_list`；
- CTF 二值化機率。

### 18.3 表現

第三輪結果：

| Method | Avg PDev | 判斷 |
|---|---:|---|
| FREQ_GATED_V2_GBC | 0.123710% | 三者最差 |

這表示 frequency-blended score 同時用在 CP order 和 binary conversion 會過度偏置，反而破壞穩定性。

### 18.4 目前結論

```text
不保留。
暫停這個方向。
```

---

## 19. 目前總結表

| 類別 | 方法 | 是否實測 | 表現判斷 | 目前建議 |
|---|---|---:|---|---|
| Baseline | LP/RC order | 是 | 穩定 | 保留 |
| Baseline variant | group shuffle | 是 | 不穩 | 不保留 |
| Repair scoring | dynamic weight drop | 是 | 不穩或退步 | 不保留 |
| Score scaffold | CND / DUAL / RC / HYB / LAG × rank/weight | 是 | HYB-rank 有潛力但未過 gate | 不帶回 |
| Binary guidance | GBC | 是 | 有改善，但 formal 未完成 | 候選 |
| Combined | FULL | 是 | 與 GBC 打平，LS/PR 額外收益小 | 暫不保留 |
| Diagnostic | ORACLE_CP | 是 | 500 iter 全部達 BKS | 只作診斷 |
| Static hybrid | CORE_SCORE_CP | 是 | 最穩的新 CP 方法 | 下一輪正式候選 |
| Frequency probing | FREQ_CP | 是 | 小題好，大題不穩 | 不直接保留 |
| Frequency + GBC | FREQ_CP_GBC | 是 | 平均好但不穩 | 不直接保留 |
| Elite frequency | ELITE_FREQ_CP | 是 | 有單題亮點但不穩 | 不保留 |
| Strong branching lite | SBL_LITE_CP | 是 | 成本高、效果普通 | 不優先 |
| Gated elite frequency | ELITE_FREQ_GATED | 是 | 表現差 | 不保留 |
| Gated frequency | FREQ_GATED | 是 | 平均最好但 dim=10 不穩 | 研究候選 |
| Dim-aware gated frequency | FREQ_GATED_V2 | 是 | 未改善穩定性 | 暫不保留 |
| Dim-aware gated frequency + GBC | FREQ_GATED_V2_GBC | 是 | 更差 | 不保留 |

---

## 20. 目前最重要的結論

### 20.1 物品評估是主要瓶頸

ORACLE_CP 實驗證明，如果 `cp_list` 足夠接近最佳解，現有 solver 可以在 500 iterations 內穩定達到 BKS。因此，目前主問題是 CP 評估不夠精準。

### 20.2 頻率型方法有訊號，但不穩

FREQ_CP / FREQ_GATED 在部分 OR5x100 題目非常強，甚至追平 QPSO*，但在 OR10x100 題目退步。這代表 probing frequency 確實含有有效訊號，但 gate / blend 還不足以保證跨題穩定。

### 20.3 CORE_SCORE_CP 是目前最可靠的正式候選

CORE_SCORE_CP 沒有 FREQ 類方法激進，但跨題穩定性最好。它是目前最適合進入下一輪 formal 的方法。

目前建議下一輪正式測：

```text
BASE_PARAM_20
CORE_SCORE_CP
CORE_SCORE_CP + 原始 GBC
```

若這三組通過 5 題 guard，再擴到：

```text
15 題 × 20 seeds × 500 iterations
```

最後才進入完整：

```text
完整 CB × 20 seeds × 5000 iterations
```

---

## 21. 建議下一步實驗

### Phase 1：短迭代正式 guard

```text
instances: 5 guard 題
seeds: 1000..1019
max_iterations: 500
methods:
  - BASE_PARAM_20
  - CORE_SCORE_CP
  - CORE_SCORE_CP + GBC
```

Gate：

```text
1. 平均 PDev 必須低於 BASE。
2. 任一 guard 題退步不能超過 0.02%。
3. Hit rate 不得低於 BASE。
4. Runtime 增加需可接受。
```

### Phase 2：中規模擴張

```text
instances: OR5x100, OR5x250, OR10x100 共 15 題
seeds: 1000..1019
max_iterations: 500
```

### Phase 3：長迭代驗證

```text
instances: 完整 CB 或正式論文 subset
seeds: 1000..1019
max_iterations: 5000
```

---

## 22. 目前推薦寫入實驗設定的候選 YAML

### CORE_SCORE_CP

```yaml
item_eval_method: core_score_cp
core_w_x_lp: 0.40
core_w_rc: 0.25
core_w_eff: 0.20
core_w_bucket: 0.15

a: 2.5
z: 0.01
ctf: abs_pow_16
repair_passes: 2
repair_swap_limit: 4
mixed_init_enabled: true
restart_enabled: true
restart_window: 40
restart_ratio: 0.25
```

### CORE_SCORE_CP + GBC

```yaml
item_eval_method: core_score_cp
core_w_x_lp: 0.40
core_w_rc: 0.25
core_w_eff: 0.20
core_w_bucket: 0.15

guided_binary_enabled: true
guided_lambda_lp: 0.20
guided_lambda_bucket: 0.05
guided_lambda_slack: 0.05

a: 2.5
z: 0.01
ctf: abs_pow_16
repair_passes: 2
repair_swap_limit: 4
mixed_init_enabled: true
restart_enabled: true
restart_window: 40
restart_ratio: 0.25
```

---

## 23. 最終結論

目前為止，所有物品評估方法測試後，最穩定的結論是：

```text
CORE_SCORE_CP 是目前最值得推進到 formal 的新 item evaluation 方法。
```

FREQ 類方法雖然可能在部分題目更強，但目前不穩，不建議直接寫進 `param_20`。GBC 有改善潛力，但應該先和 CORE_SCORE_CP 搭配做正式 guard，而不是和 FREQ score 疊加。

因此下一步應該聚焦：

```text
BASE_PARAM_20 vs CORE_SCORE_CP vs CORE_SCORE_CP + GBC
```

而不是繼續擴展 PR、FULL、FREQ_GATED_V2_GBC 或其他更複雜機制。
