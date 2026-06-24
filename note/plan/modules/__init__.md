# `__init__.py`

## 模組責任

根 `__init__.py` 是 `mkp` 套件的對外聚合入口。它負責重新匯出主流程常用型別與 helper，並透過 `__getattr__` 延遲暴露 `main`。

## 公開入口/主要類型

- package-level exports：`Engine`、`SimulationBundle`、`ExperimentSpec`、`RunTask`、`SolveResult`
- solver exports：`BSMACore`、`BSMASolver`、`BSCACore`、`BSCASolver`、`BRLSMASCATestCore`、`BRLSMASCATestSolver`
- runtime exports：`Machine*`、`Simulator*`、`ProblemRepository`、`SolverConfigLoader`
- converter / CLI exports：`getConverter`、`listConverters`、`register`、`executeSimulator`
- lazy export：`__getattr__(...)` 提供 `main`

## 主要資料結構與資料契約

- `__all__` 是套件層承諾的公開 API。
- `main` 不在載入時直接 import，而是透過 `__getattr__` 延遲導到 `cli.run.main`。
- `ProblemModel`、`SimulatorResult`、`MachineResult` 等名稱在這一層只是 re-export，不重新定義契約。

## 資料流與控制流

1. 外部程式 `import mkp`。
2. 模組先做 package context 修正，兼容直接執行此檔的特殊情況。
3. 重新匯入並暴露各子套件常用 symbol。
4. 若外部請求 `mkp.main`，`__getattr__` 才動態 import `cli.run.main`。

## 失敗路徑與例外條件

- 任一被 re-export 的下游模組若 import 失敗，根套件 import 也會失敗。
- `__getattr__` 只接受 `main`，其他名稱一律丟 `AttributeError`。

## 副作用與資源生命週期

- import `mkp` 時會一併 import 多個子套件，因此有明顯的 import-time 耦合。
- 本模組本身不做 I/O，也不建立長生命週期資源。

## 與其他模組的關係

- 上游：外部腳本、pytest、研究工具可能直接以 `mkp.*` 使用這裡的匯出面。
- 下游：`cli`、`converter`、`engine`、`machine`、`problem`、`simulator`、`solver`、`tools` 幾乎都被聚合到此。

## 對應函式索引與閱讀順序

1. package context bootstrap
2. `__getattr__`
3. `__all__`
