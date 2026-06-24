# 文件品質 Dashboard

本文件是 `note/plan/` 的常駐品質看板。之後任何正式介紹文件更新，都必須同步重評這份 dashboard，否則視為治理失敗。

## 文件撰寫規則

- 系統層文件必須描述主流程、資料流、狀態流、失敗路徑、輸出產物、責任邊界。
- 模組層文件必須至少到 `.py` 檔粒度，不接受只寫目錄摘要。
- 功能架構層必須描述跨模組協作，例如 `CLI -> Engine -> Bundle -> Simulator -> Machine -> Solver -> Validation -> Stat/Show`。
- 函式文件至少要寫：`目的`、`輸入`、`輸出`、`副作用`、`主要呼叫者/被呼叫者`、`修改風險`。
- 輔助函式若屬於演算法 helper、Numba hot-loop helper、repair/sort/score helper，必須再補「在演算法中的角色」。
- 模板句只能存在於 inventory，不可作為正式介紹文件的最終內容。
- 任何 `note/plan` 正式介紹文件更新後，必須同步更新：`最後評估日期`、`分層分數`、`已知缺口`、`更新紀錄`。

## 總覽摘要

- 最後評估日期：`2026-06-15`
- 目前總分：`81 / 100`
- 目前狀態：`Yellow`
- 計分模型：`系統層 15% + 模組層 20% + 功能架構層 20% + 功能函數/輔助函數層 35% + 治理/新鮮度層 10%`
- 狀態門檻：`Green = 90-100`、`Yellow = 75-89`、`Red = 0-74`
- 本次評估判斷：
  這一輪把 `tests/` / `valid/` 剩餘長尾也補進函式級說明。新增最後 `14` 份模組文件中的手寫「核心函式與 helper 說明」章節，並在 `05_api_reference.md` 的 `13` 個剩餘測試模組段落加入人工工程補充區。函式級手寫小節總數由 `263` 增至 `308`，`tests/valid` 也從 `22/36` 提升到 `36/36` 全覆蓋；正式介紹現在已可從 runtime、solver、evaluation 一路追到所有 pytest 與研究驗證腳本。但全量 API 仍大多停留在模板層，函式層的主缺口已從「tests/valid 未覆蓋」轉成「API 索引長尾與研究工具 helper 深度不足」。
- 主要證據指標：
  靜態掃描結果維持 `136` 個 source Python 檔，其中非 `old/` `113` 個、模組級文件 `113` 份，缺漏 `0`。目前已有 `69` 份核心模組文件含手寫函式級章節，合計 `308` 個手寫函式/helper 小節；`05_api_reference.md` 另有 `45` 個核心模組的人工工程補充區塊。在 `tests/` / `valid/` 這一層，現在已是 `36 / 36` 份文件全數進入手寫函式級說明。全量 API 基線仍是 `1321` 條條目，其中既有的模板壓力指標仍高：`630` 條泛化用途句、`1191` 條模板化輸入句、`894` 條模板化副作用句、`382` 條無明確呼叫者句。這表示函式層已從 runtime 主鏈延伸到演算法、評估與驗證鏈，覆蓋面明顯增加，但距離全量工程化仍有明顯差距。

## 分層評分表

| 層級 | 權重 | 分數 | 狀態 | 證據 | 缺口 | 下一步 |
|---|---:|---:|---|---|---|---|
| 系統層 | 15% | 91 | Green | `01_system_architecture.md`、`02_execution_flows.md`、`03_data_and_config.md` 現在已把 runtime validation/test flow、`cli.convert -> YAML -> repository -> bank` 契約鏈、problem builder 啟用規則與 output 形成責任寫進正式文件。 | shared memory 失敗回收矩陣、converter partial-failure 行為、非 canonical TSP sample path 的運營定位仍未完全系統化。 | 把錯誤/回收分支再細寫成 failure matrix，並明確區分 active catalog 與 reference samples。 |
| 模組層 | 20% | 98 | Green | 靜態掃描顯示非 `old/` source module `113/113` 已全部有模組級文件，且每份都符合固定 `8` 章節模板；Wave 5 新補齊 `cli.convert`、`problem` 次題型、`tools` 支援鏈、package wiring 與 `pytest_plugin.py`。 | `old/` 雖然明確排除在本波之外，但仍未有對等精度的歷史模組文件；此外，薄入口模組天生只會提供 wiring 級精度。 | 維持 active tree 全覆蓋，下一階段不再擴模組數量，改轉向函式級重寫。 |
| 功能架構層 | 20% | 95 | Green | `04_module_guide.md` 已把 `cli.convert`、problem 次題型、`tools` 分析支援鏈、tests/valid、package wiring 全部納入閱讀路線；`06_solver_algorithms.md` 與 `08_validation_and_tests.md` 現在也把 validation/test flow 與研究驗證腳本的閱讀位置寫清楚。 | convert parser family、TSP canonical path 與研究工具輸出之間的 cross-flow 仍可再畫得更細。 | 補更細的 cross-flow 與失敗分支，但不以新增清單為主。 |
| 功能函數/輔助函數層 | 35% | 59 | Red | `05_api_reference.md` 全量基線仍是 `1321` 條 API，但現在已有 `69` 份核心模組文件、`308` 個手寫函式/helper 小節，並且在 `05_api_reference.md` 補進 `45` 個核心模組的人工工程補充區，覆蓋 runtime 主鏈、solver family、Numba hot-loop、`experiment.evaluation` / `cli.exp`，以及 `tests/valid` 全部 `36` 份模組。 | 全量 API 仍多數留在模板層；`630` 條泛化用途句、`1191` 條模板化輸入句、`894` 條模板化副作用句、`382` 條無明確呼叫者句仍未被系統性清理。主缺口已轉向 API 索引長尾、研究型 tools 與部分 solver helper 深度不足，而不是 `tests/valid` 覆蓋缺漏。 | 下一波改成按 API 長尾與研究工具收尾：先補 `05_api_reference.md` 未人工補充的核心檔，再回頭加深研究型 tools / solver helper 說明。 |
| 治理/新鮮度層 | 10% | 84 | Yellow | dashboard 已完成第十一次正式重評，且本次同步更新了 active-tree 模組覆蓋 `113/113`、函式級手寫章節 `69` 檔 / `308` 小節、`tests/valid` 手寫覆蓋 `36/36`，以及 `05_api_reference.md` 的 `45` 個人工補充區塊四組證據。 | 仍沒有自動提醒或靜態檢查機制；函式層模板句指標尚未建立可重複計算流程。 | 把 dashboard 重評納入固定檢查腳本，並補函式層模板句指標的可再生統計流程。 |

加權總分計算：
`91 * 0.15 + 98 * 0.20 + 95 * 0.20 + 59 * 0.35 + 84 * 0.10 = 81.40`，四捨五入後為 `81 / 100`。

## 已知缺口清單

- `old/` 明確排除在短期補強目標之外；它保留為歷史參考區，不再作為 active-tree 模組覆蓋分數的扣分來源。
- `05_api_reference.md` 已開始出現核心模組的人工工程補充區，但整體仍以 coverage 為主，尚未成為可維護的全量函式級工程文件。
- solver、Numba helper、`cli.exp` / `experiment.evaluation` evaluator helper，以及 `tests/valid` 模組都已進入函式級工程說明，但仍只覆蓋主幹，不是全量去模板化。
- `old/transform.py` 目前有 `IndentationError`，仍只保留 parse error 紀錄，不納入本波修補。
- 目前 governance 規則已成立，但還沒有自動化驗證「文件有改、dashboard 沒改」的檢查。
- 接下來的優先順序維持：
  1. 把同樣的函式級寫法擴到 `05_api_reference.md` 尚未人工補充的核心區段、solver helper 長尾與研究型 tool helper。
  2. 逐步把函式層從「有章節」提升到「有足夠深度」，尤其是研究腳手架與薄測試檔。
  3. 建立 dashboard 自動檢查與函式層模板句統計流程。

## 更新紀錄

| 日期 | 變更文件 | 分數變化 | 尚未解決問題 |
|---|---|---|---|
| 2026-06-15 | `11_dashboard.md`、`00_index.md` | 初次建立基準，總分 `42 / Red` | 模組級說明不足、函式說明模板句過多、shared memory 與失敗路徑描述不足。 |
| 2026-06-15 | `02_execution_flows.md`、`03_data_and_config.md`、`04_module_guide.md`、`note/plan/modules/*.md`、`11_dashboard.md` | 總分 `42 -> 57`；`系統層 74 -> 84`、`模組層 35 -> 68`、`功能架構層 57 -> 82`、`治理/新鮮度層 40 -> 58`、`功能函數層維持 24` | `solver/`、`rng/`、`converter/` 尚未模組級化；函式層模板句仍是最大瓶頸。 |
| 2026-06-15 | `04_module_guide.md`、`06_solver_algorithms.md`、`note/plan/modules/solver/*.md`、`note/plan/modules/rng/*.md`、`note/plan/modules/converter/*.md`、`note/plan/modules/tools/solver_config_loader.md`、`note/plan/modules/cli/exp/*.md`、`11_dashboard.md` | 總分 `57 -> 61`；`系統層 84 -> 86`、`模組層 68 -> 79`、`功能架構層 82 -> 86`、`治理/新鮮度層 58 -> 62`、`功能函數層維持 24` | evaluator 模組、tests/valid/old 尚未模組級化；函式層仍未去模板化。 |
| 2026-06-15 | `04_module_guide.md`、`07_experiment_and_evaluation.md`、`note/plan/modules/cli/exp/mkp_*.md`、`11_dashboard.md` | 總分 `61 -> 63`；`系統層 86 -> 87`、`模組層 79 -> 84`、`功能架構層 86 -> 88`、`治理/新鮮度層 62 -> 66`、`功能函數層維持 24` | `tests/valid/old` 尚未模組級化；函式層仍未去模板化。 |
| 2026-06-15 | `01_system_architecture.md`、`04_module_guide.md`、`08_validation_and_tests.md`、`note/plan/modules/tests/*.md`、`note/plan/modules/valid/*.md`、`11_dashboard.md` | 總分 `63 -> 66`；`系統層 87 -> 90`、`模組層 84 -> 93`、`功能架構層 88 -> 92`、`治理/新鮮度層 66 -> 71`、`功能函數層維持 24` | `old/` 與剩餘工具模組尚未模組級化；函式層仍未去模板化。 |
| 2026-06-15 | `03_data_and_config.md`、`04_module_guide.md`、`06_solver_algorithms.md`、`note/plan/modules/cli/convert/*.md`、`note/plan/modules/cli/run/main.md`、`note/plan/modules/engine/builders.md`、`note/plan/modules/problem/*.md`、`note/plan/modules/tools/*.md`、`note/plan/modules/pytest_plugin.md`、`11_dashboard.md` | 總分 `66 -> 68`；`系統層 90 -> 91`、`模組層 93 -> 98`、`功能架構層 92 -> 95`、`治理/新鮮度層 71 -> 74`、`功能函數層維持 24` | 非 `old/` 模組已補齊，主缺口正式轉成函式級去模板化與 dashboard 自動檢查。 |
| 2026-06-15 | `note/plan/modules/engine/*.md`、`note/plan/modules/machine/core.md`、`note/plan/modules/experiment/experiment.md`、`note/plan/modules/tools/stat.md`、`note/plan/modules/tools/show.md`、`11_dashboard.md` | 總分 `68 -> 70`；`功能函數層 24 -> 30`、`治理/新鮮度層 74 -> 76`，其餘層級維持 | 函式級手寫說明已進入核心 runtime 鏈，但 `05_api_reference.md` 與 solver/helper 家族仍大多停留在模板層。 |
| 2026-06-15 | `note/plan/modules/simulator/core.md`、`note/plan/modules/cli/run/support.md`、`note/plan/modules/problem/interface.md`、`note/plan/modules/problem/registry.md`、`note/plan/modules/problem/mkp.md`、`note/plan/modules/problem/validation.md`、`note/plan/modules/problem/tsp.md`、`note/plan/modules/problem/yaml.md`、`note/plan/modules/problem/builders.md`、`05_api_reference.md`、`11_dashboard.md` | 總分 `70 -> 73`；`功能函數層 30 -> 38`、`治理/新鮮度層 76 -> 78`，其餘層級維持 | runtime 主鏈已延伸到 simulator、cli.run、problem/validation，但 solver/Numba/evaluator helper 仍是函式層最大缺口。 |
| 2026-06-15 | `note/plan/modules/experiment/evaluation.md`、`note/plan/modules/cli/exp/*.md`、`note/plan/modules/solver/*.md`、`05_api_reference.md`、`11_dashboard.md` | 總分 `73 -> 76`；`功能函數層 38 -> 45`、`治理/新鮮度層 78 -> 80`，其餘層級維持 | solver/Numba/evaluator 主幹已進入函式級說明，但全量 API 去模板化、tests/valid helper 與研究型工具函式仍是主要缺口。 |
| 2026-06-15 | `08_validation_and_tests.md`、`note/plan/modules/tests/*.md`、`note/plan/modules/valid/*.md`、`05_api_reference.md`、`11_dashboard.md` | 總分 `76 -> 79`；`功能函數層 45 -> 53`、`治理/新鮮度層 80 -> 82`，其餘層級維持 | validation/test flow 已進入函式級說明，但 `tests/valid` 尚有 `14` 份文件只有模組級，全量 API 去模板化與治理自動檢查仍未完成。 |
| 2026-06-15 | `08_validation_and_tests.md`、`note/plan/modules/tests/*.md`、`note/plan/modules/valid/__init__.md`、`05_api_reference.md`、`11_dashboard.md` | 總分 `79 -> 81`；`功能函數層 53 -> 59`、`治理/新鮮度層 82 -> 84`，其餘層級維持 | `tests/valid` 已達函式級全覆蓋，但全量 API 去模板化、研究工具 helper 深度與治理自動檢查仍未完成。 |
