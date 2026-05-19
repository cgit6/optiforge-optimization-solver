from __future__ import annotations

from pathlib import Path

from mkp.solver.BSCASMA_numba import _policy_mode_settings
from mkp.tools.solver_config_loader import SolverConfigLoader


def test_literature_solver_presets_match_expected_variant_grid() -> None:
    loader = SolverConfigLoader(config_root=Path("configs/solvers"))

    bsma_transfer = loader.load_all("bsma_numba_transfer_literature")
    bsca_transfer = loader.load_all("bsca_numba_transfer_literature")
    brlsmasca_transfer = loader.load_all("brlsmasca_numba_transfer_literature")
    random50_transfer = loader.load_all("brlsmasca_numba_random50_transfer_literature")
    bsma = loader.load_all("bsma_numba_literature")
    bsca = loader.load_all("bsca_numba_literature")
    brlsmasca = loader.load_all("brlsmasca_numba_literature")
    random50 = loader.load_all("brlsmasca_numba_random50_literature")

    assert len(bsma_transfer) == 3
    assert len(bsca_transfer) == 3
    assert len(brlsmasca_transfer) == 3
    assert len(random50_transfer) == 3
    assert len(bsma) == 3
    assert len(bsca) == 3
    assert len(brlsmasca) == 9
    assert len(random50) == 1
    assert all(
        cfg["stop_condition"]["max_iterations"] == 5000
        for cfg in (
            *bsma_transfer,
            *bsca_transfer,
            *brlsmasca_transfer,
            *random50_transfer,
            *bsma,
            *bsca,
            *brlsmasca,
            *random50,
        )
    )

    assert [cfg["params"]["ctf"] for cfg in bsma_transfer] == ["sigmoid_s0", "abs_pow_17", "tanh_abs"]
    assert [cfg["params"]["ctf"] for cfg in bsca_transfer] == ["sigmoid_s0", "abs_pow_17", "tanh_abs"]
    assert all(cfg["params"]["policy_mode"] == "rl_best_method" for cfg in brlsmasca_transfer)
    assert all(cfg["params"]["policy_mode"] == "random_family_50_50" for cfg in random50_transfer)
    assert [cfg["params"]["z"] for cfg in bsma] == [0.01, 0.08, 0.15]
    assert [cfg["params"]["a"] for cfg in bsca] == [1.5, 2.0, 2.5]
    assert (bsma[1]["param_set_index"], bsma[1]["params"]["z"]) == (1, 0.08)
    assert (bsca[0]["param_set_index"], bsca[0]["params"]["a"]) == (0, 1.5)
    assert (
        brlsmasca[5]["param_set_index"],
        brlsmasca[5]["params"]["z"],
        brlsmasca[5]["params"]["a"],
    ) == (5, 0.08, 2.5)
    assert random50[0]["params"]["policy_mode"] == "random_family_50_50"


def test_policy_mode_settings_normalize_random50_family_probabilities() -> None:
    mode_id, sma_global_ratio, sca_sin_ratio = _policy_mode_settings(
        "random_family_50_50",
        (0.04, 0.46, 0.25, 0.25),
    )

    assert mode_id == 1
    assert sma_global_ratio == 0.08
    assert sca_sin_ratio == 0.5
