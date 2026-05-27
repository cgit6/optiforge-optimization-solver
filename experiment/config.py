from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from ..engine.repository import ProblemRepository
from ..problem import buildProblemRegistry, problemBuilders
from ..tools.solver_config_loader import SolverConfigLoader


DEFAULT_WORKER_COUNT = 15 # 併發數

_REQUIRED_TOP_LEVEL_KEYS = frozenset(
    {"experiment_name", "collects", "solvers", "repeat", "dataset_settings"}
)
_ALLOWED_TOP_LEVEL_KEYS = _REQUIRED_TOP_LEVEL_KEYS
_REQUIRED_SOLVER_KEYS = frozenset({"solver", "param_idx"})
_ALLOWED_SOLVER_KEYS = _REQUIRED_SOLVER_KEYS
_REQUIRED_DATASET_KEYS = frozenset({"experiment-id", "dataset", "problems", "type"})
_ALLOWED_DATASET_KEYS = _REQUIRED_DATASET_KEYS
_REQUIRED_PROBLEM_KEYS = frozenset({"problem", "evaluation"})
_ALLOWED_PROBLEM_KEYS = _REQUIRED_PROBLEM_KEYS | {"base_line"}
_REQUIRED_BASELINE_KEYS = frozenset({"name"})
_ALLOWED_BASELINE_KEYS = _REQUIRED_BASELINE_KEYS | {"Mean", "Pdev"}


@dataclass(frozen=True)
class EvaluationBaseline:
    name: str
    mean: float | None = None
    pdev: float | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("base_line.name cannot be empty.")
        if self.mean is None and self.pdev is None:
            raise ValueError("base_line must contain Mean or Pdev.")
        object.__setattr__(self, "mean", _validate_optional_float(self.mean, "base_line.Mean"))
        object.__setattr__(self, "pdev", _validate_optional_float(self.pdev, "base_line.Pdev"))


@dataclass(frozen=True)
class EvaluationSpec:
    name: str
    base_line: tuple[EvaluationBaseline, ...] = ()

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("evaluation name cannot be empty.")
        base_line = tuple(self.base_line)
        if any(not isinstance(item, EvaluationBaseline) for item in base_line):
            raise ValueError("base_line must contain EvaluationBaseline entries.")
        object.__setattr__(self, "base_line", base_line)


@dataclass(frozen=True)
class ProblemSetting:
    problem_id: str
    evaluations: tuple[EvaluationSpec, ...]

    def __post_init__(self) -> None:
        if not self.problem_id.strip():
            raise ValueError("problem cannot be empty.")
        evaluations = tuple(self.evaluations)
        if any(not isinstance(item, EvaluationSpec) for item in evaluations):
            raise ValueError("evaluation must contain EvaluationSpec entries.")
        names = tuple(item.name for item in evaluations)
        if len(set(names)) != len(names):
            raise ValueError("evaluation cannot contain duplicate value.")
        object.__setattr__(self, "evaluations", evaluations)

    @property
    def evaluation_names(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.evaluations)


@dataclass(frozen=True)
class DatasetSetting:
    experiment_id: str
    dataset: str
    problem_settings: tuple[ProblemSetting, ...]
    problem_type: str

    def __post_init__(self) -> None:
        if not self.experiment_id.strip():
            raise ValueError("experiment-id cannot be empty.")
        if not self.dataset.strip():
            raise ValueError("dataset cannot be empty.")
        if not self.problem_type.strip():
            raise ValueError("type cannot be empty.")
        problem_settings = tuple(self.problem_settings)
        if not problem_settings:
            raise ValueError("problems cannot be empty.")
        if any(not isinstance(item, ProblemSetting) for item in problem_settings):
            raise ValueError("problems must contain ProblemSetting entries.")
        problem_ids = tuple(item.problem_id for item in problem_settings)
        if len(set(problem_ids)) != len(problem_ids):
            raise ValueError("problems cannot contain duplicate value.")
        object.__setattr__(self, "problem_settings", problem_settings)

    @property
    def problem_ids(self) -> tuple[str, ...]:
        return tuple(item.problem_id for item in self.problem_settings)

    def problem_setting(self, problem_id: str) -> ProblemSetting:
        for setting in self.problem_settings:
            if setting.problem_id == problem_id:
                return setting
        raise KeyError(f"unknown problem_id in dataset setting: {problem_id!r}")


@dataclass(frozen=True)
class SolverSelection:
    solver_id: str
    param_indices: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.solver_id.strip():
            raise ValueError("solvers[].solver cannot be empty.")
        param_indices = tuple(self.param_indices)
        if not param_indices:
            raise ValueError("solvers[].param_idx cannot be empty.")
        if any(index < 0 for index in param_indices):
            raise ValueError("solvers[].param_idx must be >= 0.")
        if len(set(param_indices)) != len(param_indices):
            raise ValueError("solvers[].param_idx cannot contain duplicate value.")
        object.__setattr__(self, "param_indices", param_indices)


@dataclass(frozen=True)
class ExperimentConfig:
    experiment_name: str
    collects: int
    solver_selections: tuple[SolverSelection, ...]
    repeat: int
    dataset_settings: tuple[DatasetSetting, ...]
    worker_count: int = DEFAULT_WORKER_COUNT

    def __post_init__(self) -> None:
        if not self.experiment_name.strip():
            raise ValueError("experiment_name cannot be empty.")
        if self.collects <= 0:
            raise ValueError("collects must be > 0.")
        if self.repeat <= 0:
            raise ValueError("repeat must be > 0.")
        if self.worker_count <= 0:
            raise ValueError("worker_count must be > 0.")
        solver_selections = tuple(self.solver_selections)
        if not solver_selections:
            raise ValueError("solvers cannot be empty.")
        if any(not isinstance(item, SolverSelection) for item in solver_selections):
            raise ValueError("solvers must contain SolverSelection entries.")
        pairs = self.solver_variants
        if len(set(pairs)) != len(pairs):
            raise ValueError("solvers cannot contain duplicate solver/param_idx pair.")
        if not self.dataset_settings:
            raise ValueError("dataset_settings cannot be empty.")
        object.__setattr__(self, "solver_selections", solver_selections)

    @property
    def solver_ids(self) -> tuple[str, ...]:
        solver_ids: list[str] = []
        seen: set[str] = set()
        for selection in self.solver_selections:
            if selection.solver_id not in seen:
                seen.add(selection.solver_id)
                solver_ids.append(selection.solver_id)
        return tuple(solver_ids)

    @property
    def solver_variants(self) -> tuple[tuple[str, int], ...]:
        return tuple(
            (selection.solver_id, param_index)
            for selection in self.solver_selections
            for param_index in selection.param_indices
        )


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
    collects = _parse_positive_int(raw["collects"], "collects")
    repeat = _parse_positive_int(raw["repeat"], "repeat")
    solver_selections = _parse_solver_selections(raw["solvers"], "solvers")

    solver_configs = _load_solver_configs(_unique_solver_ids(solver_selections), solver_root)
    _validate_solver_param_indices(solver_selections, solver_configs)
    solver_capabilities = _solver_capabilities(solver_configs)
    dataset_settings = _parse_dataset_settings(
        raw["dataset_settings"],
        problem_root=problem_root,
        solver_capabilities=solver_capabilities,
    )
    return ExperimentConfig(
        experiment_name=experiment_name,
        collects=collects,
        solver_selections=solver_selections,
        repeat=repeat,
        dataset_settings=dataset_settings,
        worker_count=DEFAULT_WORKER_COUNT,
    )


def _parse_solver_selections(value: Any, field_name: str) -> tuple[SolverSelection, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field_name} must be a non-empty list.")
    selections: list[SolverSelection] = []
    seen_pairs: set[tuple[str, int]] = set()
    for index, item in enumerate(value):
        context = f"{field_name}[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{context} must be a mapping.")
        _validate_keys(item, required=_REQUIRED_SOLVER_KEYS, allowed=_ALLOWED_SOLVER_KEYS, context=context)
        solver_id = _parse_non_empty_string(item["solver"], f"{context}.solver")
        param_indices = _parse_int_list(item["param_idx"], f"{context}.param_idx")
        for param_index in param_indices:
            pair = (solver_id, param_index)
            if pair in seen_pairs:
                raise ValueError(f"solvers cannot contain duplicate solver/param_idx pair: {pair!r}")
            seen_pairs.add(pair)
        selections.append(SolverSelection(solver_id=solver_id, param_indices=param_indices))
    return tuple(selections)


def _unique_solver_ids(selections: tuple[SolverSelection, ...]) -> tuple[str, ...]:
    solver_ids: list[str] = []
    seen: set[str] = set()
    for selection in selections:
        if selection.solver_id not in seen:
            seen.add(selection.solver_id)
            solver_ids.append(selection.solver_id)
    return tuple(solver_ids)


def _validate_solver_param_indices(
    selections: tuple[SolverSelection, ...],
    solver_configs: dict[str, tuple[dict[str, Any], ...]],
) -> None:
    for selection in selections:
        available = len(solver_configs[selection.solver_id])
        for param_index in selection.param_indices:
            if param_index >= available:
                raise ValueError(
                    "solvers[].param_idx out of range: "
                    f"solver={selection.solver_id!r} param_idx={param_index} "
                    f"available=0..{available - 1}"
                )


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
    problem_settings = _parse_problem_settings(item["problems"], context=f"{context}.problems")

    metas = [
        repository.read_metadata(dataset, problem_setting.problem_id, problem_type)
        for problem_setting in problem_settings
    ]
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
        problem_settings=problem_settings,
        problem_type=problem_type,
    )


def _parse_problem_settings(value: Any, *, context: str) -> tuple[ProblemSetting, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{context} must be a non-empty list.")
    settings: list[ProblemSetting] = []
    seen_problem_ids: set[str] = set()
    for index, item in enumerate(value):
        item_context = f"{context}[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{item_context} must be a mapping.")
        _validate_keys(item, required=_REQUIRED_PROBLEM_KEYS, allowed=_ALLOWED_PROBLEM_KEYS, context=item_context)
        problem_id = _parse_non_empty_string(item["problem"], f"{item_context}.problem")
        if problem_id in seen_problem_ids:
            raise ValueError(f"{context} cannot contain duplicate problem: {problem_id!r}")
        seen_problem_ids.add(problem_id)
        base_line = _parse_base_line(item.get("base_line", []), field_name=f"{item_context}.base_line")
        evaluations = tuple(
            EvaluationSpec(name=evaluation_name, base_line=base_line)
            for evaluation_name in _parse_evaluation_list(item["evaluation"], f"{item_context}.evaluation")
        )
        settings.append(ProblemSetting(problem_id=problem_id, evaluations=evaluations))
    return tuple(settings)


def _parse_base_line(value: Any, *, field_name: str) -> tuple[EvaluationBaseline, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list.")
    return tuple(
        _parse_baseline_entry(item, field_name=f"{field_name}[{index}]")
        for index, item in enumerate(value)
    )


def _parse_baseline_entry(value: Any, *, field_name: str) -> EvaluationBaseline:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a mapping.")
    _validate_keys(
        value,
        required=_REQUIRED_BASELINE_KEYS,
        allowed=_ALLOWED_BASELINE_KEYS,
        context=field_name,
    )
    if "Mean" not in value and "Pdev" not in value:
        raise ValueError(f"{field_name} must contain Mean or Pdev.")
    return EvaluationBaseline(
        name=_parse_non_empty_string(value["name"], f"{field_name}.name"),
        mean=_parse_optional_float(value["Mean"], f"{field_name}.Mean") if "Mean" in value else None,
        pdev=_parse_optional_float(value["Pdev"], f"{field_name}.Pdev") if "Pdev" in value else None,
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


def _parse_evaluation_list(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list.")
    parsed = tuple(_parse_non_empty_string(item, f"{field_name}[{index}]") for index, item in enumerate(value))
    if len(set(parsed)) != len(parsed):
        raise ValueError(f"{field_name} cannot contain duplicate value.")
    return parsed


def _parse_int_list(value: Any, field_name: str) -> tuple[int, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field_name} must be a non-empty list.")
    parsed = tuple(_parse_non_negative_int(item, f"{field_name}[{index}]") for index, item in enumerate(value))
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


def _parse_optional_float(value: Any, field_name: str) -> float:
    parsed = _validate_optional_float(value, field_name)
    if parsed is None:
        raise ValueError(f"{field_name} cannot be empty.")
    return parsed


def _validate_optional_float(value: Any, field_name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be numeric.")
    return float(value)


def _parse_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")
    return int(value)
