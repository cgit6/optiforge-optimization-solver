from __future__ import annotations

import hashlib

from ...experiment import FAIL, PASS, RoundEvalDecision, RoundEvalInput

MIN_REPEAT_INTERVAL = 5
MAX_REPEAT_INTERVAL = 20


def mkp_random_collect_every_n_5_20_evaluator(input_data: RoundEvalInput) -> RoundEvalDecision:
    interval = _problem_interval(
        dataset=input_data.dataset_setting.dataset,
        problem_id=input_data.problem_id,
    )
    block_index = input_data.repeat_index // interval
    selected_offset = _selected_block_offset(
        dataset=input_data.dataset_setting.dataset,
        problem_id=input_data.problem_id,
        interval=interval,
        block_index=block_index,
    )
    current_offset = input_data.repeat_index % interval
    passed = current_offset == selected_offset
    details = {
        "min_interval": MIN_REPEAT_INTERVAL,
        "max_interval": MAX_REPEAT_INTERVAL,
        "interval": interval,
        "block_index": block_index,
        "selected_offset": selected_offset,
        "current_offset": current_offset,
        "repeat_index": input_data.repeat_index,
        "selected_repeat_index": block_index * interval + selected_offset,
    }
    return RoundEvalDecision(
        passed=passed,
        verdict=PASS if passed else FAIL,
        message=(
            "Repeat accepted by deterministic random collection interval."
            if passed
            else "Repeat rejected by deterministic random collection interval."
        ),
        details=details,
    )


def _problem_interval(*, dataset: str, problem_id: str) -> int:
    span = MAX_REPEAT_INTERVAL - MIN_REPEAT_INTERVAL + 1
    return MIN_REPEAT_INTERVAL + _stable_int("interval", dataset, problem_id) % span


def _selected_block_offset(
    *,
    dataset: str,
    problem_id: str,
    interval: int,
    block_index: int,
) -> int:
    return _stable_int("offset", dataset, problem_id, str(interval), str(block_index)) % interval


def _stable_int(*parts: str) -> int:
    payload = "\x1f".join(parts).encode("utf-8")
    return int.from_bytes(hashlib.blake2b(payload, digest_size=8).digest(), "big")
