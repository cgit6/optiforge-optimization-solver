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

```cmd
/home/sean/mkp/.venv/bin/python -m mkp.cli.run \
  --experiment-id my_exp \
  --dataset WEISH \
  --problems weish01 \
  --solver bsma_v1_008 \
  --repeat 1 \
  --base-seed 101 \
  --output-dir ./output
```

## 系統層實作問題

- 搞清楚目前需要維護的清單有多少
- 系統中有多少預設參數(可能會導致操作人員以為正常但結果非預期的情況)
- 若新增一個新的算法需要哪些事情做一個 "操作手冊" 出來
- 修改命名，現在的名稱都過長而且都很不精確，然後需要對目前專案進行 "註釋"

- 輸出有問題，結果是非預期的內容(我預期要的內容是每一次獨立執行模擬一題的 最佳解、最佳適應值、執行時間、評估物品時間)
- RNG 雖然是用 numpy 的，但是還是要放在獨立一個模組當中
- `cil/convert` 執行轉換題庫的功能透過命令行參數決定解析函數這件事是否有優化的可能? 感覺目前這樣使用者的認知成本有點高。
- 將 求解方法與 問題解耦，意思是 我同一個算法可以計算 MKP 問題也可以計算 TSP 問題，這個比較複雜一點，問題可以放在獨立模組中，然後用註冊清單的方式管理目前模擬系統中所有優化問題，然後在執行模擬的命令參數中可以選擇要求解什麼問題。我不確定這會不會衍伸什麼其他的問題出來。我想做這件是但是我現在擔心的是每個優化問題他的編碼都是獨特的，有時候算法需要針對這個特殊的編碼去特別設計那這樣的話，就會變成說如果任意選擇一個問題和算法可能會出現非預期的問題可能會根本無法執行(比如說 連續型的問題用離散型算法求解) 或是類似的問題可能可以跑但結果會是錯的這個通用性的問題似乎變成不是那麼好處理。
- `ProblemModel` 現在是 MKP 專用：values / weights / capacities / best_known
- 執行模擬時用進度條顯示

## 優化算法
- 檢查一下算法架構是否需要調整
- 考慮算法迭代時若用併發處理 thread 併發觸發 GLI 影響效能的問題
- 在 SolveResult 添加可以提交當前狀態的 hook function。hook 會以一個共同入口提交當下狀態，在算法中調用的方式大概像 SolveResult.addAct(當前狀態, 當前編碼, 其他算法狀態) 
