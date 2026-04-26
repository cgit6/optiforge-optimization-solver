

## 執行

```cmd
cd /home/sean/mkp && .venv/bin/python -m mkp.cli.run \
  --experiment-id demo_seed \
  --dataset WEISH \
  --problems weish30 \
  --solver bsma_v1_008 \
  --repeat 20 \
  --base-seed 42 \
  --output-dir mkp/output \
  --execution-mode worker_curriculum
```