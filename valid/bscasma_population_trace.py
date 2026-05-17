from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import importlib
import json
import math
import random
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from ruamel.yaml import YAML

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1].parent))
    from mkp.problem import ProblemModel
    from mkp.solver.BSCASMA import BRLSMASCATestCore
else:
    from ..problem import ProblemModel
    from ..solver.BSCASMA import BRLSMASCATestCore


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
    "a",
    "z",
    "prob_arr",
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
    "old_crashed_iteration",
    "new_crashed_iteration",
    "crash_match",
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
    # 若 run 過程中觸發 old 已知的 S=0 NaN bug 而崩潰，記錄崩潰 iter 與例外型別（用於比較 old/new 崩潰行為是否一致）
    crashed_iteration: int | None = None
    crashed_exception: str | None = None


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
    a: float
    z: float
    prob_arr: tuple[float, ...]
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
    old_crashed_iteration: int | None = None
    new_crashed_iteration: int | None = None
    crash_match: bool = True


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

    def _result(
        self,
        *,
        executed_iterations: int,
        stop_iteration: int | None,
        stop_reason: str,
        crashed_iteration: int | None = None,
        crashed_exception: str | None = None,
    ) -> TraceRunResult:
        return TraceRunResult(
            final_fit=int(self.Gbest_fit) if self.Gbest_fit is not None else -1,  # type: ignore[attr-defined]
            final_solution_digest=_solution_digest(self.Gbest_sol) if self.Gbest_sol is not None else "",  # type: ignore[attr-defined]
            executed_iterations=int(executed_iterations),
            stop_iteration=stop_iteration,
            stop_reason=stop_reason,
            rows=tuple(self.trace_rows),
            crashed_iteration=crashed_iteration,
            crashed_exception=crashed_exception,
        )


def _load_old_bscasma_test_class(repo_root: Path) -> type[Any]:
    old_dir = repo_root / "old"
    if not old_dir.is_dir():
        raise FileNotFoundError(f"old BSCASMA directory not found: {old_dir}")
    if str(old_dir) not in sys.path:
        sys.path.insert(0, str(old_dir))
    module = importlib.import_module("BSCASMA")
    return getattr(module, "BRLSMASCATest")


def _make_old_trace_class(old_base: type[Any]) -> type[Any]:
    class OldTraceBSCASMATest(PopulationTraceMixin, old_base):  # type: ignore[misc, valid-type]
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
            a: float = 2.0,
            z: float = 0.03,
            prob_arr: tuple[float, ...] = (0.04, 0.46, 0.25, 0.25),
        ) -> None:
            # 舊版 _test 雖有 seed 參數但 __init__ 內並未使用；雙源 RNG 必須在這裡 seed
            random.seed(seed)
            np.random.seed(seed)
            old_base.__init__(self, items, dim, glbal_best, values, weights, capacities, seed=seed)
            self.trace_rows: list[PopulationTraceRow] = []
            self._configure_trace_params(pop_size=pop_size, a=a, z=z, prob_arr=prob_arr, seed=seed)

        def _configure_trace_params(
            self,
            *,
            pop_size: int,
            a: float,
            z: float,
            prob_arr: tuple[float, ...],
            seed: int | None,
        ) -> None:
            pop_size = int(pop_size)
            self.a = float(a)
            self.z = float(z)
            if pop_size == int(self.pop_size):
                return
            self.pop_size = pop_size
            self.W = np.zeros([self.pop_size, self.items])
            self.pop_fit = np.zeros([self.pop_size], dtype=int)
            self.pop_fit_new = np.zeros([self.pop_size], dtype=int)
            self.individual_best_sol = np.zeros([self.pop_size, self.items], dtype=int)
            self.individual_best_fit = np.zeros([self.pop_size], dtype=int)
            random.seed(seed)
            np.random.seed(seed)
            self.initial_pop()
            # 與 old _test __init__ 重新生成 prob_arr 與 best_method 一樣的順序
            self.prob_arr = np.array(list(prob_arr) * self.pop_size)
            self.exe_time = np.zeros([self.pop_size, 4], dtype=int)
            # 原版 init_best_method 用 literal probabilities，我們以 prob_arr 覆寫保持與 new 一致
            elements = [0, 1, 2, 3]
            self.best_method = np.random.choice(elements, size=self.pop_size, p=list(prob_arr))

        def run_with_population_trace(self) -> TraceRunResult:
            self._snapshot("initial_unsorted", -1)
            random.seed(self.seed)
            np.random.seed(self.seed)

            self.pop_sol, self.pop_fit, self.individual_best_sol, self.individual_best_fit = self.sort_pop()
            self._snapshot("initial_sorted", -1)
            self.Gbest_sol = copy.deepcopy(self.pop_sol[0])
            self.Gbest_fit = copy.deepcopy(self.pop_fit[0])

            for iteration in range(self.max_iter):
                self.update_sma_weight()
                self.r1 = self.a - self.a * (iteration / self.max_iter)

                for i in range(self.pop_size):
                    action = self.policy(i)

                    if action == 0:
                        self.sma_global(i)
                    elif action == 1:
                        self.sma_local(i, iteration)
                    elif action == 2:
                        self.sca_sin(i)
                    elif action == 3:
                        self.sca_cos(i)

                    self.pop_fit[i] = np.sum(np.multiply(self.values, self.pop_sol[i]))
                    self.pop_sol[i], self.pop_fit[i] = self.repair(self.pop_sol[i], self.pop_fit[i])
                    (
                        self.pop_sol,
                        self.pop_fit,
                        self.individual_best_sol,
                        self.individual_best_fit,
                    ) = self.sort_pop()

                    if self.pop_fit[i] > self.individual_best_fit[i]:
                        self.individual_best_sol[i] = copy.deepcopy(self.pop_sol[0])
                        self.individual_best_fit[i] = copy.deepcopy(self.pop_fit[0])
                        self.best_method[i] = action

                    if self.pop_fit[0] > self.Gbest_fit:
                        self.Gbest_sol = copy.deepcopy(self.pop_sol[0])
                        self.Gbest_fit = copy.deepcopy(self.pop_fit[0])

                    if self.Gbest_fit == self.glbal_best:
                        self._snapshot("iteration_end", iteration)
                        return self._result(
                            executed_iterations=iteration + 1,
                            stop_iteration=iteration,
                            stop_reason="best_known_reached",
                        )

                self._snapshot("iteration_end", iteration)

            return self._result(
                executed_iterations=int(self.max_iter),
                stop_iteration=int(self.max_iter) - 1,
                stop_reason="max_iterations_reached",
            )

    return OldTraceBSCASMATest


class NewTraceBSCASMATest(PopulationTraceMixin, BRLSMASCATestCore):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        BRLSMASCATestCore.__init__(self, *args, **kwargs)
        self.trace_rows: list[PopulationTraceRow] = []

    def run_with_population_trace(self) -> TraceRunResult:
        self._snapshot("initial_unsorted", -1)
        random.seed(self.seed)
        np.random.seed(self.seed)

        self.pop_sol, self.pop_fit, self.individual_best_sol, self.individual_best_fit = self.sort_pop()
        self._snapshot("initial_sorted", -1)
        self.Gbest_sol = copy.deepcopy(self.pop_sol[0])
        self.Gbest_fit = copy.deepcopy(self.pop_fit[0])

        for iteration in range(self.max_iter):
            self.update_sma_weight()
            self.r1 = self.a - self.a * (iteration / self.max_iter)

            for i in range(self.pop_size):
                action = self.policy(i)

                if action == 0:
                    self.sma_global(i)
                elif action == 1:
                    self.sma_local(i, iteration)
                elif action == 2:
                    self.sca_sin(i)
                elif action == 3:
                    self.sca_cos(i)

                self.pop_fit[i] = np.sum(np.multiply(self.values, self.pop_sol[i]))
                self.pop_sol[i], self.pop_fit[i] = self.repair(self.pop_sol[i], self.pop_fit[i])
                (
                    self.pop_sol,
                    self.pop_fit,
                    self.individual_best_sol,
                    self.individual_best_fit,
                ) = self.sort_pop()

                if self.pop_fit[i] > self.individual_best_fit[i]:
                    self.individual_best_sol[i] = copy.deepcopy(self.pop_sol[0])
                    self.individual_best_fit[i] = copy.deepcopy(self.pop_fit[0])
                    self.best_method[i] = action

                if self.pop_fit[0] > self.Gbest_fit:
                    self.Gbest_sol = copy.deepcopy(self.pop_sol[0])
                    self.Gbest_fit = copy.deepcopy(self.pop_fit[0])

                if self.Gbest_fit == self.glbal_best:
                    self._snapshot("iteration_end", iteration)
                    return self._result(
                        executed_iterations=iteration + 1,
                        stop_iteration=iteration,
                        stop_reason="best_known_reached",
                    )

            self._snapshot("iteration_end", iteration)

        return self._result(
            executed_iterations=int(self.max_iter),
            stop_iteration=int(self.max_iter) - 1,
            stop_reason="max_iterations_reached",
        )


def _build_problem_from_yaml(repo_root: Path, dataset: str, problem_id: str) -> ProblemModel:
    file_path = repo_root / "configs/problems" / "mkp" / dataset / f"{problem_id}.yaml"
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


def _safe_run_with_trace(solver: Any) -> TraceRunResult:
    """執行 solver.run_with_population_trace()，捕捉 old 已知的 S=0 NaN bug。

    BRLSMASCATest 的 ``update_sma_weight`` 對 best=worst（S=0）情況沒做保護，會把 ``self.W`` 變成 NaN，
    後續解碼時 ``self.pop_sol[i,j]=NaN`` 嘗試轉 int 會觸發 ``ValueError("cannot convert float NaN to integer")``。
    這是 old 的 bug；fidelity 要求保留，但等價對比仍可比較「兩端是否在同一 iter 同型例外崩潰」與「崩潰前的 trace」是否一致。
    """
    try:
        return solver.run_with_population_trace()
    except ValueError as exc:
        message = str(exc)
        if "NaN" not in message and "nan" not in message:
            raise
        # 從 trace_rows 推出已執行的 outer iter 數（snapshot 順序：initial_unsorted, initial_sorted, iteration_end×N）
        completed_outer = sum(1 for row in solver.trace_rows if row.phase == "iteration_end" and row.rank == 0)
        return solver._result(
            executed_iterations=completed_outer,
            stop_iteration=completed_outer,
            stop_reason="value_error_nan",
            crashed_iteration=completed_outer,
            crashed_exception=type(exc).__name__,
        )


def _run_old_trace(
    *,
    repo_root: Path,
    problem: ProblemModel,
    seed: int,
    max_iterations: int,
    pop_size: int,
    a: float,
    z: float,
    prob_arr: tuple[float, ...],
) -> TraceRunResult:
    old_cls = _make_old_trace_class(_load_old_bscasma_test_class(repo_root))
    random.seed(seed)
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
        a=a,
        z=z,
        prob_arr=prob_arr,
    )
    solver.max_iter = int(max_iterations)
    return _safe_run_with_trace(solver)


def _run_new_trace(
    *,
    problem: ProblemModel,
    seed: int,
    max_iterations: int,
    pop_size: int,
    a: float,
    z: float,
    prob_arr: tuple[float, ...],
) -> TraceRunResult:
    random.seed(seed)
    np.random.seed(seed)
    solver = NewTraceBSCASMATest(
        problem.items,
        problem.dim,
        problem.best_known,
        np.asarray(problem.values, dtype=int),
        np.asarray(problem.weights, dtype=int),
        np.asarray(problem.capacities, dtype=int),
        seed=seed,
        pop_size=pop_size,
        a=a,
        z=z,
        max_iter=int(max_iterations),
        prob_arr=prob_arr,
    )
    return _safe_run_with_trace(solver)


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
    a: float,
    z: float,
    prob_arr: tuple[float, ...],
) -> ProblemTraceSummary:
    problem = _build_problem_from_yaml(repo_root, dataset, problem_id)
    old_result = _run_old_trace(
        repo_root=repo_root,
        problem=problem,
        seed=seed,
        max_iterations=max_iterations,
        pop_size=pop_size,
        a=a,
        z=z,
        prob_arr=prob_arr,
    )
    new_result = _run_new_trace(
        problem=problem,
        seed=seed,
        max_iterations=max_iterations,
        pop_size=pop_size,
        a=a,
        z=z,
        prob_arr=prob_arr,
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

    # 崩潰行為一致性：若一邊崩另一邊沒崩 → mismatch；兩邊都崩且 iter/exception 一致 → match
    crash_match = (
        old_result.crashed_iteration == new_result.crashed_iteration
        and old_result.crashed_exception == new_result.crashed_exception
    )

    if old_result.crashed_iteration is not None or new_result.crashed_iteration is not None:
        # 兩邊都崩潰且崩在同一 iter / 同一例外、崩前 trace 與 stop 行為都一致才算 PASS
        all_match = (
            crash_match
            and first_mismatch is None
            and final_solution_match
            and old_result.stop_iteration == new_result.stop_iteration
            and old_result.stop_reason == new_result.stop_reason
        )
    else:
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
        a=float(a),
        z=float(z),
        prob_arr=tuple(float(x) for x in prob_arr),
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
        old_crashed_iteration=old_result.crashed_iteration,
        new_crashed_iteration=new_result.crashed_iteration,
        crash_match=crash_match,
    )


def _write_summary(output_dir: Path, rows: list[ProblemTraceSummary], *, elapsed_seconds: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "summary.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            payload = asdict(row)
            payload["prob_arr"] = json.dumps(list(payload["prob_arr"]))
            writer.writerow(payload)

    payload = {
        "all_pass": all(row.all_match for row in rows),
        "problem_count": len(rows),
        "elapsed_seconds": round(elapsed_seconds, 3),
        "results": [
            {**asdict(row), "prob_arr": list(row.prob_arr)} for row in rows
        ],
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


def _parse_prob_arr(raw: str | None) -> tuple[float, ...]:
    if raw is None or not raw.strip():
        return (0.04, 0.46, 0.25, 0.25)
    parts = [token.strip() for token in raw.split(",") if token.strip()]
    if len(parts) != 4:
        raise ValueError("--prob-arr must contain exactly 4 comma-separated probabilities")
    values = tuple(float(x) for x in parts)
    if any(v < 0 for v in values) or abs(sum(values) - 1.0) > 1e-9:
        raise ValueError("--prob-arr values must be non-negative and sum to 1.0")
    return values


def run_population_trace(
    *,
    repo_root: Path,
    output_dir: Path,
    seed: int,
    max_iterations: int,
    pop_size: int,
    a: float,
    z: float,
    prob_arr: tuple[float, ...],
    problems: tuple[tuple[str, str], ...],
) -> dict[str, Any]:
    if max_iterations <= 0:
        raise ValueError("max_iterations must be > 0")
    if pop_size <= 0:
        raise ValueError("pop_size must be > 0")
    if a <= 0:
        raise ValueError("a must be > 0")
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
            a=a,
            z=z,
            prob_arr=prob_arr,
        )
        summaries.append(summary)
        status = "PASS" if summary.all_match else "FAIL"
        crash_note = ""
        if summary.old_crashed_iteration is not None or summary.new_crashed_iteration is not None:
            crash_note = (
                f" [crashed old@{summary.old_crashed_iteration} new@{summary.new_crashed_iteration} "
                f"crash_match={summary.crash_match}]"
            )
        print(
            f"{dataset}/{problem_id}: {status} "
            f"old={summary.final_objective_old} new={summary.final_objective_new} "
            f"trace={summary.trace_csv}{crash_note}",
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
    parser = argparse.ArgumentParser(description="Compare old/new BRLSMASCA test-policy population fitness traces.")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path, default=Path("output/bscasma_population_trace"))
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--max-iterations", type=int, default=5000)
    parser.add_argument("--pop-size", type=int, default=20)
    parser.add_argument("--a", type=float, default=2.0)
    parser.add_argument("--z", type=float, default=0.03)
    parser.add_argument(
        "--prob-arr",
        type=str,
        default=None,
        help="Comma-separated 4 probabilities (sma_global,sma_local,sca_sin,sca_cos). Defaults to 0.04,0.46,0.25,0.25",
    )
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
        a=float(args.a),
        z=float(args.z),
        prob_arr=_parse_prob_arr(args.prob_arr),
        problems=_parse_problem_list(args.problems),
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
