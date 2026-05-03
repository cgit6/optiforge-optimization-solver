from __future__ import annotations

import math

import numpy as np
import pytest

from mkp.tools.continuous_to_binary import (
    CTF_KINDS,
    flip_probability,
    parse_ctf_kind,
)
from mkp.tools.ctf_numba import ctf_flip_probability


def test_parse_ctf_default() -> None:
    k, i = parse_ctf_kind({})
    assert k == "tanh_abs" and i == 0


def test_parse_ctf_explicit() -> None:
    k, i = parse_ctf_kind({"ctf": "sigmoid_s2"})
    assert k == "sigmoid_s2" and i == CTF_KINDS.index("sigmoid_s2")


def test_parse_unknown_raises() -> None:
    with pytest.raises(ValueError, match="Unknown"):
        parse_ctf_kind({"ctf": "not_a_kind"})


@pytest.mark.parametrize("ctf_id", range(len(CTF_KINDS)))
def test_flip_matches_numba(ctf_id: int) -> None:
    """Python flip_probability 與 Numba ctf_flip_probability 數值對齊。"""
    xs = [-5.0, -1.25, -0.5, 0.0, 0.3, 2.5, 8.0]
    kind = CTF_KINDS[ctf_id]
    for x in xs:
        py = flip_probability(float(x), kind)
        nb = float(ctf_flip_probability(ctf_id, float(x)))
        assert math.isfinite(py) and math.isfinite(nb), (kind, x)
        np.testing.assert_allclose(py, nb, rtol=1e-14, atol=1e-14)
