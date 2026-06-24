# `cli/exp/main.py`

## 模組責任

`cli/exp/main.py` 是 `cli.exp` 的實際執行入口。它負責註冊專案內建的 evaluator，載入預設 `exp_cfg.yaml`，再呼叫 `Experiment.run(...)`。

## 公開入口/主要類型

- `DEFAULT_CONFIG_PATH`
- `DEFAULT_PROBLEM_ROOT`
- `DEFAULT_SOLVER_ROOT`
- `DEFAULT_OUTPUT_ROOT`
- `main()`

## 主要資料結構與資料契約

- 這個入口目前是「內建配置」模式，不從命令列接收動態路徑。
- evaluator 名稱必須與 `exp_cfg.yaml` 中 `evaluation` 欄位一致。
- `main()` 回傳 `ExperimentReport`。

## 資料流與控制流

1. import bundled evaluator 模組。
2. 在 `main()` 中逐一 `register(name, evaluator)`。
3. 用 `build(...)` 載入 `DEFAULT_CONFIG_PATH`，建立 `Experiment`。
4. 呼叫 `experiment.run(...)`，使用預設 problem root、solver root、output root。

## 失敗路徑與例外條件

- evaluator 名稱若重複註冊，會在 `experiment.experiment.register(...)` 失敗。
- `exp_cfg.yaml` 路徑錯誤、problem/solver config 驗證失敗、collect 條件收不滿，都會從下游往上拋。

## 副作用與資源生命週期

- 會改寫 experiment evaluator 註冊表。
- 會觸發完整 collect 流程與 output 寫入；這是 `cli.exp` 的主副作用入口。

## 與其他模組的關係

- 上游：`cli/exp/__main__.py`、`cli/exp/__init__.py`。
- 下游：`experiment.config`、`experiment.experiment`、各 evaluator 模組。

## 核心函式與 helper 說明

### `main()`

- 目的：完成 `cli.exp` 的 evaluator 註冊、實驗建立與執行。
- 控制流：先逐一 `register(...)` 內建 evaluator，再 `build(DEFAULT_CONFIG_PATH, ...)` 建 `Experiment`，最後呼叫 `experiment.run(...)`。
- 副作用：會改寫 evaluator registry，並觸發完整 collect / output 流程。
- 修改風險：這裡的 evaluator 名稱必須和 `exp_cfg.yaml` 完全對齊；任何 rename 若沒同步更新 config，collect 會在 runtime lookup 階段失敗。

## 對應函式索引與閱讀順序

1. `DEFAULT_CONFIG_PATH`
2. `DEFAULT_PROBLEM_ROOT`
3. `DEFAULT_SOLVER_ROOT`
4. `DEFAULT_OUTPUT_ROOT`
5. `main`
