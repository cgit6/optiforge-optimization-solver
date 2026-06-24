# `solver/BSCASMA.py`

## 模組責任

`solver/BSCASMA.py` 提供混合 SMA/SCA 的純 Python 測試策略版本。它維持與歷史 `old/BSCASMA.py` 對齊，用固定 policy 分布在四種動作間切換。

## 公開入口/主要類型

- `BRLSMASCATestCore`
- `BRLSMASCATestSolver`

## 主要資料結構與資料契約

- `BRLSMASCATestCore` 同時保存：
  - SMA 狀態：`W`
  - SCA 狀態：`a`、`r1`
  - 個體最佳：`individual_best_sol`、`individual_best_fit`
  - 動作記錄：`best_method`、`exe_time`
- `prob_arr` 長度必須為 4，對應：
  - `sma_global`
  - `sma_local`
  - `sca_sin`
  - `sca_cos`

## 資料流與控制流

1. solver adapter 驗證 `pop_size`、`a`、`z`、`prob_arr`。
2. core 初始化：
   - 建立 `cp_list`
   - 生成初始族群
   - 依 `prob_arr` 為每個個體初始化 `best_method`
3. `run()` 每代先更新 SMA 權重與 SCA 退火參數。
4. 每個個體透過 `policy(i)` 選一個動作：
   - `sma_global`
   - `sma_local`
   - `sca_sin`
   - `sca_cos`
5. 執行後 repair、排序、更新 individual best 與 global best。

## 失敗路徑與例外條件

- `prob_arr` 不是長度 4、含負值、總和不為 1 都會失敗。
- 保留了部分舊版 dead code 與未使用欄位，這些不是文件錯誤，而是 fidelity 設計的一部分。

## 副作用與資源生命週期

- 會重設 numpy 全域 RNG。
- `exe_time` 與 `best_method` 是內建 instrumentation，可反映四種動作被採用的次數與個體偏好。
- 同樣會呼叫 `linprog` 取得 `cp_list`。

## 與其他模組的關係

- 上游：`solver.registry`、`engine.builders`。
- 下游：`BSCASMA_test_numba.py` 是這條邏輯的 Numba 版本，但刻意保持檔案獨立，不與 RL 版共享 hot-loop。
- 共用：排序基準依賴 `BSMA._argsort_pop_fit_desc_deterministic(...)`。

## 核心函式與 helper 說明

### `BRLSMASCATestCore.init_best_method()`

- 目的：依 `prob_arr` 為每個個體初始化預設偏好的動作。
- 角色：它定義了 test-policy 版最初的行為分布，後續 `policy(...)` 會優先沿用這些偏好。

### `BRLSMASCATestCore.policy(i)`

- 目的：決定某個個體這一輪要走 `sma_global`、`sma_local`、`sca_sin` 或 `sca_cos`。
- 控制流：大多數時間沿用 `best_method[i]`，少數情況隨機探索其他動作。
- 角色：這是 test-policy 版和 RL 版最大的分界點。

### `update_sma_weight()` / `sma_global()` / `sma_local()` / `sca_sin()` / `sca_cos()`

- 角色：這一組函式分別對應 SMA 權重更新與四種 row-level 動作。
- 維護意義：它們保留了純 Python 測試策略版的可讀性，也是 Numba / RL 版本對照行為的來源。

### `BRLSMASCATestCore.run()`

- 目的：執行混合 SMA/SCA 的純 Python test-policy 主循環。
- 控制流：每代先更新權重與 `r1`，再逐個體取 `policy`、執行動作、repair、排序，並更新 individual/global best。

### `BRLSMASCATestSolver.solve(...)`

- 目的：驗證 `prob_arr`、`a`、`z`、`ctf_kind` 等參數，再把結果包成 `SolveResult`。
- 注意事項：`prob_arr` 長度與總和契約是這個 adapter 最重要的 fail-fast 邊界。

## 對應函式索引與閱讀順序

1. `BRLSMASCATestCore.__init__`
2. `BRLSMASCATestCore.init_best_method`
3. `BRLSMASCATestCore.pseudo_utility`
4. `BRLSMASCATestCore.initial_pop`
5. `BRLSMASCATestCore.repair`
6. `BRLSMASCATestCore.sort_pop`
7. `BRLSMASCATestCore.policy`
8. `BRLSMASCATestCore.update_sma_weight`
9. `BRLSMASCATestCore.sma_global`
10. `BRLSMASCATestCore.sma_local`
11. `BRLSMASCATestCore.sca_sin`
12. `BRLSMASCATestCore.sca_cos`
13. `BRLSMASCATestCore.run`
14. `BRLSMASCATestSolver.solve`
