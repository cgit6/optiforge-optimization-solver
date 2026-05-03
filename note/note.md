# 最佳化模擬平台介紹


## 概述

這是一個...


## 模組介紹

為了維持系統擴容與維護性...

### RNG 搭建


### main 函數

- 解析命令行參數
- 驗證命令參數
 
### Engine 模組


### Simulator 模組

### Solver 模組


### run 模組

執行後先解析命令參數，

### converter 模組

#### 模組介紹

在該模組中有兩個主要的函數 `transformToMomery` 和 `transformToYaml` 用於對原始題庫做轉換。前者轉換後保存至記憶體中，後者將 dat/txt 原始題目轉換後保存到 yaml 中。

`converter` 模組供 `cil/convert` 執行模組調用，開發人員可以根據題庫格式於 `cli/convert/resgister.py` 中註冊解析函數(key value pair)，透過命令行參數指定選用解析函數。

#### 模組問題

- `build` 函數有個問題，就是目前返回的資料格式無法兼容所有的問題(kp, tsp, ..., vrp) 所以返回的 `ProblemModel` 必須要重新定義資料結構。但是每一個優化問題必須要一個獨立的 `ProblemModel` 資料結構嗎? 如果要的話在哪裡註冊會比較好? 能不能透過抽象問題的結構解決這個問題? 若光是 `converter` 模組就要維護兩個自定義內容系統在維護上可能會過於複雜。

## 命令

### 題庫轉換

weing 轉換格式命令: `.venv/bin/python -m mkp.cli.convert --dataset WEING --converter weing --repo-root .`

### 執行模擬

執行模擬(cd /home/sean/mkp): 

`--experiment-id`: 實驗 id
`--problem-type`: 優化問題類型
`--dataset`: 提庫
`--problems`: 問題 
`--solver`: 算法
`--repeat`: 重複次數
`--base-seed`: 隨機種子
`--output-dir`: 輸出的資料夾
`--execution-mode`: 是否併發

以下範例 算法 bsma 獨立執行 20 次 隨機種子 42:
```cmd
.venv/bin/python -m mkp.cli.run   --experiment-id bsma_weish_repeat20_worker   --problem-type mkp   --dataset WEISH   --problems weish01,weish02,weish03,weish04,weish05,weish06,weish07,weish08,weish09,weish10,weish11,weish12,weish13,weish14,weish15,weish16,weish17,weish18,weish19,weish20,weish21,weish22,weish23,weish24,weish25,weish26,weish27,weish28,weish29,weish30   --solver bsma  --repeat 20   --base-seed 42   --output-dir output   --execution-mode worker_curriculum
```

## 系統層可以優化的問題

- []搞清楚目前需要維護的清單有多少。清點後盡量減少或是自動化
- []系統中有多少預設參數(可能會導致操作人員以為正常但結果非預期的情況)
- []若新增一個新的算法需要哪些事情做一個 "操作手冊" 出來
- []修改命名，現在的名稱都過長而且都很不精確，然後需要對目前專案進行 "註釋"
- []RNG 雖然是用 numpy 的但是還是要放在獨立一個模組當中，準備未來自建一組 PRNG 模組
- []`cil/convert` 執行轉換題庫的功能透過命令行參數決定解析函數這件事是否有優化的可能? 感覺目前這樣使用者的認知成本有點高。
- [v]執行模擬時用進度條顯示

- [] 輸出有問題，結果是非預期的內容(我預期要的內容是每一次獨立執行模擬一題的 最佳解、最佳適應值、執行時間、評估物品時間) json 格式也有問題多筆資料應該是陣列不是多個物件。

## 系統層功能
- [v]將求解方法與 問題解耦，意思是 我同一個算法可以計算 MKP 問題也可以計算 TSP 問題，這個比較複雜一點，問題可以放在獨立模組中，然後用註冊清單的方式管理目前模擬系統中所有優化問題，然後在執行模擬的命令參數中可以選擇要求解什麼問題。我不確定這會不會衍伸什麼其他的問題出來。我想做這件是但是我現在擔心的是每個優化問題他的編碼都是獨特的，有時候算法需要針對這個特殊的編碼去特別設計那這樣的話，就會變成說如果任意選擇一個問題和算法可能會出現非預期的問題可能會根本無法執行(比如說 連續型的問題用離散型算法求解) 或是類似的問題可能可以跑但結果會是錯的這個通用性的問題似乎變成不是那麼好處理。
- []檢查統計模組，統計模組有兩個功能 1.統計、2.輸出 兩個要拆開
- []實驗模組(cil/opt) 給定一組指定範圍的算法設定檔(允許一個算法有多組設定檔例如 bsma z=0.03,transform=v、z=0.05,transform=s、...、z=0.08,transform=u) 允許一次創建多個 Simulator 物件同時執行多算法多參數模擬獲取 "統計結果" 所有的算法執行模擬完之後筆對結果是否符合判定標準(可以自定義判定標準，然後註冊) 若符合則通過保存結果，若未通過 `seed+=1` 後再跑一次全模擬直到通過或是超出 seed 允許範圍(可以自訂 seed 從 [0,100] 做實驗)。這是一組實驗可以串接多組實驗找出符合預期的結果，筆對的對象可以是算法模擬的結果也可以是一組靜態數據可以是一個筆對的對象也可以是多個筆對的對象，白話說就是跑到出現理想結果為止。

## 優化算法
- []檢查一下算法架構是否需要調整
- []考慮算法迭代時若用併發處理 thread 併發觸發 GLI 影響效能的問題
- []在 SolveResult 添加可以提交當前狀態的 hook function。hook 會以一個共同入口提交當下狀態，在算法中調用的方式大概像 SolveResult.addAct(當前狀態, 當前編碼, 其他算法狀態) 
- []記得添加 Gurobi 的 slover 腳本

- [v]對 BSMA numba 版本在改成 支援 numba 之後，貼到 code file 中，進行測試是否可以順利執行，求解 gk 題庫 第一和第二題。 實驗(repeat) 1 次和 20 次。如果有問題就修改。實驗除了確保結果需要保持一致以外，還需要看總執行時間。最後我想知道的是算法是否有保持一樣的初始解、過程、結果，還有最後執行時間是否有縮減

- [v]現在 傳入 `BSMANumbaCore` 物件中的資料格式並沒有被嚴格定義，我希望可以優化整個資料路徑，看能不能解析出來的時候就保持正確嚴謹的資料格式最終傳到 `BSMANumbaCore` 物件所需的資料格式盡量不要到 算法中還要做 `self.values = np.ascontiguousarray(values, dtype=np.int64)` 這種事。然後路徑中的資料格式如果更新了之後檢查其他 solver 文件的 core 物件需不需要更新資料格式。因為我這些資料是要準備給 Numba 使用的所以需要精確固定的資料格式


## 界面

- 等系統穩定+ 我完全搞懂流程之後，做一個 web 界面可以開 server 跟 前端 UI 對系統進行操作。


## 新算法註冊

1. config/<algo_name>.yaml
2. `/home/sean/mkp/simulator/core.py` 的 `_build_process_local_registry` 函數
3. `/home/sean/mkp/engine/builders.py` 的 `default_solver_builders` 函數
4. `/home/sean/mkp/simulator/core.py` 的 `_PROCESS_SAFE_SOLVERS` 函數

