---
artifact_type: socratic-knowledge
schema_version: 2
id: "20260913-optiforge-architecture-improvement-discussion"
title: "Optiforge 架構優化討論紀錄"
status: provisional
verification: source-backed
mode:
  - A
  - D
topics:
  - "optimization architecture"
  - "reproducibility"
  - "RNG seeding"
  - "parallel execution"
  - "solver and problem registration"
aliases:
  - "Optiforge 優化討論"
  - "RNG 重現性決策"
created: "2026-09-13"
updated: "2026-09-13"
---

# Optiforge 架構優化討論紀錄

## 快速檢索卡

- 核心問題：比較 Optiforge 與參考 Slot 模擬系統，逐題釐清可重現性、擴充性、平行執行與模組邊界的設計決策。
- 當前結論：固定迭代停止可提供有條件的精確重現；時間停止必須保留，但不保證結果相同。
- 關鍵爭點：task seed 的身分、worker 與 RNG 的關係、停止條件、execution fingerprint，以及 solver 內部平行化。
- 適用於：Optiforge 的實驗組裝、RNG、Machine、Simulator、Experiment 與 replay 設計。
- 不適用於：尚未實測的跨硬體 bitwise 一致性，以及尚未討論完成的 solver 內部平行 RNG。
- 待驗證：不同 solver／param variant 是否共享 seed、平行 solver 的 RNG 子串流，以及 exact replay 的自動化測試矩陣。

## 記錄規則

- 每個已形成結論的議題立即新增一個 block，不等待整場討論結束。
- block 保留當時的問題、攻防、決策過程與結論；後續即使出現衝突，也不回寫舊 block。
- 新結論若修正或推翻舊結論，另開新 block，並標明它與舊 block 的關係。
- 每個 block 使用 Asia/Taipei（UTC+08:00）時間，記錄該次結論形成的時間點。
- 「當時結論已確認」只代表該回合已形成決策，不代表後續不能推翻。

## 核心問題

目前系統以可重現實驗為首要價值，solver/problem 註冊便利性次之；平行吞吐是效能需求，清楚邊界則是約束其他設計的原則。討論採逐題辯論，每題形成結論後保存完整但精簡的演化脈絡。

## 形成的知識

### D01｜RNG 停止條件與重現性

- 討論時間：2026-09-13 09:40:58 +08:00
- 狀態：當時結論已確認
- 討論問題：相同初始 seed 是否應保證實驗得到完全相同的結果，以及 worker 數量與停止條件應如何影響這項保證。
- 初始主張：相同 seed、RNG 算法與 RNG 消耗次數應產生完全相同的結果；併發執行可能需要從初始 seed 派生 worker seed。
- 關鍵挑戰：若 seed 綁定 worker，task 分配會隨 worker 數與排程改變；若使用 `max_seconds`，即使同一裝置也可能因執行進度差異而在不同迭代停止。
- 決策過程：先確認現行程式是在排程前按邏輯 task 派生 seed，而不是讓 worker 持有持續演進的 RNG；再用時間停止作為反例，將無條件的精確重現主張收縮為兩級契約；最後排除跨裝置結果一致性的要求，並補入 execution fingerprint 前提。
- 結論：
  1. task seed 必須在排程前由邏輯 task 身分派生；外層 scheduler 與 worker 不應持有會影響結果的共享 RNG 狀態。
  2. `max_iterations` 在 problem、solver、參數、程式、依賴、RNG 與 seed 派生規則一致時，可提供 exact replay；改變外層 worker 數與完成順序不應改變結果。
  3. `max_seconds` 必須保留，但只能提供 traceable run；不保證迭代數、RNG 消耗量或最終結果相同。
  4. 跨裝置執行不承諾完全相同的結果。
  5. 結果應保存 execution fingerprint，至少能追溯 problem 資料、solver 設定、停止條件、base/task seed、seed 派生版本、RNG、程式版本與關鍵依賴版本。
- 主張變化：`相同 seed 即完全重現` → `worker-independent task seed` → `固定工作量才保證 exact replay` → `跨裝置排除，時間停止降級為 traceable run`。
- 適用邊界：目前結論針對外層 task-level multiprocessing；尚未涵蓋 solver 內部自行平行運算、非確定性數值 kernel 或不同硬體環境。
- 待處理問題：不同 solver／param variant 是否共享同一 task seed；solver 內部平行化時如何派生 RNG 子串流；execution fingerprint 的必要欄位與 exact replay 測試方式。
- 依據來源：使用者於本輪提供的需求與限制；`rng/seeding.py`、`rng/strategy.py`、`machine/core.py`、`engine/models.py`、`tools/solver_config_loader.py`。

## 討論的演化

- D01：從「相同 seed 應完全一致」出發，經 worker 排程與時間停止反例後，形成 exact replay／traceable run 分級契約。

## 邊界與未解問題

- K1 的現行 task seed 不包含 solver ID 與 param-set index；是否維持跨 variant 共用 seed 尚未定案。
- solver 內部若引入平行化，RNG 消耗可能再次受到排程影響，需要獨立討論。
- 尚未建立 execution fingerprint schema 與自動化重現測試。
- 參考系統 K2 的 upstream `problab` 實作不在本輪指定路徑內；目前只採用 K2 專案接線與其內附文件，不把所有 upstream 細節視為已驗證事實。

## 知識範圍與前提

- K1｜`/home/sean/optiforge-optimization-solver`｜目前系統｜已參考・鎖定。
- K2｜`/home/sean/work/steak_math_v0510`｜參考 Slot 系統｜已參考・鎖定。
- 實際採用的 K1 來源集中於 `engine/`、`machine/`、`simulator/`、`experiment/`、`problem/`、`rng/`、`solver/`、`tools/`、`cli/` 與架構文件。
- 實際採用的 K2 來源集中於 `pkg/engine`、`internal/rng`、`cmd/run`、`cmd/opt`、`go.mod` 與 `plan/docs` 架構文件。
- LLM 背景知識已開啟，只用於一般軟體架構與確定性推論，不視為外部查證。
- 本文件區分專案程式事實、使用者設計要求與討論推論；未完成的議題保留為待處理問題。

## 交接資訊

- 可安全採用 D01 的停止條件分級，作為後續 RNG 設計的暫定基線。
- 不可假設不同硬體、時間停止或 solver 內部平行執行能產生完全相同的結果。
- 下一步由異端辯士挑戰 exact replay 契約的必要性與維護成本。

## 追加討論紀錄

### D02｜Exact replay 與統計可重現性的角色

- 討論時間：2026-09-13 09:42:39 +08:00
- 狀態：當時結論已確認
- 與既有結論的關係：補充並收縮 D01，不回寫 D01 的當時結論。
- 討論問題：研究型最佳化平台是否應把單次執行結果完全相同，視為最重要的可重現性保證。
- 初始主張：符合 execution fingerprint 且採固定迭代停止時，系統應提供 exact replay。
- 關鍵挑戰：隨機最佳化研究真正關心的是多個 seed 下的結果分布；鎖定單次結果可能增加環境維護成本，也不能證明算法品質可靠。
- 決策過程：接受 exact replay 不能代表研究結論可重現，也不應限制跨版本或跨硬體演進；但保留它作為同一 execution fingerprint 內定位 RNG、排程與程式回歸的工程契約，並將研究可信度交給獨立的統計可重現性契約。
- 結論：
  1. 可重現性分成兩個互補維度，不再以單一等級表達。
  2. Deterministic replay 用於除錯與 regression testing；在固定 execution fingerprint、固定工作量與相同 task seed 下，外層 worker 數不應改變單次結果。
  3. Statistical reproducibility 用於評估算法品質；必須比較多個 seed 的分布與彙總指標，單次 exact replay 不能替代它。
  4. execution fingerprint 改變後即進入新的重現範圍，不要求新舊環境產生完全相同結果，但必須能辨識兩者不可直接宣稱等價。
  5. `max_seconds` 執行只承諾可追溯與統計評估，不承諾 deterministic replay。
- 主張變化：`exact replay 是首要研究保證` → `exact replay 是受限的工程診斷契約` ＋ `統計可重現性是研究結論契約`。
- 適用邊界：本結論尚未定義統計指標、容許誤差或跨版本比較門檻，也尚未證明所有現行 solver 都能達成 deterministic replay。
- 待處理問題：驗證 NumPy／SciPy／Numba 與各 solver 的實際確定性；定義統計可重現性的 seed 數量、指標與接受標準；確定 execution fingerprint schema。
- 依據來源：使用者對可重現性與時間停止的要求；`rng/seeding.py`、`experiment/seed_bank.py`、`engine/models.py`、`machine/core.py`、`.github/workflows/ci.yml`；一般隨機實驗設計背景知識。

### D03｜論文投稿所需的實驗可重現性

- 討論時間：2026-09-13 09:46:24 +08:00
- 狀態：當時結論已確認；投稿規範的普遍性仍待外部查證
- 與既有結論的關係：修正 D02 對 exact replay 工程價值的表述，不回寫 D02；D02 所稱「不能單獨證明算法品質」仍保留。
- 討論問題：exact replay 是否只是除錯能力，或同時是論文實驗可重現性的一部分。
- 初始主張：D02 將 deterministic replay 主要定位為除錯與 regression testing，將統計可重現性定位為研究結論契約。
- 使用者修正：投稿論文通常要求實驗可被重現，因此「能重播」本身也是實驗系統的重要要求，不能只視為工程便利。
- 決策過程：接受論文需要可重現的實驗產物，但進一步區分「提供足夠材料重新執行」、「固定條件下重現單次結果」與「多 seed 下重現研究結論」；保留 exact replay 的論文價值，同時避免把單次相同結果誤當成算法穩健性的完整證明。
- 結論：
  1. Paper artifact reproducibility 是系統核心需求：應保存或提供程式版本、依賴、problem 資料、solver config、停止條件、seed 與執行命令，使投稿審查者能重新執行實驗。
  2. Deterministic replay 是 artifact reproducibility 的一部分：在相同 execution fingerprint 與固定工作量下，單次 run 應可得到相同結果，並可作為論文數值表與除錯的驗證工具。
  3. Statistical reproducibility 是另一項必要證據：隨機算法的研究主張仍須由多 seed 的分布與統計摘要支持。
  4. 三者是包含但不等價的需求；能重播單次結果很重要，但不能單獨證明算法品質或研究結論具有穩健性。
  5. `max_seconds` 實驗仍應完整保存 artifact 與 seed，但只能重現執行條件及統計結論，不承諾單次終點完全相同。
- 主張變化：`exact replay 主要是工程診斷契約` → `exact replay 同時是論文 artifact reproducibility 的重要組件，但不是研究穩健性的充分條件`。
- 適用邊界：這是本專案決定採用的投稿級設計要求；不同期刊、會議或 artifact badge 是否要求 bitwise-identical output 尚未查證，不宣稱所有投稿規範完全一致。
- 待處理問題：確認目標投稿場域的 reproducibility／artifact 規範；設計可攜的 run manifest；定義統計重現的指標與門檻。
- 依據來源：使用者對投稿需求的修正；K1 的 `readme.md`、`experiment/seed_bank.py`、`engine/models.py`、`tools/show.py`、`.github/workflows/ci.yml`；一般研究可重現性背景知識。

### D04｜外部投稿與 Artifact 標準對「完整還原」的要求

- 討論時間：2026-09-13 16:21:29 +08:00
- 狀態：外部查證完成；當時結論已確認
- 與既有結論的關係：以官方規範驗證並收緊 D03，不回寫 D03；否定「只要符合統計分布即可滿足投稿重現要求」這種過度寬鬆的解讀。
- 討論問題：主要電腦科學與最佳化投稿／artifact 規範，是否普遍要求完全還原實驗，以及是否要求跨硬體 bitwise-identical output。
- 初始主張：投稿可能只要求材料完整、主要結果可合理再現，不一定要求所有數值逐位元一致。
- 使用者修正：指導教授要求最好能完整還原；僅符合統計分布不足以作為本系統的實驗標準。
- 查證結果：
  1. NeurIPS 要求提供重現主要實驗結果所需的 code、data、instructions，並明示應包含 exact command 與 environment；同時另要求說明變異來源與統計顯著性。這表示「可執行地重建主要結果」與「統計證據」是並列要求，後者不能取代前者。
  2. INFORMS _Operations Research_ 期望作者提供所有 code、scripts、data 與足以讓他人重現論文結果的說明；_INFORMS Journal on Computing_ 對以計算實驗為主要貢獻的論文，把釋出軟體列為最終接受條件，並將 repository 與論文一同凍結。
  3. ACM PADS 的 artifact 評估要求 artifact documented、consistent、complete、exercisable；Results Reproduced 指主要結果由作者以外的人使用作者 artifact 成功取得。
  4. 但跨硬體逐位元相同不是一致的普遍門檻。ACM SIGMOD 明示：時間等結果受硬體影響，無相同硬體時不期待 identical results，而要求重建資料／圖表並支持相同核心行為與結論。
- 決策過程：官方規範支持使用者與指導教授對「完整材料、可實際重跑、能重建主要結果」的要求，因此不能把統計分布相符當成唯一驗收；另一方面，官方規範也沒有形成「任何硬體、任何停止條件皆須 bitwise identical」的共同要求。故將本專案的標準定得比最低投稿規範更強，但把保證範圍寫清楚。
- 結論：
  1. Optiforge 採用「完整還原優先」作為內部標準；僅有相近統計分布不算完成實驗重現。
  2. 論文主要數值實驗應使用固定工作量（如 `max_iterations`／固定 evaluations），並在相同 execution fingerprint 下要求 deterministic exact replay。
  3. 每次論文 run 必須保存不可變的 run manifest、程式 commit、problem/data hash、完整 solver config、base/task seeds、RNG 與 seed-derivation 版本、dependency lock/container、執行命令、raw per-run results，以及產生圖表與表格的腳本。
  4. 多 seed 統計分析仍然必要，用來證明算法結論穩健；它是 exact replay 之外的第二道要求，不能替代 exact replay。
  5. `max_seconds` 必須保留，但歸類為 performance/time-budget experiment：保存同等完整 artifact、硬體資訊、實際迭代／evaluation 數與多次重複統計，不宣稱單次終點 exact replay。
  6. 跨硬體重跑的驗收是能重建主要數據、圖表與結論；跨硬體 bitwise equality 不列為共同承諾。同硬體也只有在固定工作量及 execution fingerprint 一致時才承諾 exact replay。
- 主張變化：`材料完整且統計相近可能足夠` → `官方標準要求材料可執行並能重建主要結果` → `本專案採更嚴格的同 fingerprint／固定工作量 exact replay，同時保留跨硬體與時間停止的明確例外`。
- 適用邊界：這是跨 NeurIPS、ACM artifact/SIGMOD 與 INFORMS 最佳化期刊規範歸納出的工程基線；實際投稿時仍需再核對目標 venue 當年度規範。`exact` 的比較層級（完整 raw output、最佳解、軌跡或 bit pattern）尚待另題定義。
- 待處理問題：選定目標 venue 後建立 compliance checklist；定義 exact replay 的欄位級驗收；確認 NumPy／SciPy／Numba、浮點 reduction 與 solver 內部平行化對同 fingerprint replay 的限制。
- 外部來源：
  - [NeurIPS Paper Checklist Guidelines](https://neurips.cc/public/guides/PaperChecklist)
  - [ACM SIGMOD Availability & Reproducibility Initiative](https://reproducibility.sigmodconf.hosting.acm.org/)
  - [ACM SIGSIM PADS 2024 Reproducibility and Artifact Evaluation](https://sigsim.acm.org/conf/pads/2024/blog/artifact-evaluation/)
  - [INFORMS Journal on Computing Software Policy](https://pubsonline.informs.org/page/ijoc/softwarepolicy)
  - [INFORMS Operations Research Code and Data Disclosure Policy](https://pubsonline.informs.org/page/opre/code-and-data-disclosure-policy)

### D05｜停止模式的完整集合與混合模式語意

- 討論時間：2026-09-13 16:32:58 +08:00
- 狀態：當時結論已確認
- 與既有結論的關係：精確化 D01、D03、D04 對停止條件的分類；不回寫舊 block。另將 D04 所稱的結果分類標記移出結果資料，改由文件定義契約。
- 討論問題：系統應支援哪些停止模式；同時設定時間與迭代上限時，兩項限制如何組合；結果是否需要標示可否 exact replay。
- 初始主張：論文主要數值實驗優先使用固定迭代；時間停止保留但不保證 exact replay，並曾提議在結果中標記其分類。
- 使用者修正：三種模式都必須支援；結果資料不需要額外標記是否可重現，相關保證寫在文件；混合模式採任一上限先到即停止。
- 決策過程：先區分「支援的停止能力」與「建議用於 exact replay 的模式」，避免把論文建議誤寫成系統功能限制；再把混合條件定義為 OR，讓時間與迭代都保持上限語意；最後將重現性分類視為模式契約，而不是每筆結果的評價欄位。
- 結論：
  1. 系統支援 `iteration-only`、`time-only`、`time-or-iterations` 三種停止模式。
  2. `time-or-iterations` 採 OR 語意：時間上限或迭代上限任一先到即停止。
  3. 只有 `iteration-only` 可在 execution fingerprint 相同的前提下承諾 deterministic exact replay。
  4. `time-only` 與 `time-or-iterations` 都可能由時間決定 RNG 消耗量，因此模式契約不承諾 exact replay；即使某次混合執行實際由迭代上限先觸發，也不把整個模式提升為無條件可重現。
  5. 不在每筆結果加入 `reproducible` 或同類判斷欄位；各停止模式的重現保證由系統文件統一定義。
- 主張變化：`固定迭代是主要模式，時間模式另行分類` → `三種模式都是正式能力` → `混合模式明定為任一上限先到即停，重現性差異留在文件契約而非結果標籤`。
- 適用邊界：本結論只定義停止條件與模式級重現保證，不決定結果 schema 是否保存實際停止原因、實際迭代數或 elapsed time。
- 待處理問題：結果資料的最小必要欄位；一般文件、版本庫與 experiment-level manifest 各自應負責保存哪些重現資訊。
- 依據來源：使用者本輪確認；D01–D04 的既有討論與外部查證。

### D06｜實驗設定快照與同名實驗覆寫策略

- 討論時間：2026-09-13 16:37:36 +08:00
- 狀態：當時結論已確認；失敗時的替換原子性尚待討論
- 與既有結論的關係：收縮 D04「每次 run 保存完整 manifest」的要求，延續 D05 對結果資料精簡化的方向；不回寫舊 block。
- 討論問題：一般文件能否取代單次實驗設定快照，以及相同實驗重新執行時是否保留設定歷史。
- 初始主張：每筆結果不應重複保存 commit、dependency、RNG 等共同資訊，這些資訊可放在文件或版本庫中。
- 關鍵挑戰：一般文件只能描述系統，不能唯一指出某批結果當時使用的 problem、solver、參數、停止條件與 seed；只靠輸出也無法反推出唯一實驗輸入。
- 決策過程：將資訊拆成研究版本、實驗與單次結果三層；研究版本共同負責程式、文件、依賴鎖定與 RNG 實作，實驗層只保存一次原始設定，結果層保持精簡。使用者確認相同實驗重跑時採覆寫而非在結果目錄維護歷史版本。
- 結論：
  1. 系統應將該次使用的原始 `experiment.yaml` 自動保存到實驗結果目錄，作為整場實驗唯一的設定快照；不在每筆 run 重複。
  2. 研究版本中的文件負責說明 RNG、停止模式與重現性契約；Git commit 與 dependency lock 負責版本級資訊。
  3. 同名實驗重新執行且設定已改變時，新的設定快照覆蓋舊設定；實驗結果目錄內不保留設定歷史。
  4. 因此實驗結果目錄的語意是「同名實驗的最新一次執行」，不是版本庫或不可變 archive。
  5. 現行 `Experiment.run()` 會在執行開始前刪除整個同名實驗目錄，與「不保留舊版」方向一致，但尚未保存原始 `experiment.yaml`。
- 主張變化：`共同資訊全部放一般文件` → `一般文件無法識別特定實驗` → `每場實驗保存一次原始設定，但同名重跑直接覆寫且不留歷史`。
- 適用邊界：本結論不要求在 live result directory 內保留歷史；正式論文 artifact 是否另行凍結，由後續發布流程決定。
- 待處理問題：重跑時是否整個結果目錄一起替換；執行中斷時保留舊的完整結果還是留下空／部分目錄；如何避免新設定與舊結果混合。
- 依據來源：使用者本輪確認；`experiment/experiment.py` 的結果目錄重設流程；D03–D05 的既有討論。

### D07｜同名實驗重跑失敗時的舊結果保護

- 討論時間：2026-09-13 16:41:17 +08:00
- 狀態：需求結論已確認；發布替換機制尚待確認
- 與既有結論的關係：為 D06 的覆寫策略增加失敗安全邊界；不回寫 D06。
- 討論問題：同名實驗重新執行但未能完整產出結果時，舊的完整結果應被刪除還是保留。
- 初始主張：D06 定義同名重跑會覆蓋舊設定且不保留歷史；現行 `Experiment.run()` 在新執行開始前直接刪除舊目錄。
- 使用者修正：只有新實驗能完整產出時才可替換舊實驗；新實驗過程若發生任何意外，舊版實驗結果必須保持不變。
- 決策過程：將「是否保留歷史版本」與「替換失敗時是否保護目前版本」分開。正常完成後仍只留新版，不形成版本歷史；但新結果尚未完成前不得破壞舊的完整結果。
- 結論：
  1. 新實驗的設定、run results、summary 與 seed bank 必須先寫到正式結果目錄之外的 staging directory。
  2. 新實驗全部完成並通過完整性檢查以前，既有同名實驗目錄保持不變。
  3. 新實驗在計算、寫檔或驗證階段失敗時，刪除或隔離 staging 資料，舊結果繼續作為正式結果。
  4. 新實驗成功發布後只保留新版正式結果；結果目錄內仍不維護歷史版本。
  5. 現行「執行開始前 `shutil.rmtree(experiment_output_dir)`」不符合這項失敗保護需求，後續實作必須調整。
- 主張變化：`同名重跑直接覆寫且不留歷史` → `不留歷史，但只在新版完整可用後才替換；失敗時舊版保持不變`。
- 適用邊界：需求已確認，但「先刪舊目錄再移入新版」仍存在刪除與搬移之間的崩潰窗口，尚未視為已確認的安全實作。
- 待處理問題：採用可恢復的 backup-rename 流程、版本目錄加原子 current pointer，或限定平台後使用目錄交換；同時需定義完整性檢查與啟動時的殘留 staging 復原規則。
- 依據來源：使用者本輪確認；`experiment/experiment.py:58-61`；D06 的既有討論。

### D08｜現行結果落地粒度與簡化替換方向

- 討論時間：2026-09-13 17:06:27 +08:00
- 狀態：現況已確認；最終快取／落地策略尚待決定
- 與既有結論的關係：補充 D07 的程式現況；使用者否決 D07 待處理項目中的 backup-rename／複雜交換方向，但不回寫 D07。
- 討論問題：現行實驗是每完成一題就落地結果，還是將整場資料全部快取後才輸出；這會如何影響「新版成功前保留舊版」的簡單作法。
- 使用者立場：不採 staging、backup rename 等搬移與復原機制；保留簡單作法，在新資料成功產出後才清空舊資料並寫入新版。
- 程式查核：
  1. `Experiment.run()` 目前在任何計算開始前刪除整個同名實驗目錄。
  2. `_run_dataset()` 依序處理各個 problem。
  3. `_run_problem()` 只在記憶體累積當前 problem 的 accepted rows；problem 收集完成後，立即呼叫 `write_simulator_result()`。
  4. `write_simulator_result()` 依 solver／param variant 立即寫出 `runs.csv`、`runs.json`、`summary.json` 與 `summary.csv`。
  5. 全部 problem 完成後，才在實驗根目錄寫出整場 `summary.json` 與 `seed_bank.json`。
- 結論：現行流程是「當前 problem 暫存在記憶體，problem 完成即落地」的混合模式，不是每個 task 立即落地，也不是整場實驗完成後一次輸出。若後續 problem 失敗，先前 problem 的新版部分結果會留在磁碟，但舊實驗已在開跑前被刪除，因此不符合 D07 的舊結果保護需求。
- 主張變化：`考慮 staging＋可恢復交換` → `使用者要求保留簡單替換` → `確認現行逐 problem 落地與簡單的整場延後替換存在結構衝突`。
- 適用邊界：本 block 只確認目前落地時機及使用者的簡化方向，尚未決定要改成整場記憶體快取，還是允許最小限度的暫存輸出。
- 待處理問題：若不使用 staging，是否接受整場結果留在記憶體直到所有 problem 完成；若輸出檔本身寫入失敗，是否接受舊目錄已被清除而無法恢復。
- 依據來源：使用者本輪修正；`experiment/experiment.py` 的 `run()`、`_run_dataset()`、`_run_problem()`；`tools/show.py` 的 `write_simulator_result()`。
