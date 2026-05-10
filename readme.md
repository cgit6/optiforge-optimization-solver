

## 執行

```cmd
cd /home/sean/mkp && .venv/bin/python -m mkp.cli.run \
  --experiment-name demo_seed \
  --type mkp \
  --dataset WEISH \
  --problems weish30 \
  --solver bsma \
  --repeat 20 \
  --seed 42 \
  --worker 4
```
