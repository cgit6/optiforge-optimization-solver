## 問題

[問題1]執行實驗的時候使用 seed 的方式有問題。如果我 cil 輸入 `seed=123456` 且多個算法組合例如以下:

```
bsma z=0.01 tanh_abs
bsma z=0.08 tanh_abs
bsma z=0.15 tanh_abs
bsma z=0.01 sigmoid_s0
bsma z=0.08 sigmoid_s0
bsma z=0.15 sigmoid_s0
bsma z=0.01 abs_pow_16
bsma z=0.08 abs_pow_16
bsma z=0.15 abs_pow_16

bsca a=1.5 tanh_abs
bsca a=2.0 tanh_abs
bsca a=2.5 tanh_abs
bsca a=1.5 sigmoid_s0
bsca a=2.0 sigmoid_s0
bsca a=2.5 sigmoid_s0
bsca a=1.5 abs_pow_16
bsca a=2.0 abs_pow_16
bsca a=2.5 abs_pow_16
```

並執行 Weish 題庫的前 3 題，那我會期望所有的算法在執行 `weish01` 的時候所使用的 seed 都是一樣的。但是 weish01/weish02/weish03 每一題的 seed 都不一樣，假設 cil 那邊的 `seed=123456` 那 weish01 所有算法組合的 seed 可以是 235913， weish02 所有算法組合的 seed 可以是 230984，weish03 所有算法組合的 seed 可以是 320938。

然後一樣的，我在 cil 輸入相同的 seed 進行實驗時，每個算法組合在給相同 seed 的情況下同一題的結果也必須一樣(可重現) 不會因為算法參數設定排序改變(第一組移動到第三組)、算法數量改變(執行一個算法或執行多個算法) 執行題目改變(從 weish01 變成 weish03、weish01) 執行題庫改變而結果有所不同，也就是同一個 seed、同一組算法設定、同一題目，結果在任何情況下皆須保持一致。

[問題2] seed 問題，現在有兩種模擬方式

seed 使用方式1:

```
weish01: seeds 1001~1020
weish02: seeds 1001~1020
...
weish30: seeds 1001~1020
```

seed 使用方式2:
```
weish01: seeds 1001~1020
weish02: seeds 2001~2020
weish03: seeds 3001~3020
```


[問題3] 模擬物件分工還是不夠明確。目前的結構是 Bundle 會創建一個 Simulator 物件，這個物件會執行`多算法x多設定` 組合的模擬結果，並把結果全部存到 `SimulatorResult` 中。目前需要把這些東西都分開並且分開統計。
[目標] 系統可以分開模擬並統計一個題庫下，多組算法+多組設定。串性或併發模擬。

[方案] 一次模擬中題庫有多題目並重複多次，多求解器有多設定。不同 solver 分成多 Simulator 物件處理，不同的 Solver 在 Simulator 中創建多組 `Machine` 分開模擬。而 `Machine` 才應該是真正執行算法求解的地方。

如果該次 `ExperimentSpec` 的 solver_id 是多個 solver 的話，應該要創建多個 `Simulator` 物件。一個 `Simulator` 中僅支持跑一個 solver 的

應該以 Solvers 的數量拆成多張 "實驗規格" 每個 solver_id 拆成 1 張實驗規格。並根據 "實驗規格" 物件創建對應的 Simulator 物件。

假設 cil 參數定義模擬 題庫 Weish 01~30 題、算法有 bsma、bsca

那實驗規格應該要拆成 2 張 一張是 bsma 一張是 bsca 算法的實驗規格。那現在會根據有幾個實驗規格就創建幾個 `Simulator` 物件。每個 Simulator 物件只會負責執行一組題庫 一個 solver 多組算法參數設定的結果。所以 Simulator 的 Result 要改成一個 Result pool 負責分開儲存每一個 solver 一組算法參數的結果

假設 bsma 有 3 組算法參數設定，bsca 有 4 組算法參數設定。在 bsma 的 Simultor 在執行串行或是併發模擬的時候會先創建與算法參數設定相對應數量的 Machine。 每一個 Machine 負責執行 一組 solver + 一組算法參數設定。Machine 物件會自己有一個 Result 物件用於緩存該次求解的結果 格式上應該跟 SimulatorRunRow 類似就是這次 模擬結果的訊息。

執行串行模擬就是一次只會有一個 Machine 在執行求解，但是如果是併發模擬那就是同時會有 n 個 Machine 在執行求解，但是會有一個 Machine Pool 負責去控制同一時間執行求解的數量。在這個 Pool 中的任務才會被執行其他的任務就需要排隊在外面等

Machine 物件中會使用 Share Memory 共同使用一份唯獨的題庫設定，不會各自獨立複製好幾份。Machine 主要的任務就是執行 run task 清單，Machine 會根據 題庫+ 算法+ 算法組合 跑 特定次數(repeat)的求解。

Machine 的 Result 只會緩存當前的求解結果，在開始新的一次求解的時候會清空(重置) Machine 的 Result。然後 Simulator 會緩存這次模擬的所有算法組合的結果所以可能會如下:

"""
Simulator 物件 result pool 結果保存:
第一組算法組合: [第一題第一次模擬、第一題第二次模擬, ... 第三十題第二十次模擬]
第二組算法組合: [第一題第一次模擬、第一題第二次模擬, ... 第三十題第二十次模擬]
第三組算法組合: [第一題第一次模擬、第一題第二次模擬, ... 第三十題第二十次模擬]
"""

簡單一點說就是 Simulator 現在就是負責調度 Machine 求解以及保存結果的控制台，會對Machine 做執行上的排呈，MAchine 中又各自對自己的任務做排呈。

現在有個問題，就是 Simulator 層級怎麼知道現在的執行進度? 因為現在實際執行是在 Machine 中被處理，每個 Machine 又被分開處理。

現在依然需要保持同一個 base seed 同題庫同題目同 repeat 在任意算法組合下 run seed 都要是一樣的。確保實驗的功能性與重現性。

Machine 模組需要放到一個獨立的 machine 資料夾中，成為一個工作分明，文件結構清晰的獨立模組。


[問題4] cil.run 算法數量支援保持 一個題庫、一個 solver、多組算法設定串行或是併發模擬、只是底層系統需要支援單一題庫、多 solver、多參數設定 串行或併發模擬。
[目標] 上面改好之後，重新檢視 cil.run 的執行在流程上是否確保受到限制(一個題庫、一個 solver、多組算法設定串行或是併發模擬)
[方案] 用 cil.run 模組的 cil 參數合法性驗證去擋。

[問題5] 根據目前修改的結果評估是否有能力可以提取 同一個題庫同一個題目同一次 repeat 下當前所有 solver 的所有 參數組合的求解結果
[目標] 我需要知道某一題相同 run seed 下範圍內的所有算法參數組合的表現 
[方案] 先根據 問題3、問題4 修改方案評估如果這樣修改，那在 cil.exp 模組重構之後有沒有辦法拿到這樣的資料。如果不行或是會增加複雜度可能上面得方案要修改要修改。


[問題6] 結果緩存、統計方式、輸出格式 
[目標] 根據前面提到
[方案]
1. 目前統計方式改成新增一筆資料就更新一次統計結果而不是全部跑完才一起更新
2. 串行模擬統計方式變成每執行完一題模擬則呼叫 Record 函數用於更新統計狀態。
3. 併發模擬的統計方式保持模擬完成之後再一次處理模擬，但因為統計模組需要改成 input 是吃一筆新增的資料然後更新統計值的方式，所以可能也會有相對應的改變。這個需要重新檢查或評估。


[問題7] cil.exp 收集 seed。
[目標] cil.exp 可以透過所有算法組合不斷 repeat 找到符合預期的 結果(比如說 bsma 適應值 >= bsca 等) 逐題收集所需要的 seed 數量，比如說 20 個符合條件的 seed  
[方案] 更新 exp_cfg.yaml 格式、更新 expriment 處理流程。目前大概的想法是所有的算法會根據設定的 題庫/題目設定去逐題收集符合預期的 seed ，收集滿了才執行下一題，如果超過 repeat 上限則終止 cil.exp 的運行並返回錯誤原因 

cil.run 流程不能動，前面修改好的東西也不能動，在解決這個問題的時候只能動 cil.exp 和 expriment 模組。

[問題8] cil.exp 的 `_register_configured_evaluators(experiment)` 不應該這邊定義一個註冊函數，我記得 experiment 模組有一個註冊評估函數的公共 api 應要用那個來註冊評估函數。我記得叫做 register() 的樣子，你看一下目前 experiment 有沒有需要根據目前最新需求做更新的地方。因為目前 experiment 模組的架構可能會有點過時。

評估函數不要有內建預設的評估函數，也不要在 main.py 自己定義一個 維護清單，維護清單應該要在 experiment 中維護不應該給外部人員自己維護。外部人員(cil.exp) 只能呼叫模組的公共 api (register 函數) 把 cil.exp 外部人員自定義的評估函數註冊到系統當中。

然後 exp_cfg.yaml 會透過設定指名每一個題庫要用哪一個評估函數進行評估。實際使用情境上不一定每一個題庫中的每一個題目是否要通過 collect 的標準都是一樣的。

如果設定檔上的 評估函數沒有被註冊就是錯誤。

基本上 cil.exp 模組中，就是只做設定、執行、還有利用experiment 公開 API 做事情(例如註冊評估函數) 其他的事情應該要放在 experiment 模組中處理，放在experiment 模組中的邏輯是系統開發人員不希望外部使用人員隨意動到的東西。所以你要檢視一下目前 cil.exp 有沒有這類的 code。

[問題9] exp_cfg.yaml 的格式需要做一點微調。

1. 移除 `worker` 系統統一預設 10 就好。
2. 算法沒辦法設定要使用哪幾組算法參數組合做實驗，這個問題我站時還沒想到解決方案，目前粗步構想是 solver 值改成用 yaml 清單，大概如下:
    ```yaml

    # 要執行的演算法，以及算法參數索引值
    solvers: 
    - solver: bsma_numba 
        param_idx: 0
    - solver: bsca_numba 
        param_idx: 0
    - solver: brlsmasca_numba 
        param_idx: 0
    ```
3. base_line 的定義方式也要重新修改，不應該是題庫的統計值應該要是題目的競爭算法的統計值(PDev) 每一題一個統計值。 base line 可以 1 組也可以多組也可以沒有

```yaml
    problems: 
      - problems: weish01 
        evaluation: [mkp_base, mkp_base2]
        base_line: 
          - name: HLMS
            Pdev: 0.154
          - name: BIWOA
            Pdev: 0.472
          - name: BMMVO
            Pdev: 0.861
          - name: BSCA
            Pdev: 0.314
          - name: IBSMA_U1
            Pdev: 0.105 
```

4. evaluation 是一個清單，它可以是一個也可以是多個。
 
我已經把我構想的新構想的格式寫在 exp_cfg.yaml 做為範例了。 然後 base line 的數據你可以根據 note/apx.md 做參考設定出每一個 競爭算法每一題 合理的 Pdev 出來。

[問題10] 目前 cil.exp 的 mkp.py 評估方式有點過時，重寫評估邏輯。然後把 literature_mkp.py 移除這東西是多餘的。

[方案] 寫一個評估函數對應 `exp_cfg.yaml` 中的 mkp_base、mkp_base2 這個評估的邏輯

1. mkp_base 對應的評估函數是目前實驗的算法組合表現都要比 base line 好。
2. mkp_base2 對應的評估函數是 brlsmasca_numba 算法組合的表現要是最好的。

評估函數在評估 Pdev 的時候要算 PDev，就是如果這次 repeat 模擬的結果加進 collect 清單中結果是符合條件的，那就就加入，反之就放棄這次 repeat 的結果。

把這兩個評估函數分別寫在 mkp_base.py、mkp_base2.py 中。

有符合條件的 seed 會先保存在結果物件中，到最後才會一次性輸出到文件中。然後符合條件的模擬結果也應該要像 cil.run 輸出模擬結果的格式一樣輸出符合預期的執行結果。

[問題11] 在終端機要顯示目前預計要收那些題目預計收多少筆已經收多少筆，總共要收多少筆。以下給範例以目前 exp_cfg.yaml 只有 Weish01~11 的情況下，終端機在每一次 repeat 模擬完成之後評估一次，評估完一次會更新狀態，更新後就會打印在終端機會更新目前收集的結果

一開始狀態
```
step1: collect
[Weish] weish01: 0/20 weish02: 0/20 weish03: 0/20 weish04: 0/20 weish05: 0/20 weish06: 0/20 weish07: 0/20 weish08: 0/20 weish09: 0/20 weish10: 0/20 weish11: 0/20 | remaining: 220
```

然後收集了一段時間後可能會當前狀態會變成

```
step1: collect
[Weish] weish01: 20/20 weish02: 5/20 weish03: 0/20 weish04: 0/20 weish05: 0/20 weish06: 0/20 weish07: 0/20 weish08: 0/20 weish09: 0/20 weish10: 0/20 weish11: 0/20 | remaining: 195
```

如果設定上是多題庫(Weish、GK) 會把每一個題庫要收集的數量以及當前狀態打印出來

```
step1: collect
[Weish] weish01: 20/20 weish02: 5/20 weish03: 0/20 weish04: 0/20 weish05: 0/20 weish06: 0/20 weish07: 0/20 weish08: 0/20 weish09: 0/20 weish10: 0/20 weish11: 0/20
[GK] gk_01: 0/20 gk_02: 0/20 | remaining: 235

```

[問題12] cil.run 要可以支援定義直接給 run seed 陣列然後執行模擬。

[問題13] 測試 GK 題庫跑看看樹拒絕果是否合理