# `experiment/__init__.py`

## 模組責任

`experiment/__init__.py` 是 experiment domain package 的匯出面，集中暴露 config model、round evaluator 契約、collect runtime 與 verdict 常數。

## 公開入口/主要類型

- config types：`ExperimentConfig`、`SolverSelection`、`DatasetSetting`、`ProblemSetting`、`EvaluationSpec`、`EvaluationBaseline`
- evaluator types：`VariantSummary`、`RoundEvalInput`、`RoundEvalDecision`、`DatasetEvalInput`、`DatasetEvalDecision`
- runtime：`Experiment`、`ExperimentReport`、`ProblemCollectionReport`
- helper：`load_config`、`build`、`executeExperiment`、`register`
- verdict constants：`PASS`、`FAIL`

## 主要資料結構與資料契約

- `PASS` / `FAIL` 是 collect evaluator 家族共享的 verdict 名稱。
- `build(...)` 與 `register(...)` 來自 `experiment/experiment.py`，而非 config 模組。
- package 匯出面把 config 契約與 runtime 放在同一層，方便 CLI 與 tests 使用。

## 資料流與控制流

1. 上游 import `mkp.experiment`。
2. package 重新匯出 config model、evaluator contract 與 collect runtime。
3. 外部通常只透過這一層操作 `load_config(...)`、`build(...)`、`register(...)`。

## 失敗路徑與例外條件

- 若 config / evaluation / experiment 任一子模組匯入失敗，這層 API 就不可用。

## 副作用與資源生命週期

- 無直接 I/O；註冊表修改與 collect 實際執行都在下游模組。

## 與其他模組的關係

- 上游：`cli.exp`、`cli.replay`、tests、研究工具。
- 下游：`config.py`、`evaluation.py`、`experiment.py`。

## 對應函式索引與閱讀順序

1. config-level exports
2. evaluation-level exports
3. runtime exports
4. `PASS` / `FAIL`
5. `__all__`
