# Config Inventory

## Solver Configs

| Solver ID | Class | Param Sets | Capabilities | Path |
|---|---|---:|---|---|
| `brlsmasca` | `BRLSMASCATestSolver` | 1 | problem_types=['mkp'], encodings=['binary'], directions=['max'] | `configs/solvers/brlsmasca.yaml` |
| `brlsmasca_rl_numba` | `BRLSMASCARLNumbaSolver` | 27 | problem_types=['mkp'], encodings=['binary'], directions=['max'] | `configs/solvers/brlsmasca_rl_numba.yaml` |
| `brlsmasca_rl_rc_numba` | `BRLSMASCARLRCNumbaSolver` | 27 | problem_types=['mkp'], encodings=['binary'], directions=['max'] | `configs/solvers/brlsmasca_rl_rc_numba.yaml` |
| `brlsmasca_test_numba` | `BRLSMASCATestNumbaSolver` | 9 | problem_types=['mkp'], encodings=['binary'], directions=['max'] | `configs/solvers/brlsmasca_test_numba.yaml` |
| `bsca` | `BSCASolver` | 1 | problem_types=['mkp'], encodings=['binary'], directions=['max'] | `configs/solvers/bsca.yaml` |
| `bsca_numba` | `BSCANumbaSolver` | 9 | problem_types=['mkp'], encodings=['binary'], directions=['max'] | `configs/solvers/bsca_numba.yaml` |
| `bsca_rc_numba` | `BSCARCNumbaSolver` | 9 | problem_types=['mkp'], encodings=['binary'], directions=['max'] | `configs/solvers/bsca_rc_numba.yaml` |
| `bsma` | `BSMASolver` | 3 | problem_types=['mkp'], encodings=['binary'], directions=['max'] | `configs/solvers/bsma.yaml` |
| `bsma_numba` | `BSMANumbaSolver` | 9 | problem_types=['mkp'], encodings=['binary'], directions=['max'] | `configs/solvers/bsma_numba.yaml` |
| `bsma_rc_numba` | `BSMARCNumbaSolver` | 9 | problem_types=['mkp'], encodings=['binary'], directions=['max'] | `configs/solvers/bsma_rc_numba.yaml` |

## Problem YAML Counts

| Problem Type | Dataset | YAML Count |
|---|---|---:|
| `mkp` | `GK` | 11 |
| `mkp` | `HP` | 2 |
| `mkp` | `OR10x100` | 30 |
| `mkp` | `OR10x250` | 30 |
| `mkp` | `OR10x500` | 30 |
| `mkp` | `OR30x100` | 30 |
| `mkp` | `OR30x250` | 30 |
| `mkp` | `OR30x500` | 30 |
| `mkp` | `OR5x100` | 30 |
| `mkp` | `OR5x250` | 30 |
| `mkp` | `OR5x500` | 30 |
| `mkp` | `PB` | 6 |
| `mkp` | `PET` | 6 |
| `mkp` | `SENT` | 2 |
| `mkp` | `WEING` | 8 |
| `mkp` | `WEISH` | 30 |
| `mkp` | `tsp` | 2 |

## Active Experiment Config

- Path: `cli/exp/exp_cfg.yaml`
- Top-level keys: `experiment_name, collects, repeat, solvers, dataset_settings`
- experiment_name: `mkp_cb_qpso_rc`
- solvers count: `1`
- dataset_settings count: `2`
