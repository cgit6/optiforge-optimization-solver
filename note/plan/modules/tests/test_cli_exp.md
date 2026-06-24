# `tests/test_cli_exp.py`

## 模組責任

`test_cli_exp.py` 是 `cli.exp.main` 的薄 wiring smoke test，確認 bundled evaluator 會被註冊，並且 `build(...).run(...)` 鏈路被正確呼叫。

## 公開入口/主要類型

- pytest 自動發現測試
- 主要測試群：`test_cli_exp_main_registers_bundled_evaluators_builds_and_runs`

## 主要資料結構與資料契約

此檔不驗證 evaluator 邏輯本身，而是驗證 `cli.exp` 啟動層能把 evaluator registry、config build 與 experiment run 串起來。

## 資料流與控制流

測試以 monkeypatch/stub 取代真正的 build/run，再檢查 `main()` 是否完成註冊與呼叫序。

## 失敗路徑與例外條件

若未註冊 evaluator、未使用預設 config 路徑或未觸發 `Experiment.run(...)`，都屬 wiring regression。

## 副作用與資源生命週期

無實際 solver 執行；副作用主要是 evaluator registry 的暫時修改。

## 與其他模組的關係

目標模組是 `cli/exp/main.py`，它補足 `test_exp_config.py` 與 `test_experiment_run.py` 之間的入口層空缺。

## 對應函式索引與閱讀順序

1. `test_cli_exp_main_registers_bundled_evaluators_builds_and_runs`

## 核心函式與 helper 說明

### `test_cli_exp_main_registers_bundled_evaluators_builds_and_runs`

這個測試是 `cli.exp.main` 的 wiring smoke test。它用 monkeypatch 攔住 `register(...)`、`build(...)` 與 `Experiment.run(...)`，確認 CLI 入口會先註冊內建 evaluator，再用預設路徑 build experiment，最後把正確的 root 路徑交給 `run(...)`。這個案例保護的是入口接線順序，不是 evaluator 規則本身。
