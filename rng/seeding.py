from __future__ import annotations

import hashlib
import json

import numpy as np


TASK_SEED_VERSION = "mkp.task-seed.v2"


def validate_base_seed(base_seed: int) -> int:
    base_seed = int(base_seed)
    if base_seed < 0:
        raise ValueError("base_seed must be >= 0.")
    return base_seed


def stable_task_seed(
    *,
    base_seed: int,
    problem_type: str,
    dataset: str,
    problem_id: str,
    repeat_index: int,
) -> int:
    payload = {
        "version": TASK_SEED_VERSION,
        "base_seed": int(base_seed),
        "problem_type": problem_type,
        "dataset": dataset,
        "problem_id": problem_id,
        "repeat_index": int(repeat_index),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.blake2b(raw, digest_size=8).digest()
    return int.from_bytes(digest, byteorder="little", signed=False) % int(np.iinfo(np.int32).max)
