# 系統問題

## 問題討論

[問題1] 算法是不是需要類似 Act 函數可以提交過程的狀態用於研究?
[目標] 算法可以在運行過程中執行 `Act("狀態","編碼","對外訊息")` 將狀態提交到緩存中
[方案] 這個 method 要掛在 `Machine> ` 物件下面。但是這個問題暫時無法處理，需要對 Machine -> Solver 之間做重構後再處理

`*problab.Machine > *slot.Game > *slot.GameMode > *buf.GameModeResult > AddAct(...)`

[問題2] cil.run 要可以支援定義直接給 run seed 陣列然後執行模擬。
[目標] cil.run 要可以重現 cil.exp 的結果
[方案] cil.exp 結束後會輸出一個 seed_bank 他會對指定的算法組合做結果的重現，算法設定檔那邊可以設定 opt 打開。所以這個問題有三件事要處理。

1. seed 需要在執行 `cil.exp` 後被保存下來。保存至 seed_bank.json 然後把檔案放在 seed folder 中
2. 算法設定那邊需要一個開關。用於判斷是否要用預定的那些 seed 來執行模擬。
3. 模擬的時候需要判斷開關，以及開了之後的後續動作。

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

[問題7] 缺乏視覺介面(GUI)來執行模擬操作

[問題8] 添加 Makefile

[問題9] docker、打包成套件的架構

[問題10] 優化(簡化)註冊 solver 的流程，調查清楚目前系統內一共有多少個各式各樣的註冊清單(調查範圍不限於 solver)
