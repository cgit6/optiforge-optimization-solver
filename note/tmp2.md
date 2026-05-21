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

[問題2] seed 問題
