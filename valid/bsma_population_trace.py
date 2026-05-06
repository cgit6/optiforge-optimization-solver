from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import importlib
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from ruamel.yaml import YAML

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1].parent))
    from mkp.engine.models import ProblemModel
    from mkp.solver.BSMA import BSMACore
else:
    from ..engine.models import ProblemModel
    from ..solver.BSMA import BSMACore


DEFAULT_PROBLEMS: tuple[tuple[str, str], ...] = (
    ("HP", "hp1"),
    ("HP", "hp2"),
    ("PB", "pb1"),
    ("PB", "pb2"),
    ("PET", "pet2"),
    ("PET", "pet3"),
    ("SENT", "sent01"),
    ("SENT", "sent02"),
    ("WEING", "weing1"),
    ("WEING", "weing2"),
    ("WEISH", "weish01"),
    ("WEISH", "weish02"),
)

TRACE_FIELDNAMES = (
    "dataset",
    "problem_id",
    "seed",
    "phase",
    "iteration",
    "rank",
    "old_fit",
    "new_fit",
    "fit_match",
    "old_solution_digest",
    "new_solution_digest",
    "solution_match",
)

SUMMARY_FIELDNAMES = (
    "dataset",
    "problem_id",
    "seed",
    "max_iterations",
    "pop_size",
    "z",
    "initial_unsorted_match",
    "initial_sorted_match",
    "population_trace_match",
    "final_objective_old",
    "final_objective_new",
    "final_solution_match",
    "old_stop_iteration",
    "new_stop_iteration",
    "old_stop_reason",
    "new_stop_reason",
    "first_mismatch_phase",
    "first_mismatch_iteration",
    "first_mismatch_rank",
    "first_mismatch_field",
    "trace_csv",
    "all_match",
)

PHASE_ORDER = {
    "initial_unsorted": 0,
    "initial_sorted": 1,
    "iteration_end": 2,
}


@dataclass(frozen=True)
class PopulationTraceRow:
    phase: str
    iteration: int
    rank: int
    fit: int
    solution_digest: str


@dataclass(frozen=True)
class TraceRunResult:
    final_fit: int
    final_solution_digest: str
    executed_iterations: int
    stop_iteration: int | None
    stop_reason: str
    rows: tuple[PopulationTraceRow, ...]


@dataclass(frozen=True)
class FirstMismatch:
    phase: str
    iteration: int
    rank: int
    field: str


@dataclass(frozen=True)
class ProblemTraceSummary:
    dataset: str
    problem_id: str
    seed: int
    max_iterations: int
    pop_size: int
    z: float
    initial_unsorted_match: bool
    initial_sorted_match: bool
    population_trace_match: bool
    final_objective_old: int
    final_objective_new: int
    final_solution_match: bool
    old_stop_iteration: int | None
    new_stop_iteration: int | None
    old_stop_reason: str
    new_stop_reason: str
    first_mismatch_phase: str | None
    first_mismatch_iteration: int | None
    first_mismatch_rank: int | None
    first_mismatch_field: str | None
    trace_csv: str
    all_match: bool


def _solution_digest(solution: np.ndarray) -> str:
    raw = np.asarray(solution, dtype=np.int8).ravel().tobytes()
    return hashlib.sha256(raw).hexdigest()[:16]


def _trace_key(row: PopulationTraceRow) -> tuple[str, int, int]:
    return row.phase, row.iteration, row.rank


def _sort_key(key: tuple[str, int, int]) -> tuple[int, int, int]:
    phase, iteration, rank = key
    return PHASE_ORDER.get(phase, 99), iteration, rank


class PopulationTraceMixin:
    trace_rows: list[PopulationTraceRow]

    def _snapshot(self, phase: str, iteration: int) -> None:
        for rank in range(int(self.pop_size)):  # type: ignore[attr-defined]
            self.trace_rows.append(
                PopulationTraceRow(
                    phase=phase,
                    iteration=int(iteration),
                    rank=int(rank),
                    fit=int(self.pop_fit[rank]),  # type: ignore[attr-defined]
                    solution_digest=_solution_digest(self.pop_sol[rank]),  # type: ignore[attr-defined]
                )
            )

    def _result(self, *, executed_iterations: int, stop_iteration: int | None, stop_reason: str) -> TraceRunResult:
        return TraceRunResult(
            final_fit=int(self.Gbest_fit),  # type: ignore[attr-defined]
            final_solution_digest=_solution_digest(self.Gbest_sol),  # type: ignore[attr-defined]
            executed_iterations=int(executed_iterations),
            stop_iteration=stop_iteration,
            stop_reason=stop_reason,
            rows=tuple(self.trace_rows),
        )


def _load_old_bsma_class(repo_root: Path) -> type[Any]:
    old_dir = repo_root / "old"
    if not old_dir.is_dir():
        raise FileNotFoundError(f"old BSMA directory not found: {old_dir}")
    if str(old_dir) not in sys.path:
        sys.path.insert(0, str(old_dir))
    module = importlib.import_module("BSMA")
    return getattr(module, "BSMA")


def _make_old_trace_class(old_base: type[Any]) -> type[Any]:
    class OldTraceBSMA(PopulationTraceMixin, old_base):  # type: ignore[misc, valid-type]
        def __init__(
            self,
            items: int,
            dim: int,
            glbal_best: int,
            values: np.ndarray,
            weights: np.ndarray,
            capacities: np.ndarray,
            seed: int | None = None,
            *,
            pop_size: int = 20,
            z: float = 0.08,
        ) -> None:
            old_base.__init__(self, items, dim, glbal_best, values, weights, capacities, seed=seed)
            self.trace_rows: list[PopulationTraceRow] = []
            self._configure_trace_params(pop_size=pop_size, z=z)

        def _configure_trace_params(self, *, pop_size: int, z: float) -> None:
            pop_size = int(pop_size)
            self.z = float(z)
            if pop_size == int(self.pop_size):
                return
            self.pop_size = pop_size
            self.W = np.zeros([self.pop_size, self.items])
            self.pop_fit = np.zeros([self.pop_size], dtype=int)
            if self.seed is not None:
                np.random.seed(self.seed)
            self.pop_sol = self.initial_pop()
            self.Gbest_sol = copy.deepcopy(self.pop_sol[0])
            self.Gbest_fit = copy.deepcopy(self.pop_fit[0])

        def run_with_population_trace(self) -> TraceRunResult:
            self._snapshot("initial_unsorted", -1)
            np.random.seed(self.seed)

            self.pop_sol, self.pop_fit = self.sort_pop()
            self._snapshot("initial_sorted", -1)
            self.Gbest_sol = self.pop_sol[0]
            self.Gbest_fit = self.pop_fit[0]

            for iteration in range(self.max_iter):
                self.W = np.zeros([self.pop_size, self.items])
                worst_fit = self.pop_fit[-1]
                best_fit = self.pop_fit[0]
                s_val = best_fit - worst_fit if best_fit - worst_fit > 0 else 0.0001
                for i in range(self.pop_size):
                    if i < self.pop_size / 2:
                        self.W[i, :] = 1 + np.random.random([self.items]) * np.log10(
                            (best_fit - self.pop_fit[i]) / (s_val) + 1
                        )
                    else:
                        self.W[i, :] = 1 - np.random.random([self.items]) * np.log10(
                            (best_fit - self.pop_fit[i]) / (s_val) + 1
                        )

                a = np.arctanh(-1 * ((iteration + 1) / self.max_iter) + 1)
                b = 1 - (iteration + 1) / self.max_iter

                for i in range(self.pop_size):
                    if np.random.random() < self.z:
                        self.pop_sol[i] = np.zeros(self.items)
                        accumulated_resources = np.zeros([self.dim])
                        for j in self.cp_list:
                            if np.random.uniform(0.0, 1.0) < 0.5:
                                accumulated_resources += self.weights[j]
                                if np.all(accumulated_resources <= self.capacities):
                                    self.pop_sol[i, j] = 1
                    else:
                        p = np.tanh(abs(self.pop_fit[i] - self.Gbest_fit))
                        vb = np.random.uniform(-a, a, self.items)
                        vc = np.random.uniform(-b, b, self.items)

                        for j in range(self.items):
                            r = np.random.random()
                            a_idx, b_idx = np.random.choice(list(set(range(0, self.pop_size)) - {i}), 2, replace=False)
                            if r < p:
                                self.pop_sol[i, j] = self.Gbest_sol[j] + vb[j] * (
                                    self.W[i, j] * self.pop_sol[a_idx, j] - self.pop_sol[b_idx, j]
                                )
                            else:
                                self.pop_sol[i, j] = vc[j] * self.pop_sol[i, j]

                            if np.random.uniform(0.0, 1.0) < np.abs(np.tanh(self.pop_sol[i, j])):
                                self.pop_sol[i, j] = 1
                            else:
                                self.pop_sol[i, j] = 0

                    self.pop_fit[i] = np.sum(np.multiply(self.values, self.pop_sol[i]))
                    self.pop_sol[i], self.pop_fit[i] = self.repair(self.pop_sol[i], self.pop_fit[i])

                self.pop_sol, self.pop_fit = self.sort_pop()
                if self.pop_fit[0] > self.Gbest_fit:
                    self.Gbest_sol = copy.deepcopy(self.pop_sol[0])
                    self.Gbest_fit = copy.deepcopy(self.pop_fit[0])
                self._snapshot("iteration_end", iteration)
                if self.Gbest_fit == self.glbal_best:
                    return self._result(
                        executed_iterations=iteration + 1,
                        stop_iteration=iteration,
                        stop_reason="best_known_reached",
                    )

            return self._result(
                executed_iterations=int(self.max_iter),
                stop_iteration=int(self.max_iter) - 1,
                stop_reason="max_iterations_reached",
            )

    return OldTraceBSMA


class NewTraceBSMA(PopulationTraceMixin, BSMACore):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        BSMACore.__init__(self, *args, **kwargs)
        self.trace_rows: list[PopulationTraceRow] = []

    def run_with_population_trace(self) -> TraceRunResult:
        self._snapshot("initial_unsorted", -1)
        np.random.seed(self.seed)

        self.pop_sol, self.pop_fit = self.sort_pop()
        self._snapshot("initial_sorted", -1)
        self.Gbest_sol = self.pop_sol[0]
        self.Gbest_fit = self.pop_fit[0]

        for iteration in range(self.max_iter):
            self.W = np.zeros([self.pop_size, self.items])
            worst_fit = self.pop_fit[-1]
            best_fit = self.pop_fit[0]
            s_val = best_fit - worst_fit if best_fit - worst_fit > 0 else 0.0001
            for i in range(self.pop_size):
                if i < self.pop_size / 2:
                    self.W[i, :] = 1 + np.random.random([self.items]) * np.log10(
                        (best_fit - self.pop_fit[i]) / (s_val) + 1
                    )
                else:
                    self.W[i, :] = 1 - np.random.random([self.items]) * np.log10(
                        (best_fit - self.pop_fit[i]) / (s_val) + 1
                    )

            a = np.arctanh(-1 * ((iteration + 1) / self.max_iter) + 1)
            b = 1 - (iteration + 1) / self.max_iter

            for i in range(self.pop_size):
                if np.random.random() < self.z:
                    self.pop_sol[i] = np.zeros(self.items)
                    accumulated_resources = np.zeros([self.dim])
                    for j in self.cp_list:
                        if np.random.uniform(0.0, 1.0) < 0.5:
                            accumulated_resources += self.weights[j]
                            if np.all(accumulated_resources <= self.capacities):
                                self.pop_sol[i, j] = 1
                else:
                    p = np.tanh(abs(self.pop_fit[i] - self.Gbest_fit))
                    vb = np.random.uniform(-a, a, self.items)
                    vc = np.random.uniform(-b, b, self.items)

                    for j in range(self.items):
                        r = np.random.random()
                        a_idx, b_idx = np.random.choice(list(set(range(0, self.pop_size)) - {i}), 2, replace=False)
                        if r < p:
                            self.pop_sol[i, j] = self.Gbest_sol[j] + vb[j] * (
                                self.W[i, j] * self.pop_sol[a_idx, j] - self.pop_sol[b_idx, j]
                            )
                        else:
                            self.pop_sol[i, j] = vc[j] * self.pop_sol[i, j]
                        if np.random.uniform(0.0, 1.0) < np.abs(np.tanh(self.pop_sol[i, j])):
                            self.pop_sol[i, j] = 1
                        else:
                            self.pop_sol[i, j] = 0

                self.pop_fit[i] = np.sum(np.multiply(self.values, self.pop_sol[i]))
                self.pop_sol[i], self.pop_fit[i] = self.repair(self.pop_sol[i], self.pop_fit[i])

            self.pop_sol, self.pop_fit = self.sort_pop()
            if self.pop_fit[0] > self.Gbest_fit:
                self.Gbest_sol = copy.deepcopy(self.pop_sol[0])
                self.Gbest_fit = copy.deepcopy(self.pop_fit[0])
            self._snapshot("iteration_end", iteration)
            if self.Gbest_fit == self.glbal_best:
                return self._result(
                    executed_iterations=iteration + 1,
                    stop_iteration=iteration,
                    stop_reason="best_known_reached",
                )
        return self._result(
            executed_iterations=int(self.max_iter),
            stop_iteration=int(self.max_iter) - 1,
            stop_reason="max_iterations_reached",
        )


def _build_problem_from_yaml(repo_root: Path, dataset: str, problem_id: str) -> ProblemModel:
    file_path = repo_root / "configs/problems" / dataset / f"{problem_id}.yaml"
    if not file_path.is_file():
        raise FileNotFoundError(f"problem YAML not found: {file_path}")
    yaml = YAML(typ="safe")
    data = yaml.load(file_path.read_text(encoding="utf-8"))
    return ProblemModel(
        problem_id=str(data["problem_id"]),
        dataset=str(data["dataset"]),
        items=int(data["items"]),
        dim=int(data["dim"]),
        values=np.asarray(data["values"], dtype=int),
        weights=np.asarray(data["weights"], dtype=int),
        capacities=np.asarray(data["capacities"], dtype=int),
        best_known=int(data["best_known"]),
    )


def _run_old_trace(
    *,
    repo_root: Path,
    problem: ProblemModel,
    seed: int,
    max_iterations: int,
    pop_size: int,
    z: float,
) -> TraceRunResult:
    old_cls = _make_old_trace_class(_load_old_bsma_class(repo_root))
    np.random.seed(seed)
    solver = old_cls(
        problem.items,
        problem.dim,
        problem.best_known,
        np.asarray(problem.values, dtype=int),
        np.asarray(problem.weights, dtype=int),
        np.asarray(problem.capacities, dtype=int),
        seed=seed,
        pop_size=pop_size,
        z=z,
    )
    solver.max_iter = int(max_iterations)
    return solver.run_with_population_trace()


def _run_new_trace(
    *,
    problem: ProblemModel,
    seed: int,
    max_iterations: int,
    pop_size: int,
    z: float,
) -> TraceRunResult:
    np.random.seed(seed)
    solver = NewTraceBSMA(
        problem.items,
        problem.dim,
        problem.best_known,
        np.asarray(problem.values, dtype=int),
        np.asarray(problem.weights, dtype=int),
        np.asarray(problem.capacities, dtype=int),
        seed=seed,
        pop_size=pop_size,
        z=z,
        max_iter=int(max_iterations),
    )
    return solver.run_with_population_trace()


def _rows_by_key(rows: tuple[PopulationTraceRow, ...]) -> dict[tuple[str, int, int], PopulationTraceRow]:
    return {_trace_key(row): row for row in rows}


def _rows_match(
    old_rows: tuple[PopulationTraceRow, ...],
    new_rows: tuple[PopulationTraceRow, ...],
    *,
    phase: str,
) -> bool:
    old_phase_rows = [row for row in old_rows if row.phase == phase]
    new_phase_rows = [row for row in new_rows if row.phase == phase]
    return old_phase_rows == new_phase_rows


def _first_mismatch(
    old_rows: tuple[PopulationTraceRow, ...],
    new_rows: tuple[PopulationTraceRow, ...],
) -> FirstMismatch | None:
    old_by_key = _rows_by_key(old_rows)
    new_by_key = _rows_by_key(new_rows)
    for key in sorted(set(old_by_key) | set(new_by_key), key=_sort_key):
        old_row = old_by_key.get(key)
        new_row = new_by_key.get(key)
        phase, iteration, rank = key
        if old_row is None:
            return FirstMismatch(phase=phase, iteration=iteration, rank=rank, field="missing_old")
        if new_row is None:
            return FirstMismatch(phase=phase, iteration=iteration, rank=rank, field="missing_new")
        if old_row.fit != new_row.fit:
            return FirstMismatch(phase=phase, iteration=iteration, rank=rank, field="fit")
        if old_row.solution_digest != new_row.solution_digest:
            return FirstMismatch(phase=phase, iteration=iteration, rank=rank, field="solution")
    return None


def _write_population_csv(
    *,
    path: Path,
    dataset: str,
    problem_id: str,
    seed: int,
    old_result: TraceRunResult,
    new_result: TraceRunResult,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    old_by_key = _rows_by_key(old_result.rows)
    new_by_key = _rows_by_key(new_result.rows)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TRACE_FIELDNAMES)
        writer.writeheader()
        for key in sorted(set(old_by_key) | set(new_by_key), key=_sort_key):
            phase, iteration, rank = key
            old_row = old_by_key.get(key)
            new_row = new_by_key.get(key)
            old_fit = old_row.fit if old_row is not None else ""
            new_fit = new_row.fit if new_row is not None else ""
            old_digest = old_row.solution_digest if old_row is not None else ""
            new_digest = new_row.solution_digest if new_row is not None else ""
            writer.writerow(
                {
                    "dataset": dataset,
                    "problem_id": problem_id,
                    "seed": seed,
                    "phase": phase,
                    "iteration": iteration,
                    "rank": rank,
                    "old_fit": old_fit,
                    "new_fit": new_fit,
                    "fit_match": old_row is not None and new_row is not None and old_fit == new_fit,
                    "old_solution_digest": old_digest,
                    "new_solution_digest": new_digest,
                    "solution_match": old_row is not None and new_row is not None and old_digest == new_digest,
                }
            )


def _compare_problem(
    *,
    repo_root: Path,
    output_dir: Path,
    dataset: str,
    problem_id: str,
    seed: int,
    max_iterations: int,
    pop_size: int,
    z: float,
) -> ProblemTraceSummary:
    problem = _build_problem_from_yaml(repo_root, dataset, problem_id)
    old_result = _run_old_trace(
        repo_root=repo_root,
        problem=problem,
        seed=seed,
        max_iterations=max_iterations,
        pop_size=pop_size,
        z=z,
    )
    new_result = _run_new_trace(
        problem=problem,
        seed=seed,
        max_iterations=max_iterations,
        pop_size=pop_size,
        z=z,
    )

    trace_csv = output_dir / "traces" / f"{dataset}_{problem_id}_population.csv"
    _write_population_csv(
        path=trace_csv,
        dataset=dataset,
        problem_id=problem_id,
        seed=seed,
        old_result=old_result,
        new_result=new_result,
    )

    first_mismatch = _first_mismatch(old_result.rows, new_result.rows)
    initial_unsorted_match = _rows_match(old_result.rows, new_result.rows, phase="initial_unsorted")
    initial_sorted_match = _rows_match(old_result.rows, new_result.rows, phase="initial_sorted")
    population_trace_match = _rows_match(old_result.rows, new_result.rows, phase="iteration_end")
    final_solution_match = old_result.final_solution_digest == new_result.final_solution_digest
    all_match = (
        first_mismatch is None
        and old_result.final_fit == new_result.final_fit
        and final_solution_match
        and old_result.stop_iteration == new_result.stop_iteration
        and old_result.stop_reason == new_result.stop_reason
    )
    return ProblemTraceSummary(
        dataset=dataset,
        problem_id=problem_id,
        seed=int(seed),
        max_iterations=int(max_iterations),
        pop_size=int(pop_size),
        z=float(z),
        initial_unsorted_match=initial_unsorted_match,
        initial_sorted_match=initial_sorted_match,
        population_trace_match=population_trace_match,
        final_objective_old=int(old_result.final_fit),
        final_objective_new=int(new_result.final_fit),
        final_solution_match=final_solution_match,
        old_stop_iteration=old_result.stop_iteration,
        new_stop_iteration=new_result.stop_iteration,
        old_stop_reason=old_result.stop_reason,
        new_stop_reason=new_result.stop_reason,
        first_mismatch_phase=first_mismatch.phase if first_mismatch is not None else None,
        first_mismatch_iteration=first_mismatch.iteration if first_mismatch is not None else None,
        first_mismatch_rank=first_mismatch.rank if first_mismatch is not None else None,
        first_mismatch_field=first_mismatch.field if first_mismatch is not None else None,
        trace_csv=str(trace_csv.relative_to(output_dir)),
        all_match=all_match,
    )


def _write_summary(output_dir: Path, rows: list[ProblemTraceSummary], *, elapsed_seconds: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "summary.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))

    payload = {
        "all_pass": all(row.all_match for row in rows),
        "problem_count": len(rows),
        "elapsed_seconds": round(elapsed_seconds, 3),
        "results": [asdict(row) for row in rows],
    }
    (output_dir / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_problem_list(raw: str | None) -> tuple[tuple[str, str], ...]:
    if raw is None or not raw.strip():
        return DEFAULT_PROBLEMS
    problems: list[tuple[str, str]] = []
    for item in raw.split(","):
        token = item.strip()
        if not token:
            continue
        if "/" not in token:
            raise ValueError(f"problem must use DATASET/problem_id format: {token}")
        dataset, problem_id = token.split("/", 1)
        if not dataset.strip() or not problem_id.strip():
            raise ValueError(f"problem must use DATASET/problem_id format: {token}")
        problems.append((dataset.strip(), problem_id.strip()))
    if not problems:
        raise ValueError("--problems did not contain any valid entries")
    return tuple(problems)


def run_population_trace(
    *,
    repo_root: Path,
    output_dir: Path,
    seed: int,
    max_iterations: int,
    pop_size: int,
    z: float,
    problems: tuple[tuple[str, str], ...],
) -> dict[str, Any]:
    if max_iterations <= 0:
        raise ValueError("max_iterations must be > 0")
    if pop_size <= 0:
        raise ValueError("pop_size must be > 0")
    if not (0.0 < z <= 1.0):
        raise ValueError("z must satisfy 0 < z <= 1")

    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    summaries: list[ProblemTraceSummary] = []
    for dataset, problem_id in problems:
        summary = _compare_problem(
            repo_root=repo_root,
            output_dir=output_dir,
            dataset=dataset,
            problem_id=problem_id,
            seed=seed,
            max_iterations=max_iterations,
            pop_size=pop_size,
            z=z,
        )
        summaries.append(summary)
        status = "PASS" if summary.all_match else "FAIL"
        print(
            f"{dataset}/{problem_id}: {status} "
            f"old={summary.final_objective_old} new={summary.final_objective_new} "
            f"trace={summary.trace_csv}",
            flush=True,
        )

    elapsed = time.perf_counter() - started
    _write_summary(output_dir, summaries, elapsed_seconds=elapsed)
    return {
        "all_pass": all(row.all_match for row in summaries),
        "problem_count": len(summaries),
        "elapsed_seconds": round(elapsed, 3),
        "summary_json": str(output_dir / "summary.json"),
        "summary_csv": str(output_dir / "summary.csv"),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare old/new BSMA population fitness traces.")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path, default=Path("output/bsma_population_trace"))
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--max-iterations", type=int, default=5000)
    parser.add_argument("--pop-size", type=int, default=20)
    parser.add_argument("--z", type=float, default=0.08)
    parser.add_argument(
        "--problems",
        type=str,
        default=None,
        help="Comma-separated DATASET/problem_id entries. Defaults to the representative non-GK/non-OR suite.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    output_dir = args.output_dir
    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir
    summary = run_population_trace(
        repo_root=repo_root,
        output_dir=output_dir,
        seed=int(args.seed),
        max_iterations=int(args.max_iterations),
        pop_size=int(args.pop_size),
        z=float(args.z),
        problems=_parse_problem_list(args.problems),
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
