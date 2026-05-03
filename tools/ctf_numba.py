"""與 continuous_to_binary 對應之 nopython scalar CTF（供 Numba 主迴圈內整數分流）。"""

from __future__ import annotations

import math

from numba import njit


@njit(cache=True)
def ctf_flip_probability(ctf_id: int, x: float) -> float:
    """回傳值與 ``mkp.tools.continuous_to_binary.flip_probability`` 對相同 ``ctf_id`` 一致。"""
    if ctf_id == 0:
        return abs(math.tanh(x))
    if ctf_id == 1:
        t = x
        if t >= 0.0:
            return 1.0 / (1.0 + math.exp(-t))
        et = math.exp(t)
        return et / (1.0 + et)
    if ctf_id == 2:
        t = 2.0 * x
        if t >= 0.0:
            return 1.0 / (1.0 + math.exp(-t))
        et = math.exp(t)
        return et / (1.0 + et)
    if ctf_id == 3:
        t = 0.5 * x
        if t >= 0.0:
            return 1.0 / (1.0 + math.exp(-t))
        et = math.exp(t)
        return et / (1.0 + et)
    if ctf_id == 4:
        t = x / 3.0
        if t >= 0.0:
            return 1.0 / (1.0 + math.exp(-t))
        et = math.exp(t)
        return et / (1.0 + et)
    if ctf_id == 5:
        return (2.0 / math.pi) * math.atan((math.pi / 2.0) * x)
    if ctf_id == 6:
        return math.tanh(x)
    if ctf_id == 7:
        return 1.0 / math.sqrt(1.0 + x * x)
    if ctf_id == 8:
        return math.erf((math.pi / 2.0) * x)
    if ctf_id == 9:
        ax = abs(x)
        return ax**1.6
    if ctf_id == 10:
        ax = abs(x)
        return ax**1.7
    if ctf_id == 11:
        ax = abs(x)
        return ax * ax
    # 無效 id：與 Python 側 KeyError 對應之行為於編譯期已過濾，此處回退
    return abs(math.tanh(x))
