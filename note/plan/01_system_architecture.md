# 系統架構

## 架構總覽

本專案是一個研究用最佳化模擬平台，套件名稱在 `pyproject.toml` 中為 `mkp`，目前主力問題是 MKP，也已經預留 TSP、KP、VRP 等問題型別位置。系統核心是把「問題資料」、「求解器」、「隨機種子」、「模擬調度」、「結果驗證」和「統計輸出」拆成明確模組。

主流程可以視為下列分層：

1. CLI 層：`cli.run`、`cli.exp`、`cli.convert`、`cli.replay`。
2. 組裝層：`engine.assembly.Engine.build` 建立 `SimulationBundle`。
3. 資料層：`ProblemRepository` 讀 YAML，`ProblemBank` 將本次題目放入記憶體/SharedMemory。
4. 執行層：`Simulator` 建立一組或多組 `Machine`，`MachinePool` 負責序列或 multiprocessing 執行。
5. 演算法層：`SolverRegistry` 建立 solver，solver 的 `solve(problem, config, rng)` 回傳 `SolveResult`。
6. 驗證層：problem 的 `validate` 方法與 `problem.validation` 重新計算 objective、可行性與 best-known gap。
7. 輸出層：`tools.stat` 將 row 彙整為 summary，`tools.show` 寫出 `runs.csv/json` 與 `summary.csv/json`。

## 核心資料契約

- `ExperimentSpec`：一次模擬或實驗的靜態規格，包含 experiment name、problem type、dataset、problem ids、solver ids、repeat、worker count、base seed。
- `RunTask`：單筆執行任務，包含 problem、solver、repeat index、task seed、param set index。
- `SolveResult`：solver 標準輸出，包含 best solution、objective、feasible、evaluation count、runtime、stop reason、metadata。
- `ValidationReport`：problem 重新驗證後的結果，包含可行性、objective mismatch、best-known reached/gap、problem type/encoding/direction。
- `SimulatorRunRow`：`RunTask + SolveResult + ValidationReport` 的不可分割單筆結果。
- `MachineResult`：單一 `(solver_id, param_set_index)` 的所有 rows。
- `SimulatorResult`：一次批次執行後，依 solver variant 分桶的結果集合。
- `SummaryReport`：從 `ResultEntry` 彙整出的 overall 與 per-problem statistics。

## 重要設計決策

- 求解器與問題透過 `Problem` 抽象介面與 solver capabilities 解耦；`cli.run` 會檢查 problem type、encoding、direction 是否與 solver YAML 相容。
- `SimulationBundle.new_simulator()` 只接受單一 solver；多 solver 情境使用 `new_simulators()` 拆成多個單 solver simulator，但共享同一份 problem bank。
- `ProblemBank` 在 multiprocessing 模式下使用 shared memory pack，worker 透過 initializer 附著資料，避免每個 task 重複解析 YAML。
- RNG 由 `SeedStrategy` 以 `SeedContext` 派生；目前主要策略是 `DerivedPerProblemSeedStrategy`，同一 problem/repeat 在不同 solver variant 間可共享 round seed。
- 結果統計只把 feasible 且 objective valid 的 run 納入 objective 平均、最佳與 PDev；runtime 和 evaluation count 則以全部 run 計算。
- `old/` 中的 solver 與 Gurobi 腳本是歷史參考，主流程不依賴它們。

## 驗證閉環

系統層的驗證不是只有 runtime `problem.validate(...)`。現況有三層閉環：

1. 執行期驗證：
   `solver.solve(...) -> SolveResult -> problem.validate(...) -> ValidationReport -> tools.stat / tools.show`
2. 自動化測試：
   `tests/` 以 pytest 守資料契約、repository、engine、simulator、machine、solver、experiment、seed bank replay 與統計輸出。
3. 研究型驗證：
   `valid/` 以 old/new equivalence、population trace、benchmark、stage1 refactor validation 守演算法重構與研究結果一致性。

這三層的角色不同：

- runtime validation 保證單次 run 的結果可被信任。
- pytest 保證程式契約與整合流程沒有明顯回歸。
- `valid/` 腳本保證 solver refactor、Numba 化與 legacy 遷移不會悄悄改變研究語意。

## 既有筆記差異

`note/模組說明.md` 中提到 Simulator 可支援多算法但不支援多參數，現況已演進為：單一 `Simulator` 僅接受一個 solver id，但會為該 solver 的多個 param set 建立多台 `Machine`；多 solver 則由 `SimulationBundle.new_simulators()` 拆分。文件以現況程式碼為準。
