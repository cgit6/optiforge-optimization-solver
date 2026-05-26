# 系統問題

## 問題討論

[問題1] 算法是不是需要類似 Act 函數可以提交過程的狀態用於研究?
[目標]
[方案]

[問題2] cil.run 要可以支援定義直接給 run seed 陣列然後執行模擬。
[目標]
[方案]

[問題3] 目前 solver 的清單 Engine 和 Simulator 各自維護一份，感覺這個有點重複了。
[目標]
[方案]

[問題4] Gurobi 也要進 solver 中求解 mkp 問題

[問題5] exp_cfg.yaml 的 repeat 應該要移除，然後應該要移動到 experiment 作為模組預設的重複次數，而且沒有公開 api 可以改這個數字(300000000000)

exp/main.py 的 預設參數也是，這應該要是 experiment 模組的預設，不應該由外部定義路徑。而且也不能有公開 API 去修改設定
DEFAULT_CONFIG_PATH
DEFAULT_PROBLEM_ROOT
DEFAULT_SOLVER_ROOT
DEFAULT_OUTPUT_ROOT

[問題6] 優化器應該產出一個 seed_bank.json 然後算法設定檔有一個開關，根據這個 seed 跑結果但是最終實驗只會對某幾組參數做實驗，所以當初在跑 cil.exp 的時候並不會將範圍外的算法參數組合納入其中，可能會導致跑出非預期的結果。
