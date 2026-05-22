from __future__ import annotations

import numpy as np
import pytest

from mkp.rng import (
    DerivedPerProblemSeedStrategy,
    SeedContext,
    SharedRepeatSeedListStrategy,
    make_numpy_rng,
)
from mkp.rng.seeding import stable_task_seed, validate_base_seed


def test_validate_base_seed_rejects_negative_values() -> None:
    with pytest.raises(ValueError, match="base_seed must be >= 0."):
        validate_base_seed(-1)


def test_stable_task_seed_matches_existing_regression_values() -> None:
    assert stable_task_seed(
        base_seed=123456,
        problem_type="mkp",
        dataset="WEISH",
        problem_id="weish01",
        repeat_index=0,
    ) == 514477028
    assert stable_task_seed(
        base_seed=123456,
        problem_type="mkp",
        dataset="WEISH",
        problem_id="weish02",
        repeat_index=0,
    ) == 686853799
    assert stable_task_seed(
        base_seed=123456,
        problem_type="mkp",
        dataset="WEISH",
        problem_id="weish03",
        repeat_index=0,
    ) == 1277264314


def test_seed_strategy_builds_expected_task_seed_mapping() -> None:
    strategy = DerivedPerProblemSeedStrategy()
    context = SeedContext(
        problem_type="mkp",
        dataset="WEISH",
        problem_ids=("weish01", "weish02"),
        repeat=2,
    )

    assert strategy.build_task_seeds(context, base_seed=999) == {
        ("weish01", 0): stable_task_seed(
            base_seed=999,
            problem_type="mkp",
            dataset="WEISH",
            problem_id="weish01",
            repeat_index=0,
        ),
        ("weish01", 1): stable_task_seed(
            base_seed=999,
            problem_type="mkp",
            dataset="WEISH",
            problem_id="weish01",
            repeat_index=1,
        ),
        ("weish02", 0): stable_task_seed(
            base_seed=999,
            problem_type="mkp",
            dataset="WEISH",
            problem_id="weish02",
            repeat_index=0,
        ),
        ("weish02", 1): stable_task_seed(
            base_seed=999,
            problem_type="mkp",
            dataset="WEISH",
            problem_id="weish02",
            repeat_index=1,
        ),
    }


def test_make_numpy_rng_returns_reproducible_generator() -> None:
    rng_a = make_numpy_rng(777)
    rng_b = make_numpy_rng(777)

    assert isinstance(rng_a, np.random.Generator)
    assert int(rng_a.integers(0, 10_000)) == int(rng_b.integers(0, 10_000))


def test_shared_repeat_seed_list_strategy_reuses_same_seed_list_for_each_problem() -> None:
    strategy = SharedRepeatSeedListStrategy(seeds=(1001, 1002, 1003))
    context = SeedContext(
        problem_type="mkp",
        dataset="WEISH",
        problem_ids=("weish01", "weish02"),
        repeat=3,
    )

    assert strategy.build_task_seeds(context, base_seed=999) == {
        ("weish01", 0): 1001,
        ("weish01", 1): 1002,
        ("weish01", 2): 1003,
        ("weish02", 0): 1001,
        ("weish02", 1): 1002,
        ("weish02", 2): 1003,
    }


def test_shared_repeat_seed_list_strategy_requires_repeat_length_match() -> None:
    strategy = SharedRepeatSeedListStrategy(seeds=(1001, 1002))
    context = SeedContext(
        problem_type="mkp",
        dataset="WEISH",
        problem_ids=("weish01",),
        repeat=3,
    )

    with pytest.raises(ValueError, match="length must equal context.repeat"):
        strategy.build_task_seeds(context, base_seed=1)
