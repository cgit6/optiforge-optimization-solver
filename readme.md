
# Optiforge Optimization Solver

Optiforge is a Python experimentation framework for combinatorial optimization. The current public scope centers on the multidimensional knapsack problem (MKP), binary metaheuristics, reproducible seed handling, and comparable structured results.

The repository is research and portfolio software. It is not presented as a production optimization service or as a general replacement for mathematical-programming solvers.

## What is included

- A `Problem`／`Solver` contract and registries for assembling compatible experiments.
- SMA, SCA, hybrid, reinforcement-learning, reduced-cost, and Numba-enabled solver variants.
- YAML problem and solver configuration with pre-run capability validation.
- Sequential and multiprocessing execution, shared-memory problem data, deterministic seeds, and seed-bank replay.
- Structured run results covering objective value, feasibility, evaluation count, runtime, stop reason, and errors.
- A pytest suite for contracts, validation, execution, replay, and solver behavior.

The installed distribution is currently named `mkp`, so commands and imports use that package name.

## Requirements

- Python 3.11 or newer
- Linux, macOS, or another environment able to install NumPy and SciPy

## Install

Create and activate a virtual environment, then install the project with the optional Numba solvers and test dependencies:

```bash
python -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[numba]' pytest
```

## Run a smoke experiment

Run one repeat of the bundled `weish01` problem with the first BSMA parameter set:

```bash
.venv/bin/python -m mkp.cli.run \
  --experiment-name smoke \
  --type mkp \
  --dataset WEISH \
  --problems weish01 \
  --solver bsma \
  --set 0 \
  --repeat 1 \
  --seed 42 \
  --worker 1
```

Results are written below `output/smoke/`. Use a different experiment name to avoid mixing runs.

## Replay saved seeds

After an experiment has produced a seed bank, replay it with another compatible solver:

```bash
.venv/bin/python -m mkp.cli.replay \
  --seed-bank output/<experiment-name>/seed_bank.json \
  --solver bsma_numba \
  --set 0
```

## Test

```bash
.venv/bin/python -m pytest -q
```

CI performs an editable installation with the Numba extra and runs the complete suite on Python 3.11 and 3.12.

## Repository map

- `problem/`: problem models, loaders, registries, and validation.
- `solver/`: solver implementations and registry.
- `engine/`, `machine/`, `simulator/`: experiment assembly and execution.
- `experiment/`: experiment configuration, evaluation, and seed-bank support.
- `cli/`: single-run, experiment, conversion, and replay entry points.
- `configs/`: bundled problem instances and solver parameter sets.
- `tests/`: automated tests.

## Reproducibility notes

Comparisons should use the same problem set, stopping rule, seed bank, hardware context, and parameter-selection procedure. Runtime and objective figures from exploratory notebooks are not release benchmarks unless a versioned report states those conditions explicitly.

## License

No open-source license has been selected yet. The code is publicly viewable, but reuse permission is not granted until a license is added.
