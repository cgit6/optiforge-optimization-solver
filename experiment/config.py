from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from ..engine.repository import ProblemRepository
from ..problem import buildProblemRegistry, problemBuilders
from ..tools.solver_config_loader import SolverConfigLoader


_REQUIRED_TOP_LEVEL_KEYS = frozenset(
    {"experiment_name", "seed", "collects", "solvers", "repeat", "dataset_settings"}
)
_ALLOWED_TOP_LEVEL_KEYS = _REQUIRED_TOP_LEVEL_KEYS | {"worker"}
_REQUIRED_DATASET_KEYS = frozenset({"experiment-id", "dataset", "problems", "type", "evaluation"})
_ALLOWED_DATASET_KEYS = _REQUIRED_DATASET_KEYS
_REQUIRED_EVALUATION_KEYS = frozenset({"name"})
_ALLOWED_EVALUATION_KEYS = _REQUIRED_EVALUATION_KEYS | {"config"}


@dataclass(frozen=True)
class EvaluationSpec:
    name: str
    config: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("evaluation.name cannot be empty.")
        if not isinstance(self.config, dict):
            raise ValueError("evaluation.config must be a mapping.")
        object.__setattr__(self, "config", dict(self.config))


@dataclass(frozen=True)
class DatasetSetting:
    experiment_id: str
    dataset: str
    problem_ids: tuple[str, ...]
    problem_type: str
    evaluation: EvaluationSpec

    def __post_init__(self) -> None:
        if not self.experiment_id.strip():
            raise ValueError("experiment-id cannot be empty.")
        if not self.dataset.strip():
            raise ValueError("dataset cannot be empty.")
        if not self.problem_type.strip():
            raise ValueError("type cannot be empty.")
        if not self.problem_ids:
            raise ValueError("problems cannot be empty.")
        if any(not problem_id.strip() for problem_id in self.problem_ids):
            raise ValueError("problems cannot contain empty value.")
        if len(set(self.problem_ids)) != len(self.problem_ids):
            raise ValueError("problems cannot contain duplicate value.")


@dataclass(frozen=True)
class ExperimentConfig:
    experiment_name: str
    seed_range: tuple[int, int]
    collects: int
    solver_ids: tuple[str, ...]
    repeat: int
    dataset_settings: tuple[DatasetSetting, ...]
    worker_count: int = 1

    def __post_init__(self) -> None:
        if not self.experiment_name.strip():
            raise ValueError("experiment_name cannot be empty.")
        start, end = self.seed_range
        if start < 0 or end < 0:
            raise ValueError("seed values must be >= 0.")
        if start > end:
            raise ValueError("seed start must be <= seed end.")
        if self.collects <= 0:
            raise ValueError("collects must be > 0.")
        if self.repeat <= 0:
            raise ValueError("repeat must be > 0.")
        if self.worker_count <= 0:
            raise ValueError("worker must be > 0.")
        if not self.solver_ids:
            raise ValueError("solvers cannot be empty.")
        if any(not solver_id.strip() for solver_id in self.solver_ids):
            raise ValueError("solvers cannot contain empty value.")
        if len(set(self.solver_ids)) != len(self.solver_ids):
            raise ValueError("solvers cannot contain duplicate value.")
        if not self.dataset_settings:
            raise ValueError("dataset_settings cannot be empty.")


def load_config(
    exp_path: Path | str,
    *,
    problem_root: Path | str = Path("configs/problems"),
    solver_root: Path | str = Path("configs/solvers"),
) -> ExperimentConfig:
    raw = _read_yaml(Path(exp_path))
    return _parse_config(raw, problem_root=Path(problem_root), solver_root=Path(solver_root))


def _read_yaml(path: Path) -> dict[str, Any]:
    yaml = YAML(typ="safe")
    try:
        with path.open("r", encoding="utf-8") as fh:
            loaded = yaml.load(fh)
    except YAMLError as exc:
        raise ValueError(f"Invalid experiment config YAML format in {path}: {exc}") from exc

    if not isinstance(loaded, dict):
        raise ValueError(f"Experiment config must be a mapping: {path}")
    return loaded


def _parse_config(raw: dict[str, Any], *, problem_root: Path, solver_root: Path) -> ExperimentConfig:
    _validate_keys(
        raw,
        required=_REQUIRED_TOP_LEVEL_KEYS,
        allowed=_ALLOWED_TOP_LEVEL_KEYS,
        context="experiment config",
    )
    experiment_name = _parse_non_empty_string(raw["experiment_name"], "experiment_name")
    seed_range = _parse_seed_range(raw["seed"])
    collects = _parse_positive_int(raw["collects"], "collects")
    repeat = _parse_positive_int(raw["repeat"], "repeat")
    worker_count = _parse_positive_int(raw.get("worker", 1), "worker")
    solver_ids = _parse_string_list(raw["solvers"], "solvers")

    solver_configs = _load_solver_configs(solver_ids, solver_root)
    solver_capabilities = _solver_capabilities(solver_configs)
    dataset_settings = _parse_dataset_settings(
        raw["dataset_settings"],
        problem_root=problem_root,
        solver_capabilities=solver_capabilities,
    )
    return ExperimentConfig(
        experiment_name=experiment_name,
        seed_range=seed_range,
        collects=collects,
        solver_ids=solver_ids,
        repeat=repeat,
        dataset_settings=dataset_settings,
        worker_count=worker_count,
    )


def _parse_seed_range(value: Any) -> tuple[int, int]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("seed must be a list with exactly two integers: [start, end].")
    start = _parse_non_negative_int(value[0], "seed[0]")
    end = _parse_non_negative_int(value[1], "seed[1]")
    if start > end:
        raise ValueError("seed start must be <= seed end.")
    return (start, end)


def _parse_dataset_settings(
    value: Any,
    *,
    problem_root: Path,
    solver_capabilities: dict[str, dict[str, set[str]]],
) -> tuple[DatasetSetting, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError("dataset_settings must be a non-empty list.")

    problem_registry = buildProblemRegistry(problemBuilders())
    repository = ProblemRepository(config_root=problem_root, registry=problem_registry)
    settings: list[DatasetSetting] = []
    experiment_ids: set[str] = set()
    for index, item in enumerate(value):
        setting = _parse_dataset_setting(
            item,
            index=index,
            repository=repository,
            solver_capabilities=solver_capabilities,
        )
        if setting.experiment_id in experiment_ids:
            raise ValueError(f"dataset_settings[{index}].experiment-id is duplicated: {setting.experiment_id}")
        experiment_ids.add(setting.experiment_id)
        settings.append(setting)
    return tuple(settings)


def _parse_dataset_setting(
    item: Any,
    *,
    index: int,
    repository: ProblemRepository,
    solver_capabilities: dict[str, dict[str, set[str]]],
) -> DatasetSetting:
    context = f"dataset_settings[{index}]"
    if not isinstance(item, dict):
        raise ValueError(f"{context} must be a mapping.")
    _validate_keys(item, required=_REQUIRED_DATASET_KEYS, allowed=_ALLOWED_DATASET_KEYS, context=context)

    experiment_id = _parse_non_empty_string(item["experiment-id"], f"{context}.experiment-id")
    dataset = _parse_non_empty_string(item["dataset"], f"{context}.dataset")
    problem_type = _parse_non_empty_string(item["type"], f"{context}.type")
    problem_ids = _parse_string_list(item["problems"], f"{context}.problems")
    evaluation = _parse_evaluation(item["evaluation"], context=f"{context}.evaluation")

    metas = [repository.read_metadata(dataset, problem_id, problem_type) for problem_id in problem_ids]
    triples = {(m["problem_type"], m["encoding"], m["direction"]) for m in metas}
    if len(triples) != 1:
        raise ValueError(f"{context} cannot mix problem_type / encoding / direction: {sorted(triples)}")
    metadata_problem_type, encoding, direction = next(iter(triples))
    _validate_solver_capabilities(
        solver_capabilities,
        problem_type=str(metadata_problem_type),
        encoding=str(encoding),
        direction=str(direction),
        context=context,
    )
    return DatasetSetting(
        experiment_id=experiment_id,
        dataset=dataset,
        problem_ids=problem_ids,
        problem_type=problem_type,
        evaluation=evaluation,
    )


def _parse_evaluation(value: Any, *, context: str = "evaluation") -> EvaluationSpec:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a mapping.")
    _validate_keys(
        value,
        required=_REQUIRED_EVALUATION_KEYS,
        allowed=_ALLOWED_EVALUATION_KEYS,
        context=context,
    )
    raw_config = value.get("config", {})
    if raw_config is None:
        raw_config = {}
    if not isinstance(raw_config, dict):
        raise ValueError(f"{context}.config must be a mapping.")
    return EvaluationSpec(
        name=_parse_non_empty_string(value["name"], f"{context}.name"),
        config=raw_config,
    )


def _load_solver_configs(solver_ids: tuple[str, ...], solver_root: Path) -> dict[str, tuple[dict[str, Any], ...]]:
    loader = SolverConfigLoader(config_root=solver_root)
    return {solver_id: loader.load_all(solver_id) for solver_id in solver_ids}


def _solver_capabilities(
    solver_configs: dict[str, tuple[dict[str, Any], ...]]
) -> dict[str, dict[str, set[str]]]:
    capabilities_by_solver: dict[str, dict[str, set[str]]] = {}
    for solver_id, configs in solver_configs.items():
        capabilities = configs[0]["capabilities"]
        capabilities_by_solver[solver_id] = {
            "problem_types": {str(v) for v in capabilities["problem_types"]},
            "encodings": {str(v) for v in capabilities["encodings"]},
            "directions": {str(v) for v in capabilities["directions"]},
        }
    return capabilities_by_solver


def _validate_solver_capabilities(
    solver_capabilities: dict[str, dict[str, set[str]]],
    *,
    problem_type: str,
    encoding: str,
    direction: str,
    context: str,
) -> None:
    for solver_id, capabilities in solver_capabilities.items():
        if problem_type not in capabilities["problem_types"]:
            raise ValueError(
                f"{context}: solver={solver_id} is incompatible: "
                f"problem_type={problem_type!r} not in {sorted(capabilities['problem_types'])!r}"
            )
        if encoding not in capabilities["encodings"]:
            raise ValueError(
                f"{context}: solver={solver_id} is incompatible: "
                f"encoding={encoding!r} not in {sorted(capabilities['encodings'])!r}"
            )
        if direction not in capabilities["directions"]:
            raise ValueError(
                f"{context}: solver={solver_id} is incompatible: "
                f"direction={direction!r} not in {sorted(capabilities['directions'])!r}"
            )


def _validate_keys(
    value: dict[str, Any],
    *,
    required: frozenset[str],
    allowed: frozenset[str],
    context: str,
) -> None:
    keys = {str(k) for k in value}
    missing = sorted(required - keys)
    unknown = sorted(keys - allowed)
    if missing:
        raise ValueError(f"{context} missing required key(s): {missing}")
    if unknown:
        raise ValueError(f"{context} has unknown key(s): {unknown}")


def _parse_string_list(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field_name} must be a non-empty list.")
    parsed = tuple(_parse_non_empty_string(item, f"{field_name}[{index}]") for index, item in enumerate(value))
    if len(set(parsed)) != len(parsed):
        raise ValueError(f"{field_name} cannot contain duplicate value.")
    return parsed


def _parse_non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")
    parsed = value.strip()
    if not parsed:
        raise ValueError(f"{field_name} cannot be empty.")
    return parsed


def _parse_positive_int(value: Any, field_name: str) -> int:
    parsed = _parse_int(value, field_name)
    if parsed <= 0:
        raise ValueError(f"{field_name} must be > 0.")
    return parsed


def _parse_non_negative_int(value: Any, field_name: str) -> int:
    parsed = _parse_int(value, field_name)
    if parsed < 0:
        raise ValueError(f"{field_name} must be >= 0.")
    return parsed


def _parse_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")
    return int(value)
