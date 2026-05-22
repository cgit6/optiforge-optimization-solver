from __future__ import annotations

from typing import Callable

import numpy as np


RngFactory = Callable[[int], np.random.Generator]


def make_numpy_rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)
