"""全題庫 + 10 萬次適應值上界；請用 pytest -m slow 執行。"""

from __future__ import annotations

from pathlib import Path

import pytest

from mkp.valid.bsma_equivalence_batch import run_weish_equivalence_suite


@pytest.mark.slow
def test_weish01_through_30_streaming_equivalence_100k_budget():
    repo_root = Path(__file__).resolve().parents[1]
    out = repo_root / "output/bsma_weish_suite_slow_pytest"
    summary = run_weish_equivalence_suite(
        repo_root=repo_root,
        seed=101,
        budget=100_000,
        output_dir=out,
        ensure_yaml=True,
    )
    assert summary["all_pass"] is True
