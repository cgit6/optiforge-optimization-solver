

## 執行


```cmd
cd /home/sean/mkp && .venv/bin/python -m mkp.cli.run \
  --experiment-name demo_seed \
  --type mkp \
  --dataset WEISH \
  --problems weish30 \
  --solver bsma \
  --set 1 \
  --repeat 20 \  
  --seed 42 \
  --worker 4
```

重現模擬結果
```
python -m mkp.cli.replay \
  --seed-bank output/<experiment_name>/seed_bank.json \
  --solver bsma_numba \
  --set 1
```