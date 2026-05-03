"""連續基因值 → 與 Uniform(0,1) 比較用之標量（CTF：continuous-to-flip）。

對齊實驗用轉換（參 old/transform.py 註解）。``tanh_signed`` 回傳未取絕對值之 tanh，
與均匀比較時負值永遠不觸發「壓成 1」分枝。幂次類對負連續值採 ``abs(x)**p``，
避免非整數幂在負底數上產生 NaN。

索引順序須與 ``mkp.tools.ctf_numba.ctf_flip_probability`` 內 ``ctf_id`` 分支一致。
"""

from __future__ import annotations

import math
from typing import Any

# 順序固定：與 tools/ctf_numba.py 中 ctf_id 一一對應
CTF_KINDS: tuple[str, ...] = (
    "tanh_abs",
    "sigmoid_s0",
    "sigmoid_s1",
    "sigmoid_s2",
    "sigmoid_s3",
    "atan_scaled",
    "tanh_signed",
    "inv_sqrt_one_plus_x2",
    "erf_scaled",
    "abs_pow_16",
    "abs_pow_17",
    "abs_pow_2",
)

CTF_ID_BY_NAME: dict[str, int] = {name: i for i, name in enumerate(CTF_KINDS)}


def _logistic(k: float, x: float) -> float:
    """數值較穩之 1/(1+exp(-k*x))。"""
    t = k * x
    if t >= 0.0:
        return 1.0 / (1.0 + math.exp(-t))
    et = math.exp(t)
    return et / (1.0 + et)


def _tanh_abs(x: float) -> float:
    return abs(math.tanh(x))


def _sigmoid_s0(x: float) -> float:
    return _logistic(1.0, x)


def _sigmoid_s1(x: float) -> float:
    return _logistic(2.0, x)


def _sigmoid_s2(x: float) -> float:
    return _logistic(0.5, x)


def _sigmoid_s3(x: float) -> float:
    return _logistic(1.0 / 3.0, x)


def _atan_scaled(x: float) -> float:
    return (2.0 / math.pi) * math.atan((math.pi / 2.0) * x)


def _tanh_signed(x: float) -> float:
    return math.tanh(x)


def _inv_sqrt_one_plus_x2(x: float) -> float:
    return 1.0 / math.sqrt(1.0 + x * x)


def _erf_scaled(x: float) -> float:
    return math.erf((math.pi / 2.0) * x)


def _abs_pow_16(x: float) -> float:
    ax = abs(x)
    return ax**1.6


def _abs_pow_17(x: float) -> float:
    ax = abs(x)
    return ax**1.7


def _abs_pow_2(x: float) -> float:
    ax = abs(x)
    return ax * ax


_HANDLERS: dict[str, Any] = {
    "tanh_abs": _tanh_abs,
    "sigmoid_s0": _sigmoid_s0,
    "sigmoid_s1": _sigmoid_s1,
    "sigmoid_s2": _sigmoid_s2,
    "sigmoid_s3": _sigmoid_s3,
    "atan_scaled": _atan_scaled,
    "tanh_signed": _tanh_signed,
    "inv_sqrt_one_plus_x2": _inv_sqrt_one_plus_x2,
    "erf_scaled": _erf_scaled,
    "abs_pow_16": _abs_pow_16,
    "abs_pow_17": _abs_pow_17,
    "abs_pow_2": _abs_pow_2,
}


def flip_probability(x: float, kind: str) -> float:
    fn = _HANDLERS.get(kind)
    if fn is None:
        legal = ", ".join(CTF_KINDS)
        raise KeyError(f"Unknown ctf kind {kind!r}; expected one of: {legal}")
    return float(fn(float(x)))


def parse_ctf_kind(params: dict[str, Any], *, key: str = "ctf") -> tuple[str, int]:
    """自 solver ``params`` 讀取 CTF；缺省為 ``tanh_abs``。"""
    raw = params.get(key)
    if raw is None:
        return ("tanh_abs", 0)
    s = str(raw).strip()
    if not s:
        raise ValueError(f"{key} must be a non-empty string when provided")
    i = CTF_ID_BY_NAME.get(s)
    if i is None:
        legal = ", ".join(CTF_KINDS)
        raise ValueError(f"Unknown {key}={raw!r}; expected one of: {legal}")
    return (CTF_KINDS[i], i)
