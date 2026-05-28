from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

SEED_BANK_VERSION = 1


def variant_key(solver_id: str, param_set_index: int) -> str:
    return f"{str(solver_id).strip()}:{int(param_set_index)}"


def solver_config_snapshot(config: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "solver_id": str(config["solver_id"]),
        "param_set_index": int(config["param_set_index"]),
        "solver_class": copy.deepcopy(config["solver_class"]),
        "capabilities": copy.deepcopy(config["capabilities"]),
        "stop_condition": copy.deepcopy(config["stop_condition"]),
        "params": copy.deepcopy(config["params"]),
    }


def problem_seed_entry(
    *,
    dataset_experiment_id: str,
    dataset: str,
    problem_type: str,
    problem_id: str,
    collected_repeat_indices: Iterable[int],
    run_seeds: Iterable[int],
    variant_keys: Iterable[str],
) -> dict[str, Any]:
    repeat_indices = tuple(int(value) for value in collected_repeat_indices)
    seeds = tuple(int(value) for value in run_seeds)
    if len(repeat_indices) != len(seeds):
        raise ValueError("collected_repeat_indices and run_seeds length must match.")
    if not seeds:
        raise ValueError("problem seed entry must contain at least one run seed.")
    variants = tuple(str(value) for value in variant_keys)
    if not variants:
        raise ValueError("problem seed entry must contain at least one variant.")
    return {
        "dataset_experiment_id": str(dataset_experiment_id),
        "dataset": str(dataset),
        "problem_type": str(problem_type),
        "problem_id": str(problem_id),
        "collected_repeat_indices": list(repeat_indices),
        "run_seeds": list(seeds),
        "variants": list(variants),
    }


def build_seed_bank(
    *,
    experiment_name: str,
    base_seed: int,
    seed_strategy: str,
    variants: Iterable[Mapping[str, Any]],
    problems: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    variant_map: dict[str, dict[str, Any]] = {}
    for variant in variants:
        snapshot = solver_config_snapshot(variant)
        key = variant_key(snapshot["solver_id"], snapshot["param_set_index"])
        if key in variant_map and variant_map[key] != snapshot:
            raise ValueError(f"conflicting solver variant snapshot in seed bank: {key!r}")
        variant_map[key] = snapshot

    problem_entries = [copy.deepcopy(dict(problem)) for problem in problems]
    if not problem_entries:
        raise ValueError("seed bank requires at least one problem entry.")
    if not variant_map:
        raise ValueError("seed bank requires at least one solver variant.")

    return {
        "version": SEED_BANK_VERSION,
        "source": {
            "experiment_name": str(experiment_name),
            "base_seed": int(base_seed),
            "seed_strategy": str(seed_strategy),
        },
        "variants": variant_map,
        "problems": problem_entries,
    }


def write_seed_bank(path: Path | str, payload: Mapping[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(_json_safe(dict(payload)), fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")


def load_seed_bank(path: Path | str) -> dict[str, Any]:
    path = Path(path)
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    validate_seed_bank(payload)
    return payload


def validate_seed_bank(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise ValueError("seed_bank must be a JSON object.")
    if int(payload.get("version", -1)) != SEED_BANK_VERSION:
        raise ValueError(f"unsupported seed_bank version: {payload.get('version')!r}")
    source = payload.get("source")
    if not isinstance(source, dict):
        raise ValueError("seed_bank.source must be an object.")
    variants = payload.get("variants")
    if not isinstance(variants, dict) or not variants:
        raise ValueError("seed_bank.variants must be a non-empty object.")
    for key, config in variants.items():
        if not isinstance(config, dict):
            raise ValueError(f"seed_bank variant must be an object: {key!r}")
        expected_key = variant_key(str(config.get("solver_id", "")), int(config.get("param_set_index", -1)))
        if key != expected_key:
            raise ValueError(f"seed_bank variant key mismatch: {key!r} != {expected_key!r}")
        for field in ("solver_class", "capabilities", "stop_condition", "params"):
            if field not in config:
                raise ValueError(f"seed_bank variant {key!r} missing {field!r}.")

    problems = payload.get("problems")
    if not isinstance(problems, list) or not problems:
        raise ValueError("seed_bank.problems must be a non-empty list.")
    for index, problem in enumerate(problems):
        if not isinstance(problem, dict):
            raise ValueError(f"seed_bank.problems[{index}] must be an object.")
        for field in ("dataset", "problem_type", "problem_id", "collected_repeat_indices", "run_seeds", "variants"):
            if field not in problem:
                raise ValueError(f"seed_bank.problems[{index}] missing {field!r}.")
        seeds = problem["run_seeds"]
        repeat_indices = problem["collected_repeat_indices"]
        problem_variants = problem["variants"]
        if not isinstance(seeds, list) or not seeds:
            raise ValueError(f"seed_bank.problems[{index}].run_seeds must be a non-empty list.")
        if not isinstance(repeat_indices, list) or len(repeat_indices) != len(seeds):
            raise ValueError(
                f"seed_bank.problems[{index}].collected_repeat_indices length must match run_seeds."
            )
        if not isinstance(problem_variants, list) or not problem_variants:
            raise ValueError(f"seed_bank.problems[{index}].variants must be a non-empty list.")
        for key in problem_variants:
            if key not in variants:
                raise ValueError(f"seed_bank problem references unknown variant: {key!r}")


def matching_problem_entries(
    payload: Mapping[str, Any],
    *,
    solver_id: str,
    param_set_index: int,
) -> tuple[dict[str, Any], ...]:
    key = variant_key(solver_id, param_set_index)
    return tuple(
        copy.deepcopy(problem)
        for problem in payload["problems"]
        if key in set(problem["variants"])
    )


def variant_config(payload: Mapping[str, Any], *, solver_id: str, param_set_index: int) -> dict[str, Any]:
    key = variant_key(solver_id, param_set_index)
    variants = payload["variants"]
    if key not in variants:
        raise KeyError(f"seed_bank does not contain solver variant: {key!r}")
    return copy.deepcopy(variants[key])


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value
