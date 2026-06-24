# Maintenance Playbooks

## 新增 Solver

1. 在 `solver/` 新增 solver class，實作 `solve(problem, config, rng) -> SolveResult`。
2. 在 `engine/builders.py::solverBuilders` 加入 solver id 與 builder。
3. 在 `configs/solvers/<solver_id>.yaml` 新增 config，確認 `solver_id` 和 builder key 一致。
4. 在 capabilities 寫清楚 `problem_types`、`encodings`、`directions`。
5. 在 `params` 放一組或多組參數；param set index 從 0 開始。
6. 新增或更新 tests，至少覆蓋可建立、短迭代可跑、可重現、invalid config。
7. 更新 `note/plan/06_solver_algorithms.md`、`05_api_reference.md` 與 inventory。

## 新增 Problem Type

1. 在 `problem/` 建立 problem dataclass，繼承 `Problem`。
2. 實作 `fitness`、`violates_constraints`、`validate`。
3. 實作 YAML loader、shared-memory pack maker/attacher。
4. 在 `ProblemTypeSpec` 中註冊 loader/model type/shared-memory callbacks。
5. 更新 `problem/builders.py::problemBuilders`。
6. 新增 `configs/problems/<problem_type>/<dataset>/*.yaml`。
7. 確認 solver YAML capabilities 支援新 problem type/encoding/direction。
8. 新增 repository、registry、validation、CLI run 測試。

## 新增 Dataset Parser

1. 在 `cli/convert/register.py` 寫 parser，輸出 `items`、`dim`、`values`、`weights`、`capacities`、`best_known`。
2. 用 `converter.register.register` 註冊 converter key。
3. 用 `cli.convert` 產生 YAML。
4. 用 `ProblemRepository.load` 或測試確認 YAML 可被載入。
5. 更新 `03_data_and_config.md` 與 dataset inventory。

## 新增 Experiment Evaluator

1. 在 `cli/exp/*.py` 新增 evaluator function，接受 `RoundEvalInput`，回傳 `RoundEvalDecision`。
2. 註冊 evaluator 名稱，並確保 `cli/exp/main.py` 匯入該模組。
3. 在 `exp_cfg.yaml` 的 problem `evaluation` 使用該名稱。
4. 測試 PASS/FAIL、baseline 缺值、variant 不存在、projected result 邏輯。
5. 更新 `07_experiment_and_evaluation.md`。

## 修改 Output/Stat

1. 先確認 `ResultEntry`、`SummaryReport` 是否需要新增欄位。
2. 更新 `_entry_to_json_dict`、CSV row、summary JSON/CSV。
3. 保持 `runs.json` 是陣列格式。
4. 新增 stat/show 測試，確認 excluded counts、PDev、metadata 不破壞既有輸出。

## 更新文件 Inventory

1. 重新做 AST 掃描，更新 `05_api_reference.md`。
2. 更新 `inventory/python_modules.md` 與 `inventory/function_coverage_checklist.md`。
3. 若新增 config/data/note/log，也更新對應 inventory。
4. 用 `rg` 檢查新增 class/function 名稱至少出現在 API reference 或 coverage checklist。

## 更新介紹文件

1. 先更新對應的正式介紹文件，例如 `01_system_architecture.md`、`04_module_guide.md`、`07_experiment_and_evaluation.md`。
2. 若更新內容影響系統層、模組層、功能架構層或函式層說明，必須同步重評 `11_dashboard.md`。
3. 更新 `11_dashboard.md` 的 `最後評估日期`、分層分數、證據指標、已知缺口與更新紀錄。
4. 若只是增加條目但仍保留模板句，不得提高 `功能函數/輔助函數層` 分數。
