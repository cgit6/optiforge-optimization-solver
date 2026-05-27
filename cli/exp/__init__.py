"""Experiment CLI entrypoint and bundled evaluators."""

from __future__ import annotations

from .main import main
from .mkp_base import mkp_base_evaluator, mkp_bsca_base_margin_2_evaluator
from .mkp_base2 import mkp_base2_evaluator, mkp_base2_margin_005_evaluator
from .mkp_calibration import (
    mkp_calibration_evaluator,
    mkp_target_combo_brlsmasca_margin_004_evaluator,
    mkp_target_combo_bsma_strict_evaluator,
    mkp_target_combo_bsca_margin_005_evaluator,
    mkp_target_combo_best_evaluator,
    mkp_target_combo_core_strict_evaluator,
    mkp_transfer_bsca_margin_005_evaluator,
    mkp_transfer_core_strict_evaluator,
    mkp_transfer_paired_strict_evaluator,
)
from .mkp_random_collect import mkp_random_collect_every_n_5_20_evaluator

__all__ = [
    "main",
    "mkp_base_evaluator",
    "mkp_bsca_base_margin_2_evaluator",
    "mkp_base2_evaluator",
    "mkp_base2_margin_005_evaluator",
    "mkp_calibration_evaluator",
    "mkp_target_combo_brlsmasca_margin_004_evaluator",
    "mkp_target_combo_bsma_strict_evaluator",
    "mkp_target_combo_bsca_margin_005_evaluator",
    "mkp_target_combo_best_evaluator",
    "mkp_target_combo_core_strict_evaluator",
    "mkp_transfer_bsca_margin_005_evaluator",
    "mkp_transfer_core_strict_evaluator",
    "mkp_transfer_paired_strict_evaluator",
    "mkp_random_collect_every_n_5_20_evaluator",
]
