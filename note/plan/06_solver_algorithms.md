# Solver Algorithms

本文件是 solver family 的架構入口；`.py` 模組內部責任請直接搭配 `note/plan/modules/solver/*.md`。

## Solver Contract

所有目前主流程 solver 都應符合 `solver.registry.Solver` protocol：

```python
solve(problem: Problem, config: dict[str, Any], rng: np.random.Generator) -> SolveResult
```

統一契約重點：

- solver 只能透過 `problem`、`config`、`rng` 取得資料。
- 不應自行讀 problem YAML 或直接寫 output 檔。
- 標準輸出必須是 `SolveResult`；validation、統計、輸出由其他模組接手。

對應文件：
- [`solver/registry.py`](modules/solver/registry.md)
- [`engine/models.py`](modules/engine/models.md)
- [`problem/validation.py`](modules/problem/validation.md)

## Family Map

| Family | Baseline | Numba | RC / Advanced | 角色 |
|---|---|---|---|---|
| BSMA | [`BSMA.py`](modules/solver/BSMA.md) | [`BSMA_numba.py`](modules/solver/BSMA_numba.md) | [`BSMA_rc_numba.py`](modules/solver/BSMA_rc_numba.md) | Binary Slime Mould Algorithm 主線。 |
| BSCA | [`BSCA.py`](modules/solver/BSCA.md) | [`BSCA_numba.py`](modules/solver/BSCA_numba.md) | [`BSCA_rc_numba.py`](modules/solver/BSCA_rc_numba.md) | Binary Sine Cosine Algorithm 主線。 |
| Hybrid SMA/SCA | [`BSCASMA.py`](modules/solver/BSCASMA.md) | [`BSCASMA_test_numba.py`](modules/solver/BSCASMA_test_numba.md) | [`BSCASMA_rl_numba.py`](modules/solver/BSCASMA_rl_numba.md)、[`BSCASMA_rl_rc_numba.py`](modules/solver/BSCASMA_rl_rc_numba.md) | 混合策略、RL、RC、guided binary、local search、archive/path relinking。 |

## Registered Solvers

目前 `engine/builders.py::solverBuilders` 註冊：

- `stub_solver`
- `bsma` / `bsma_numba` / `bsma_rc_numba`
- `bsca` / `bsca_numba` / `bsca_rc_numba`
- `brlsmasca` / `brlsmasca_test_numba`
- `brlsmasca_rl_numba` / `brlsmasca_rl_rc_numba`

這些 builder 在主行程與 process worker 都會被重新註冊，因此 solver module 必須可被重複 import 且不依賴隱含的外部初始化。

對應文件：
- [`engine/builders.py`](modules/engine/builders.md)
- [`solver/registry.py`](modules/solver/registry.md)

## Algorithm Support Chain

solver family 本身不是孤立存在，周邊還有幾個直接影響演算法語意的支援模組：

- [`tools/continuous_to_binary.py`](modules/tools/continuous_to_binary.md)
  - 定義 `ctf` 名稱、順序與 Python 側數學映射
  - adapter 會先把 `params["ctf"]` 轉成 `(kind, ctf_id)`
- [`tools/ctf_numba.py`](modules/tools/ctf_numba.md)
  - 在 Numba hot-loop 中用 `ctf_id` 做整數分派
  - 必須與 Python 側公式與順序完全一致
- [`tools/mkp_score_scaffold.py`](modules/tools/mkp_score_scaffold.md)
  - 抽離 score + repair 層，評估不同 item score family 的表現傾向
- [`tools/mkp_item_eval_experiment.py`](modules/tools/mkp_item_eval_experiment.md)
  - 以完整 solver 執行比較 item-evaluation / score 變體
- [`tools/mkp_rc_feature_ablation.py`](modules/tools/mkp_rc_feature_ablation.md)
  - 以完整 solver 執行比較 guided binary、local search、archive PR 等功能開關

這些工具不是 runtime 必經模組，但它們決定演算法調參、score family 演進與 helper 對齊方式，因此屬於演算法支援鏈，而不是單純的雜項腳本。

## Layering Pattern

大多數 solver 模組都遵循相同分層：

1. Python helper / Numba helper：
   - 排序
   - repair
   - row update
   - item evaluation
   - RL state update
2. `*Core`：
   - 保存 problem tensors 與演算法狀態
   - 建立 `cp_list` 或 item-eval payload
   - 生成初始族群
   - 執行 `run()`
3. `*Solver` adapter：
   - 驗證 solver YAML params
   - 解析 `ctf_kind` / `ctf_id`
   - 建 core
   - 計時
   - 封裝 `SolveResult`

例外：

- `solver/registry.py` 是註冊與契約層，不屬於某個演算法家族。
- `solver/__init__.py` 幾乎只作 package 標記。

## Common Data Path

1. `Machine.run_task(...)` 取得 `problem`、`config`、`rng`
2. solver adapter 解析 `params` 與 `stop_condition`
3. `Core` 先建立 `cp_list` 或 item evaluation payload
4. `Core.run()` 或單一 Numba main loop 執行主搜索
5. solver adapter 回傳 `SolveResult`
6. `problem.validate(...)` 驗證 objective 與可行性

關鍵共通欄位：

- `run_seed`
- `evaluation_count`
- `stop_reason`
- `runtime`
- `linprog_runtime`
- `metadata`

## Hot-loop Helper Categories

### 排序與決定性

- `_argsort_pop_fit_desc_deterministic(...)`
- `_sort_*_deterministic_inplace(...)`

用途：
- 保持同 fitness 時的 tie-break 一致。
- 降低 Python / Numba / 平行 worker 間的排序漂移。

### Repair Family

- `_repair_row_inplace(...)`
- `_repair_bsca_row_inplace(...)`
- `_repair_bscasma_row_inplace(...)`
- `_repair_bscasma_row_v2_inplace(...)`
- `_repair_bscasma_row_dynamic_drop_inplace(...)`
- `_repair_bscasma_swap_once_inplace(...)`

用途：
- 將連續或二值候選解修正回容量限制內。
- RC / advanced variants 會加入 dynamic drop score 與 swap。

### Item Evaluation / RC Family

集中在 [`BSCASMA_rl_rc_numba.py`](modules/solver/BSCASMA_rl_rc_numba.md)：

- `_build_lp_rc_item_eval_payload(...)`
- `_build_core_score_cp_payload(...)`
- `_build_frequency_cp_payload(...)`
- `_build_freq_gated_v2_payload(...)`
- `_build_sbl_lite_cp_payload(...)`
- `_score_values_for_method(...)`

用途：
- 把 LP dual / reduced cost / frequency probe / named score 轉成 item ranking 或 guidance score。
- 對應研究工具會再用 [`tools/mkp_score_scaffold.py`](modules/tools/mkp_score_scaffold.md) 與 [`tools/mkp_item_eval_experiment.py`](modules/tools/mkp_item_eval_experiment.md) 做外部比較。

### RL / Density Family

- `_state_bin(...)`
- `_init_density_state(...)`
- `_update_density_state_for_row(...)`
- `_state_for_row(...)`
- `_select_q_action_non_global(...)`
- `_update_q_value(...)`

用途：
- 把族群分布轉成離散 state。
- 更新 Q-table，控制非 global 動作選擇。

### Intensification Family

- guided binary helper
- local search helper
- archive/path relinking helper
- restart helper

主要集中在 `brlsmasca_rl_rc_numba`，這也是目前最需要小心維護的強化版本。

功能開關與 guard 問題比較主要由 [`tools/mkp_rc_feature_ablation.py`](modules/tools/mkp_rc_feature_ablation.md) 支撐。

## Family Notes

### BSMA

- 以 SMA 權重更新與 `z` 控制 global/local 分支。
- Numba 版主要優化排序、repair 與整段 main loop。
- RC 版加入 LP reduced-cost 排序、repair 2.0、mixed init、restart。

### BSCA

- 以 `sin/cos` 更新位移與 `a` 退火。
- Numba 版同樣保留基線語意，但用單一 `@njit` 主迴圈執行。
- RC 版沿用 BSMA RC 的 item evaluation / repair / restart 思路。

### Hybrid SMA/SCA

- `BSCASMA.py` / `BSCASMA_test_numba.py` 是 test-policy 路線。
- `BSCASMA_rl_numba.py` 把 policy 改成 Q-learning。
- `BSCASMA_rl_rc_numba.py` 再加上 RC score、guided binary、local search、archive/path relinking、restart。

## Risk Notes

- `BSCASMA_rl_rc_numba.py` 是目前最脆弱、變化面最大的檔案；修改時應配套檢查 deterministic 行為、Q-table 路徑、repair 統計與 metadata。
- `BSMA.py`、`BSCA.py`、`BSCASMA.py` 雖然較慢，但它們是很多 Numba 版的語意基準，不應任意重構。
- 類別層級 cache 會影響後續 runs 的 `linprog_runtime` 與 metadata，分析效能時必須區分 cold / warm cache。

## Extension Rule

新增 solver 時至少要同步更新：

1. solver class / module
2. `engine/builders.py`
3. `configs/solvers/<solver>.yaml`
4. 對應 tests / valid 腳本
5. 本文件
6. `04_module_guide.md`
7. `note/plan/modules/solver/<module>.md`
