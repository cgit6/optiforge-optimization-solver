# `cli/exp/__init__.py`

## 模組責任

`cli/exp/__init__.py` 是 `cli.exp` package 的對外匯出面。它把 `main` 與一部分 bundled evaluator 名稱重新匯出。

## 公開入口/主要類型

- `main`
- `mkp_base_evaluator`
- `mkp_bsca_base_margin_2_evaluator`
- `mkp_base2_evaluator`
- `mkp_base2_margin_005_evaluator`
- `mkp_calibration_evaluator`
- `mkp_target_combo_*`
- `mkp_transfer_*`
- `mkp_random_collect_every_n_5_20_evaluator`

## 主要資料結構與資料契約

- `__all__` 明確宣告 package 對外保證的入口。
- 目前只匯出部分 evaluator；`mkp_qpso.py` 中 evaluator 並未在 `__all__` 中列出，這是現況而非文件遺漏。

## 資料流與控制流

1. 上游 import `cli.exp`。
2. package 把 `main` 與指定 evaluator 重新暴露。
3. 真正註冊 evaluator 的動作仍在 `cli/exp/main.py::main()` 內完成。

## 失敗路徑與例外條件

- 若匯出的 evaluator 名稱與實際模組內容不同步，會造成 import 失敗或外部 API 漂移。

## 副作用與資源生命週期

- 無直接執行期副作用。
- 主要作用是維持 package API 的穩定對外面向。

## 與其他模組的關係

- 上游：使用 `cli.exp` 作為套件入口的外部呼叫端。
- 下游：`cli/exp/main.py` 與各 evaluator 模組。

## 對應函式索引與閱讀順序

1. `main`
2. package-level evaluator exports
3. `__all__`
