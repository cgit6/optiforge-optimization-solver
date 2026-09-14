"""核心層提供可與 Numba 整合的 PCG32 亂數工具。

此模組自行實作 PCG32（XSH RR）產生器，並將狀態儲存在長度 2 的
``np.ndarray``（``uint64``）中，讓 Numba `@njit` 函式可以直接操作。
高層物件（例如 ``Machine``）只需要保留這個狀態陣列，就能在熱路徑
裡呼叫以下 functions 取得亂數，而不必把 Python 物件帶進 JIT。
"""

from __future__ import annotations

import sys
import time

import numpy as np
from numba import njit


sys.modules.setdefault('core.core', sys.modules[__name__])

__all__ = [
    "PCG32State",
    "pcg32_seed",
    "pcg32_step",
    "pcg32_random_float64",
    "pcg32_random_uint32",
    "pcg32_randbelow",
    "pcg32_random_integers",
    "pcg32_random_floats",
]

PCG32_MULTIPLIER = np.uint64(6364136223846793005)
PCG32_FLOAT_UNIT = np.float64(1.0 / 2.0**32)

PCG32State = np.ndarray


def pcg32_seed(seed: int | None = None, seq: int = 1) -> PCG32State:
    """建立 PCG32 狀態陣列。

    ``seed`` 與 ``seq`` 分別對應 PCG 原始演算法的初始 state 與
    stream selector。回傳值為 ``np.ndarray([state, increment], uint64)``，
    可直接傳入 :func:`pcg32_step` 等 JIT 函式。
    """

    actual_seed = time.time_ns() if seed is None else seed

    state = np.zeros(2, dtype=np.uint64)
    state[1] = (np.uint64(seq) << np.uint64(1)) | np.uint64(1)
    pcg32_step(state)
    state[0] = np.uint64(state[0] + np.uint64(actual_seed))
    pcg32_step(state)
    return state


@njit(cache=True)
def pcg32_step(state: PCG32State) -> np.uint32:
    """產出下一個 ``uint32``，並就地更新 ``state``。"""

    oldstate = state[0]
    state[0] = oldstate * PCG32_MULTIPLIER + state[1]
    xorshifted = np.uint32(((oldstate >> np.uint64(18)) ^ oldstate) >> np.uint64(27))
    rot = int(oldstate >> np.uint64(59))
    return np.uint32((xorshifted >> rot) | (xorshifted << ((-rot) & 31)))


@njit(cache=True)
def pcg32_random_uint32(state: PCG32State) -> np.uint32:
    """取得 ``uint32`` 亂數。"""

    return pcg32_step(state)


@njit(cache=True)
def pcg32_random_float64(state: PCG32State) -> np.float64:
    """回傳 ``[0, 1)`` 區間的 ``float64``。"""

    return np.float64(pcg32_step(state) * PCG32_FLOAT_UNIT)


@njit(cache=True)
def pcg32_randbelow(state: PCG32State, bound: int) -> np.uint32:
    """回傳 ``[0, bound)`` 之間的整數。"""

    if bound <= 0:
        raise ValueError("bound must be positive")
    if bound > 2**32:
        raise ValueError("bound must be <= 2**32 for pcg32_randbelow")
    b = np.uint32(bound)
    threshold = np.uint32((np.uint32(0) - b) % b)
    while True:
        r = pcg32_step(state)
        if r >= threshold:
            return np.uint32(r % b)


@njit(cache=True)
def pcg32_random_integers(state: PCG32State, low: int, high: int) -> np.int64:
    """回傳 ``[low, high)`` 的整數值。"""

    if high <= low:
        raise ValueError("high must be greater than low")
    span = high - low
    return np.int64(low + int(pcg32_randbelow(state, span)))


@njit(cache=True)
def pcg32_random_floats(state: PCG32State, size: int) -> np.ndarray:
    """產生 ``size`` 個 ``float64`` 亂數並回傳新陣列。"""

    out = np.empty(size, dtype=np.float64)
    for idx in range(size):
        out[idx] = pcg32_random_float64(state)
    return out


if __name__ == "__main__":
    '''使用方法範例與效能測試'''
    import time

    rounds = 10_000_000_000
    state = pcg32_seed(41274863084)

    @njit(cache=True)
    def consume_uint32(rng_state: PCG32State, count: int) -> None:
        for _ in range(count):
            pcg32_randbelow(rng_state, 100)

    consume_uint32(state.copy(), 1)  # warm-up

    start = time.perf_counter()
    consume_uint32(state, rounds)
    elapsed = time.perf_counter() - start
    rate = rounds / elapsed
    print(
        f"{rounds:,} uint32 in {elapsed:.6f}s -> "
        f"{rate/1_000_000:.2f}M/s ({1e9/rate:.2f} ns/value)"
    )
