# Legacy Old

## Scope

`old/` 是歷史程式、舊 solver、舊主程式、Gurobi 對照腳本與 notebook 的集合。它應完整建檔，但不視為目前正式執行主流程。正式流程以 `cli/`、`engine/`、`simulator/`、`machine/`、`solver/`、`experiment/` 為準。

## Historical Solver Files

- `old/BSMA.py`、`old/BSCA.py`、`old/BSCASMA.py`：舊版演算法核心，可用於理解現行 solver 的來源或做 equivalence trace。
- `old/transform.py`：舊資料轉換邏輯參考；此檔目前頂層縮排不合法，AST 文件只能記錄 parse error，不能可靠展開函式級 API。
- `old/main1*.py`：針對不同 benchmark 的舊實驗入口。

## Gurobi Scripts

`old/GUROBI/` 保存 exact/relaxation/限制版本與各 dataset main script。這些檔案對未來新增 Gurobi adapter 有參考價值，但目前並未接入 solver registry 的正式主流程。

## Notebooks

Notebook 用於早期分析、繪圖、統計檢定或演算法探索。文件只記錄用途、cell 數與 import 摘要，不逐 cell 改寫。完整清單見 `inventory/legacy_inventory.md`。

## Maintenance Rule

若要把 `old/` 的功能升級為正式功能，需要重新接到目前契約：problem YAML、solver YAML、`solve(problem, config, rng)`、`SolveResult`、validation、stat/show、pytest。
