# `cli/run/__init__.py`

## 模組責任

`cli/run/__init__.py` 是 `cli.run` package 的對外匯出面。它把薄 `main` 與 `support.py` 中真正的 parser / spec / execute helper 一起暴露。

## 公開入口/主要類型

- `main`
- `createExperimentSpec`
- `build_parser`
- `parser`
- `validate_execute_args`
- `executeSimulator`

## 主要資料結構與資料契約

- `main` 來自 `cli/run/main.py`。
- 其餘真正的 CLI 組裝與驗證邏輯來自 `cli/run/support.py`。
- `__all__` 是 `mkp.cli.run` 對外的穩定 package API。

## 資料流與控制流

1. 上游 import `mkp.cli.run`。
2. package 同時暴露薄入口 `main` 與 support helpers。
3. 實際執行時，`main` 會再呼叫 `createExperimentSpec(...)`、`buildSimulationBundle(...)`、`executeSimulator(...)`。

## 失敗路徑與例外條件

- 若 `main.py` 或 `support.py` 中符號漂移，這一層 import 會立刻失敗。

## 副作用與資源生命週期

- 無直接執行期副作用；所有 I/O 與 shared memory lifecycle 都在 `support.py` / runtime 模組。

## 與其他模組的關係

- 上游：根套件 `mkp.__getattr__`、CLI 呼叫端、tests。
- 下游：`cli/run/main.py` 與 `cli/run/support.py`。

## 對應函式索引與閱讀順序

1. `main`
2. `createExperimentSpec`
3. `build_parser`
4. `parser`
5. `validate_execute_args`
6. `executeSimulator`
7. `__all__`
