from __future__ import annotations

from dataclasses import dataclass
from numbers import Real
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from ..engine.repository import ProblemRepository
from ..tools.solver_config_loader import SolverConfigLoader


_REQUIRED_TOP_LEVEL_KEYS = frozenset(
    {"experiment_name", "seed", "collects", "solvers", "repeat", "dataset_settings", "stages"}
)
_ALLOWED_TOP_LEVEL_KEYS = _REQUIRED_TOP_LEVEL_KEYS | {"worker", "evaluation", "static_baselines"}
_REQUIRED_DATASET_KEYS = frozenset({"experiment-id", "dataset", "problems", "type"})
_ALLOWED_DATASET_KEYS = _REQUIRED_DATASET_KEYS | {"base_line"}
_REQUIRED_BASELINE_KEYS = frozenset({"problem", "avg", "best", "PDev"})
_ALLOWED_BASELINE_KEYS = _REQUIRED_BASELINE_KEYS
_REQUIRED_STAGE_NAMES = ("transfer", "param", "final")
_REQUIRED_VARIANT_KEYS = frozenset({"combo_id", "solver", "param_set_index", "algorithm"})
_ALLOWED_VARIANT_KEYS = _REQUIRED_VARIANT_KEYS | {"transfer_type", "tags"}
_REQUIRED_STATIC_BASELINE_KEYS = frozenset({"combo_id", "algorithm", "results"})
_ALLOWED_STATIC_BASELINE_KEYS = _REQUIRED_STATIC_BASELINE_KEYS | {"tags"}
_REQUIRED_STATIC_RESULT_KEYS = frozenset({"problem", "avg", "best", "PDev"})
_ALLOWED_STATIC_RESULT_KEYS = _REQUIRED_STATIC_RESULT_KEYS | {"dataset"}
_ALLOWED_EVALUATION_KEYS = frozenset({"pdev_tolerance", "alpha", "target_algorithm"})
_TRANSFER_TYPES = frozenset({"S", "U", "V"})


@dataclass(frozen=True)
class BaselineEntry:
    problem: str
    avg: float
    best: float
    pdev: float

    def __post_init__(self) -> None:
        if not self.problem.strip():
            raise ValueError("base_line.problem cannot be empty.")
        if self.pdev < 0:
            raise ValueError("base_line.PDev must be >= 0.")


@dataclass(frozen=True)
class DatasetSetting:
    experiment_id: str
    dataset: str
    problem_ids: tuple[str, ...]
    problem_type: str
    base_line: tuple[BaselineEntry, ...] = ()

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
class EvaluationSetting:
    pdev_tolerance: float = 0.005
    alpha: float = 0.05
    target_algorithm: str = "HSMSCA"

    def __post_init__(self) -> None:
        if self.pdev_tolerance < 0:
            raise ValueError("evaluation.pdev_tolerance must be >= 0.")
        if not 0 < self.alpha < 1:
            raise ValueError("evaluation.alpha must be between 0 and 1.")
        if not self.target_algorithm.strip():
            raise ValueError("evaluation.target_algorithm cannot be empty.")


@dataclass(frozen=True)
class ExperimentVariant:
    combo_id: str
    solver_id: str
    param_set_index: int
    algorithm: str
    stage: str
    transfer_type: str | None = None
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.combo_id.strip():
            raise ValueError("variant.combo_id cannot be empty.")
        if not self.solver_id.strip():
            raise ValueError("variant.solver cannot be empty.")
        if self.param_set_index < 0:
            raise ValueError("variant.param_set_index must be >= 0.")
        if not self.algorithm.strip():
            raise ValueError("variant.algorithm cannot be empty.")
        if not self.stage.strip():
            raise ValueError("variant.stage cannot be empty.")


@dataclass(frozen=True)
class ExperimentStage:
    name: str
    variants: tuple[ExperimentVariant, ...]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("stage.name cannot be empty.")
        if not self.variants:
            raise ValueError(f"stage {self.name!r} variants cannot be empty.")


@dataclass(frozen=True)
class StaticBaselineResult:
    dataset: str
    problem: str
    problem_type: str
    direction: str
    avg: float
    best: float
    pdev: float

    def __post_init__(self) -> None:
        if not self.dataset.strip():
            raise ValueError("static_baselines.results.dataset cannot be empty.")
        if not self.problem.strip():
            raise ValueError("static_baselines.results.problem cannot be empty.")
        if not self.problem_type.strip():
            raise ValueError("static_baselines.results.problem_type cannot be empty.")
        if self.direction not in {"max", "min"}:
            raise ValueError("static_baselines.results.direction must be 'max' or 'min'.")
        if self.pdev < 0:
            raise ValueError("static_baselines.results.PDev must be >= 0.")


@dataclass(frozen=True)
class StaticBaseline:
    combo_id: str
    algorithm: str
    results: tuple[StaticBaselineResult, ...]
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.combo_id.strip():
            raise ValueError("static_baselines.combo_id cannot be empty.")
        if not self.algorithm.strip():
            raise ValueError("static_baselines.algorithm cannot be empty.")
        if not self.results:
            raise ValueError("static_baselines.results cannot be empty.")


@dataclass(frozen=True)
class ExperimentConfig:
    experiment_name: str
    seed_range: tuple[int, int]
    collects: int
    solver_ids: tuple[str, ...]
    repeat: int
    dataset_settings: tuple[DatasetSetting, ...]
    stages: tuple[ExperimentStage, ...]
    evaluation: EvaluationSetting = EvaluationSetting()
    static_baselines: tuple[StaticBaseline, ...] = ()
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
        stage_names = {stage.name for stage in self.stages}
        missing_stages = sorted(set(_REQUIRED_STAGE_NAMES) - stage_names)
        if missing_stages:
            raise ValueError(f"stages missing required stage(s): {missing_stages}")


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
    dataset_settings, problem_lookup = _parse_dataset_settings(
        raw["dataset_settings"],
        problem_root=problem_root,
        solver_capabilities=solver_capabilities,
    )
    stages = _parse_stages(raw["stages"], solver_ids=solver_ids, solver_configs=solver_configs)
    evaluation = _parse_evaluation(raw.get("evaluation", {}))
    static_baselines = _parse_static_baselines(
        raw.get("static_baselines", []),
        problem_lookup=problem_lookup,
        used_combo_ids={variant.combo_id for stage in stages for variant in stage.variants},
    )
    return ExperimentConfig(
        experiment_name=experiment_name,
        seed_range=seed_range,
        collects=collects,
        solver_ids=solver_ids,
        repeat=repeat,
        dataset_settings=dataset_settings,
        stages=stages,
        evaluation=evaluation,
        static_baselines=static_baselines,
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
) -> tuple[tuple[DatasetSetting, ...], dict[tuple[str, str], dict[str, str]]]:
    if not isinstance(value, list) or not value:
        raise ValueError("dataset_settings must be a non-empty list.")

    repository = ProblemRepository(config_root=problem_root)
    settings: list[DatasetSetting] = []
    experiment_ids: set[str] = set()
    problem_lookup: dict[tuple[str, str], dict[str, str]] = {}
    for index, item in enumerate(value):
        setting, metadata_by_problem = _parse_dataset_setting(
            item,
            index=index,
            repository=repository,
            solver_capabilities=solver_capabilities,
        )
        if setting.experiment_id in experiment_ids:
            raise ValueError(f"dataset_settings[{index}].experiment-id is duplicated: {setting.experiment_id}")
        experiment_ids.add(setting.experiment_id)
        for problem_id, metadata in metadata_by_problem.items():
            problem_lookup[(setting.dataset, problem_id)] = metadata
        settings.append(setting)
    return tuple(settings), problem_lookup


def _parse_dataset_setting(
    item: Any,
    *,
    index: int,
    repository: ProblemRepository,
    solver_capabilities: dict[str, dict[str, set[str]]],
) -> tuple[DatasetSetting, dict[str, dict[str, str]]]:
    context = f"dataset_settings[{index}]"
    if not isinstance(item, dict):
        raise ValueError(f"{context} must be a mapping.")
    _validate_keys(item, required=_REQUIRED_DATASET_KEYS, allowed=_ALLOWED_DATASET_KEYS, context=context)

    experiment_id = _parse_non_empty_string(item["experiment-id"], f"{context}.experiment-id")
    dataset = _parse_non_empty_string(item["dataset"], f"{context}.dataset")
    problem_type = _parse_non_empty_string(item["type"], f"{context}.type")
    problem_ids = _parse_string_list(item["problems"], f"{context}.problems")

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

    base_line = _parse_base_line(item.get("base_line", []), problem_ids=problem_ids, context=context)
    setting = DatasetSetting(
        experiment_id=experiment_id,
        dataset=dataset,
        problem_ids=problem_ids,
        problem_type=problem_type,
        base_line=base_line,
    )
    metadata_by_problem = {
        str(meta["problem_id"]): {
            "problem_type": str(meta["problem_type"]),
            "encoding": str(meta["encoding"]),
            "direction": str(meta["direction"]),
        }
        for meta in metas
    }
    return setting, metadata_by_problem


def _parse_base_line(value: Any, *, problem_ids: tuple[str, ...], context: str) -> tuple[BaselineEntry, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{context}.base_line must be a list when present.")

    problem_id_set = set(problem_ids)
    seen: set[str] = set()
    entries: list[BaselineEntry] = []
    for index, item in enumerate(value):
        item_context = f"{context}.base_line[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{item_context} must be a mapping.")
        _validate_keys(
            item,
            required=_REQUIRED_BASELINE_KEYS,
            allowed=_ALLOWED_BASELINE_KEYS,
            context=item_context,
        )
        problem = _parse_non_empty_string(item["problem"], f"{item_context}.problem")
        if problem not in problem_id_set:
            raise ValueError(f"{item_context}.problem is not listed in problems: {problem}")
        if problem in seen:
            raise ValueError(f"{item_context}.problem is duplicated: {problem}")
        seen.add(problem)
        pdev = _parse_number(item["PDev"], f"{item_context}.PDev")
        if pdev < 0:
            raise ValueError(f"{item_context}.PDev must be >= 0.")
        entries.append(
            BaselineEntry(
                problem=problem,
                avg=_parse_number(item["avg"], f"{item_context}.avg"),
                best=_parse_number(item["best"], f"{item_context}.best"),
                pdev=pdev,
            )
        )
    return tuple(entries)


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


def _parse_stages(
    value: Any,
    *,
    solver_ids: tuple[str, ...],
    solver_configs: dict[str, tuple[dict[str, Any], ...]],
) -> tuple[ExperimentStage, ...]:
    if not isinstance(value, dict) or not value:
        raise ValueError("stages must be a non-empty mapping.")
    missing = sorted(set(_REQUIRED_STAGE_NAMES) - {str(key) for key in value})
    if missing:
        raise ValueError(f"stages missing required stage(s): {missing}")

    stages: list[ExperimentStage] = []
    seen_combo_ids: set[str] = set()
    solver_id_set = set(solver_ids)
    for stage_name, stage_raw in value.items():
        name = _parse_non_empty_string(stage_name, "stages.<name>")
        context = f"stages.{name}"
        if not isinstance(stage_raw, dict):
            raise ValueError(f"{context} must be a mapping.")
        _validate_keys(stage_raw, required=frozenset({"variants"}), allowed=frozenset({"variants"}), context=context)
        variants_raw = stage_raw["variants"]
        if not isinstance(variants_raw, list) or not variants_raw:
            raise ValueError(f"{context}.variants must be a non-empty list.")
        variants: list[ExperimentVariant] = []
        stage_variant_keys: set[tuple[str, int]] = set()
        for index, item in enumerate(variants_raw):
            variant = _parse_variant(
                item,
                context=f"{context}.variants[{index}]",
                stage=name,
                solver_id_set=solver_id_set,
                solver_configs=solver_configs,
            )
            if variant.combo_id in seen_combo_ids:
                raise ValueError(f"{context}.variants[{index}].combo_id is duplicated: {variant.combo_id}")
            variant_key = (variant.solver_id, variant.param_set_index)
            if variant_key in stage_variant_keys:
                raise ValueError(
                    f"{context}.variants[{index}] duplicates a stage output variant: "
                    f"solver={variant.solver_id}, param_set_index={variant.param_set_index}"
                )
            stage_variant_keys.add(variant_key)
            seen_combo_ids.add(variant.combo_id)
            variants.append(variant)
        stages.append(ExperimentStage(name=name, variants=tuple(variants)))
    return tuple(stages)


def _parse_variant(
    item: Any,
    *,
    context: str,
    stage: str,
    solver_id_set: set[str],
    solver_configs: dict[str, tuple[dict[str, Any], ...]],
) -> ExperimentVariant:
    if not isinstance(item, dict):
        raise ValueError(f"{context} must be a mapping.")
    _validate_keys(item, required=_REQUIRED_VARIANT_KEYS, allowed=_ALLOWED_VARIANT_KEYS, context=context)
    combo_id = _parse_non_empty_string(item["combo_id"], f"{context}.combo_id")
    solver_id = _parse_non_empty_string(item["solver"], f"{context}.solver")
    if solver_id not in solver_id_set:
        raise ValueError(f"{context}.solver is not listed in top-level solvers: {solver_id}")
    param_set_index = _parse_non_negative_int(item["param_set_index"], f"{context}.param_set_index")
    if param_set_index >= len(solver_configs[solver_id]):
        raise ValueError(
            f"{context}.param_set_index out of range for solver={solver_id}: "
            f"got {param_set_index}, available indices are 0..{len(solver_configs[solver_id]) - 1}"
        )
    algorithm = _parse_non_empty_string(item["algorithm"], f"{context}.algorithm")
    transfer_type = _parse_optional_transfer_type(item.get("transfer_type"), context=context, stage=stage)
    tags = _parse_tags(item.get("tags", []), f"{context}.tags")
    return ExperimentVariant(
        combo_id=combo_id,
        solver_id=solver_id,
        param_set_index=param_set_index,
        algorithm=algorithm,
        stage=stage,
        transfer_type=transfer_type,
        tags=tags,
    )


def _parse_optional_transfer_type(value: Any, *, context: str, stage: str) -> str | None:
    if value is None:
        if stage == "transfer":
            raise ValueError(f"{context}.transfer_type is required for transfer stage.")
        return None
    parsed = _parse_non_empty_string(value, f"{context}.transfer_type")
    if stage == "transfer" and parsed not in _TRANSFER_TYPES:
        raise ValueError(f"{context}.transfer_type must be one of {sorted(_TRANSFER_TYPES)}.")
    return parsed


def _parse_evaluation(value: Any) -> EvaluationSetting:
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ValueError("evaluation must be a mapping when present.")
    _validate_keys(value, required=frozenset(), allowed=_ALLOWED_EVALUATION_KEYS, context="evaluation")
    return EvaluationSetting(
        pdev_tolerance=_parse_number(value.get("pdev_tolerance", 0.005), "evaluation.pdev_tolerance"),
        alpha=_parse_number(value.get("alpha", 0.05), "evaluation.alpha"),
        target_algorithm=_parse_non_empty_string(value.get("target_algorithm", "HSMSCA"), "evaluation.target_algorithm"),
    )


def _parse_static_baselines(
    value: Any,
    *,
    problem_lookup: dict[tuple[str, str], dict[str, str]],
    used_combo_ids: set[str],
) -> tuple[StaticBaseline, ...]:
    if value is None:
        value = []
    if not isinstance(value, list):
        raise ValueError("static_baselines must be a list when present.")

    baselines: list[StaticBaseline] = []
    seen_combo_ids = set(used_combo_ids)
    for index, item in enumerate(value):
        context = f"static_baselines[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{context} must be a mapping.")
        _validate_keys(
            item,
            required=_REQUIRED_STATIC_BASELINE_KEYS,
            allowed=_ALLOWED_STATIC_BASELINE_KEYS,
            context=context,
        )
        combo_id = _parse_non_empty_string(item["combo_id"], f"{context}.combo_id")
        if combo_id in seen_combo_ids:
            raise ValueError(f"{context}.combo_id is duplicated: {combo_id}")
        seen_combo_ids.add(combo_id)
        results = _parse_static_baseline_results(
            item["results"],
            context=context,
            problem_lookup=problem_lookup,
        )
        baselines.append(
            StaticBaseline(
                combo_id=combo_id,
                algorithm=_parse_non_empty_string(item["algorithm"], f"{context}.algorithm"),
                results=results,
                tags=_parse_tags(item.get("tags", []), f"{context}.tags"),
            )
        )
    return tuple(baselines)


def _parse_static_baseline_results(
    value: Any,
    *,
    context: str,
    problem_lookup: dict[tuple[str, str], dict[str, str]],
) -> tuple[StaticBaselineResult, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{context}.results must be a non-empty list.")
    seen: set[tuple[str, str]] = set()
    results: list[StaticBaselineResult] = []
    for index, item in enumerate(value):
        item_context = f"{context}.results[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{item_context} must be a mapping.")
        _validate_keys(
            item,
            required=_REQUIRED_STATIC_RESULT_KEYS,
            allowed=_ALLOWED_STATIC_RESULT_KEYS,
            context=item_context,
        )
        problem = _parse_non_empty_string(item["problem"], f"{item_context}.problem")
        dataset = _parse_static_result_dataset(
            item.get("dataset"),
            problem=problem,
            problem_lookup=problem_lookup,
            context=item_context,
        )
        key = (dataset, problem)
        if key not in problem_lookup:
            raise ValueError(f"{item_context} references a problem not listed in dataset_settings: {key}")
        if key in seen:
            raise ValueError(f"{item_context} is duplicated for dataset/problem: {key}")
        seen.add(key)
        pdev = _parse_number(item["PDev"], f"{item_context}.PDev")
        if pdev < 0:
            raise ValueError(f"{item_context}.PDev must be >= 0.")
        metadata = problem_lookup[key]
        results.append(
            StaticBaselineResult(
                dataset=dataset,
                problem=problem,
                problem_type=metadata["problem_type"],
                direction=metadata["direction"],
                avg=_parse_number(item["avg"], f"{item_context}.avg"),
                best=_parse_number(item["best"], f"{item_context}.best"),
                pdev=pdev,
            )
        )
    return tuple(results)


def _parse_static_result_dataset(
    value: Any,
    *,
    problem: str,
    problem_lookup: dict[tuple[str, str], dict[str, str]],
    context: str,
) -> str:
    if value is not None:
        return _parse_non_empty_string(value, f"{context}.dataset")
    matches = sorted(dataset for dataset, problem_id in problem_lookup if problem_id == problem)
    if not matches:
        raise ValueError(f"{context}.problem is not listed in dataset_settings: {problem}")
    if len(matches) > 1:
        raise ValueError(f"{context}.dataset is required because problem appears in multiple datasets: {problem}")
    return matches[0]


def _parse_tags(value: Any, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list when present.")
    tags = tuple(_parse_non_empty_string(item, f"{field_name}[{index}]") for index, item in enumerate(value))
    if len(set(tags)) != len(tags):
        raise ValueError(f"{field_name} cannot contain duplicate value.")
    return tags


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


def _parse_number(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field_name} must be numeric.")
    return float(value)
