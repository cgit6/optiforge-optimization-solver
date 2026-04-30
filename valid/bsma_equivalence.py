from __future__ import annotations

import hashlib
import importlib
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from ..converter import load_problem_model_from_repo_dat
from ..engine.models import ProblemModel
from ..solver.BSMA import BSMAV1008Core, BSMAV1008Solver


BSMA_DEFAULT_POP_SIZE = 20


@dataclass(frozen=True)
class TraceDigest:
    step: int
    phase: str
    digest: str
    best_fit: int


@dataclass
class EquivalenceReport:
    dataset: str
    problem_id: str
    seed: int
    max_iterations: int
    final_objective_old: int
    final_objective_new: int
    final_solution_match: bool
    trace_length_old: int
    trace_length_new: int
    trace_match: bool
    first_mismatch_index: int | None
    first_mismatch_old: TraceDigest | None
    first_mismatch_new: TraceDigest | None
    # 可選：新 Core 每外層迭代一筆（a,b,W0,p,vb,vc 摘要），用於 mismatch 時判斷 RNG/公式漂移
    loop_meta_new: list[dict[str, Any]] | None = None
    # 串流驗證或 solver 路徑：新求解器回報的停止原因與「公式上界」評估次數（提前達 best_known 時仍為上界）
    new_stop_reason: str | None = None
    new_reported_eval_count: int | None = None


def _digest_solution(solution: np.ndarray) -> str:
    raw = np.asarray(solution, dtype=np.int8).tobytes()
    return hashlib.sha256(raw).hexdigest()[:16]


def max_outer_iterations_for_budget(*, budget: int, pop_size: int = BSMA_DEFAULT_POP_SIZE) -> int:
    """對齊計畫：eval_total ≈ pop_size * (max_iter + 1) → max_iter = floor(budget/pop_size) - 1。"""
    if budget < pop_size:
        raise ValueError("budget must be >= pop_size")
    return int(budget // pop_size) - 1


def _trace_digest_to_line(digest: TraceDigest) -> str:
    return json.dumps(asdict(digest), ensure_ascii=False, separators=(",", ":"))


def _trace_digest_from_line(line: str) -> TraceDigest:
    data = json.loads(line)
    return TraceDigest(
        step=int(data["step"]),
        phase=str(data["phase"]),
        digest=str(data["digest"]),
        best_fit=int(data["best_fit"]),
    )


def _capture_new_loop_meta(problem: ProblemModel, seed: int, max_iterations: int) -> list[dict[str, Any]]:
    """與 BSMAV1008Solver 相同前置 seed + Core 建立方式，蒐集 _loop_trace。"""
    np.random.seed(seed)
    core = BSMAV1008Core(
        problem.items,
        problem.dim,
        problem.best_known,
        np.asarray(problem.values, dtype=int),
        np.asarray(problem.weights, dtype=int),
        np.asarray(problem.capacities, dtype=int),
        seed=seed,
        pop_size=20,
        z=0.08,
    )
    core.max_iter = int(max_iterations)
    core._loop_trace = []
    core.run()
    return list(core._loop_trace) if core._loop_trace is not None else []


def _build_problem_from_yaml(repo_root: Path, dataset: str, problem_id: str) -> ProblemModel:
    file_path = repo_root / "configs/problems" / dataset / f"{problem_id}.yaml"
    data = json.loads(file_path.read_text(encoding="utf-8"))
    return ProblemModel(
        problem_id=data["problem_id"],
        dataset=data["dataset"],
        items=int(data["items"]),
        dim=int(data["dim"]),
        values=np.asarray(data["values"], dtype=int),
        weights=np.asarray(data["weights"], dtype=int),
        capacities=np.asarray(data["capacities"], dtype=int),
        best_known=int(data["best_known"]),
    )


def _run_old_with_trace(problem: ProblemModel, seed: int, max_iterations: int, repo_root: Path) -> tuple[int, np.ndarray, list[TraceDigest]]:
    old_dir = repo_root / "old"
    if str(old_dir) not in sys.path:
        sys.path.insert(0, str(old_dir))
    bsma2 = importlib.import_module("BSMA2")
    cls = getattr(bsma2, "BSMA_V1_008")
    # Make legacy initialization deterministic for strict same-seed comparison.
    np.random.seed(seed)
    old_solver = cls(
        problem.items,
        problem.dim,
        problem.best_known,
        np.asarray(problem.values, dtype=int),
        np.asarray(problem.weights, dtype=int),
        np.asarray(problem.capacities, dtype=int),
        seed=seed,
    )
    old_solver.max_iter = int(max_iterations)
    trace: list[TraceDigest] = []
    step = {"repair": 0, "sort": 0}

    original_repair = old_solver.repair
    original_sort = old_solver.sort_pop

    def wrapped_repair(trial_sol: np.ndarray, trial_fit: int):
        repaired_sol, repaired_fit = original_repair(trial_sol, trial_fit)
        step["repair"] += 1
        trace.append(
            TraceDigest(
                step=step["repair"],
                phase="repair",
                digest=_digest_solution(repaired_sol),
                best_fit=int(repaired_fit),
            )
        )
        return repaired_sol, repaired_fit

    def wrapped_sort():
        sorted_sol, sorted_fit = original_sort()
        step["sort"] += 1
        trace.append(
            TraceDigest(
                step=step["sort"],
                phase="sort",
                digest=_digest_solution(sorted_sol[0]),
                best_fit=int(sorted_fit[0]),
            )
        )
        return sorted_sol, sorted_fit

    old_solver.repair = wrapped_repair  # type: ignore[method-assign]
    old_solver.sort_pop = wrapped_sort  # type: ignore[method-assign]
    best_sol, best_fit = old_solver.run()
    return int(best_fit), np.asarray(best_sol, dtype=int), trace


def _run_new_with_trace(problem: ProblemModel, seed: int, max_iterations: int) -> tuple[int, np.ndarray, list[TraceDigest]]:
    """與 BSMAV1008Solver 走同一套 BSMAV1008Core，僅對 Core 掛 trace（不動 old/BSMA2）。"""
    trace: list[TraceDigest] = []
    step = {"repair": 0, "sort": 0}

    original_repair = BSMAV1008Core.repair
    original_sort = BSMAV1008Core.sort_pop

    def wrapped_repair(self: Any, trial_sol: np.ndarray, trial_fit: int) -> tuple[np.ndarray, int]:
        repaired_sol, repaired_fit = original_repair(self, trial_sol, trial_fit)
        step["repair"] += 1
        trace.append(
            TraceDigest(
                step=step["repair"],
                phase="repair",
                digest=_digest_solution(repaired_sol),
                best_fit=int(repaired_fit),
            )
        )
        return repaired_sol, repaired_fit

    def wrapped_sort(self: Any) -> tuple[np.ndarray, np.ndarray]:
        sorted_sol, sorted_fit = original_sort(self)
        step["sort"] += 1
        trace.append(
            TraceDigest(
                step=step["sort"],
                phase="sort",
                digest=_digest_solution(sorted_sol[0]),
                best_fit=int(sorted_fit[0]),
            )
        )
        return sorted_sol, sorted_fit

    BSMAV1008Core.repair = wrapped_repair  # type: ignore[method-assign]
    BSMAV1008Core.sort_pop = wrapped_sort  # type: ignore[method-assign]
    solver = BSMAV1008Solver()
    config: dict[str, Any] = {
        "solver_id": "bsma_v1_008",
        "stop_condition": {"type": "max_iterations", "max_iterations": max_iterations},
        "run_seed": seed,
    }
    try:
        run_result = solver.solve(problem=problem, config=config, rng=np.random.default_rng(seed))
    finally:
        BSMAV1008Core.repair = original_repair
        BSMAV1008Core.sort_pop = original_sort
    return int(run_result.best_objective), np.asarray(run_result.best_solution, dtype=int), trace


def _run_old_with_trace_stream_to_file(
    problem: ProblemModel,
    seed: int,
    max_iterations: int,
    repo_root: Path,
    trace_path: Path,
) -> tuple[int, np.ndarray, int]:
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    old_dir = repo_root / "old"
    if str(old_dir) not in sys.path:
        sys.path.insert(0, str(old_dir))
    bsma2 = importlib.import_module("BSMA2")
    cls = getattr(bsma2, "BSMA_V1_008")
    np.random.seed(seed)
    old_solver = cls(
        problem.items,
        problem.dim,
        problem.best_known,
        np.asarray(problem.values, dtype=int),
        np.asarray(problem.weights, dtype=int),
        np.asarray(problem.capacities, dtype=int),
        seed=seed,
    )
    old_solver.max_iter = int(max_iterations)
    step = {"repair": 0, "sort": 0}
    lines_written = 0

    original_repair = old_solver.repair
    original_sort = old_solver.sort_pop

    with trace_path.open("w", encoding="utf-8") as handle:

        def wrapped_repair(trial_sol: np.ndarray, trial_fit: int):
            nonlocal lines_written
            repaired_sol, repaired_fit = original_repair(trial_sol, trial_fit)
            step["repair"] += 1
            digest = TraceDigest(
                step=step["repair"],
                phase="repair",
                digest=_digest_solution(repaired_sol),
                best_fit=int(repaired_fit),
            )
            handle.write(_trace_digest_to_line(digest) + "\n")
            lines_written += 1
            return repaired_sol, repaired_fit

        def wrapped_sort():
            nonlocal lines_written
            sorted_sol, sorted_fit = original_sort()
            step["sort"] += 1
            digest = TraceDigest(
                step=step["sort"],
                phase="sort",
                digest=_digest_solution(sorted_sol[0]),
                best_fit=int(sorted_fit[0]),
            )
            handle.write(_trace_digest_to_line(digest) + "\n")
            lines_written += 1
            return sorted_sol, sorted_fit

        old_solver.repair = wrapped_repair  # type: ignore[method-assign]
        old_solver.sort_pop = wrapped_sort  # type: ignore[method-assign]
        best_sol, best_fit = old_solver.run()
    return int(best_fit), np.asarray(best_sol, dtype=int), int(lines_written)


def _run_new_with_trace_stream_compare_file(
    problem: ProblemModel,
    seed: int,
    max_iterations: int,
    trace_path: Path,
) -> tuple[int, np.ndarray, int, bool, int | None, TraceDigest | None, TraceDigest | None, str, int]:
    expected_handle = trace_path.open("r", encoding="utf-8")
    compare_idx = 0
    trace_match = True
    first_mismatch_index: int | None = None
    mismatch_old: TraceDigest | None = None
    mismatch_new: TraceDigest | None = None
    new_lines = 0
    repair_step = [0]
    sort_step = [0]

    original_repair = BSMAV1008Core.repair
    original_sort = BSMAV1008Core.sort_pop

    def _read_expected_digest() -> TraceDigest | None:
        line = expected_handle.readline()
        if line == "":
            return None
        return _trace_digest_from_line(line.rstrip("\n"))

    def wrapped_repair(self: Any, trial_sol: np.ndarray, trial_fit: int) -> tuple[np.ndarray, int]:
        nonlocal compare_idx, trace_match, first_mismatch_index, mismatch_old, mismatch_new, new_lines
        repaired_sol, repaired_fit = original_repair(self, trial_sol, trial_fit)
        repair_step[0] += 1
        digest = TraceDigest(
            step=repair_step[0],
            phase="repair",
            digest=_digest_solution(repaired_sol),
            best_fit=int(repaired_fit),
        )
        new_lines += 1
        if trace_match:
            expected = _read_expected_digest()
            if expected is None:
                trace_match = False
                first_mismatch_index = compare_idx
                mismatch_old = None
                mismatch_new = digest
            elif expected != digest:
                trace_match = False
                first_mismatch_index = compare_idx
                mismatch_old = expected
                mismatch_new = digest
            compare_idx += 1
        return repaired_sol, repaired_fit

    def wrapped_sort(self: Any) -> tuple[np.ndarray, np.ndarray]:
        nonlocal compare_idx, trace_match, first_mismatch_index, mismatch_old, mismatch_new, new_lines
        sorted_sol, sorted_fit = original_sort(self)
        sort_step[0] += 1
        digest = TraceDigest(
            step=sort_step[0],
            phase="sort",
            digest=_digest_solution(sorted_sol[0]),
            best_fit=int(sorted_fit[0]),
        )
        new_lines += 1
        if trace_match:
            expected = _read_expected_digest()
            if expected is None:
                trace_match = False
                first_mismatch_index = compare_idx
                mismatch_old = None
                mismatch_new = digest
            elif expected != digest:
                trace_match = False
                first_mismatch_index = compare_idx
                mismatch_old = expected
                mismatch_new = digest
            compare_idx += 1
        return sorted_sol, sorted_fit

    BSMAV1008Core.repair = wrapped_repair  # type: ignore[method-assign]
    BSMAV1008Core.sort_pop = wrapped_sort  # type: ignore[method-assign]
    solver = BSMAV1008Solver()
    config: dict[str, Any] = {
        "solver_id": "bsma_v1_008",
        "stop_condition": {"type": "max_iterations", "max_iterations": max_iterations},
        "run_seed": seed,
    }
    try:
        run_result = solver.solve(problem=problem, config=config, rng=np.random.default_rng(seed))
    finally:
        BSMAV1008Core.repair = original_repair
        BSMAV1008Core.sort_pop = original_sort

    new_stop_reason = str(run_result.stop_reason)
    new_reported_eval_count = int(run_result.evaluation_count)

    if trace_match:
        extra_line = expected_handle.readline()
        if extra_line:
            trace_match = False
            first_mismatch_index = compare_idx
            mismatch_old = _trace_digest_from_line(extra_line.rstrip("\n"))
            mismatch_new = None

    expected_handle.close()

    return (
        int(run_result.best_objective),
        np.asarray(run_result.best_solution, dtype=int),
        int(new_lines),
        bool(trace_match),
        first_mismatch_index,
        mismatch_old,
        mismatch_new,
        new_stop_reason,
        new_reported_eval_count,
    )


def verify_equivalence_streaming(
    *,
    repo_root: Path,
    dataset: str,
    problem_id: str,
    seed: int,
    max_iterations: int,
    trace_dir: Path,
    problem: ProblemModel | None = None,
    include_loop_meta: bool = False,
) -> EquivalenceReport:
    """將 old trace 寫入 jsonl 後再跑 new 逐行比對，避免在記憶體中累積十萬級 trace。"""
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_path = trace_dir / f"{dataset}_{problem_id}_old_trace.jsonl"
    if problem is None:
        problem = _build_problem_from_yaml(repo_root, dataset, problem_id)

    old_fit, old_sol, old_len = _run_old_with_trace_stream_to_file(
        problem, seed, max_iterations, repo_root, trace_path
    )
    (
        new_fit,
        new_sol,
        new_len,
        trace_match,
        first_idx,
        mismatch_old,
        mismatch_new,
        new_stop_reason,
        new_reported_eval_count,
    ) = _run_new_with_trace_stream_compare_file(problem, seed, max_iterations, trace_path)

    loop_meta_new: list[dict[str, Any]] | None = None
    if include_loop_meta:
        loop_meta_new = _capture_new_loop_meta(problem, seed, max_iterations)

    return EquivalenceReport(
        dataset=dataset,
        problem_id=problem_id,
        seed=int(seed),
        max_iterations=int(max_iterations),
        final_objective_old=old_fit,
        final_objective_new=new_fit,
        final_solution_match=bool(np.array_equal(old_sol, new_sol)),
        trace_length_old=int(old_len),
        trace_length_new=int(new_len),
        trace_match=bool(trace_match),
        first_mismatch_index=first_idx,
        first_mismatch_old=mismatch_old,
        first_mismatch_new=mismatch_new,
        loop_meta_new=loop_meta_new,
        new_stop_reason=new_stop_reason,
        new_reported_eval_count=new_reported_eval_count,
    )


def verify_equivalence(
    *,
    repo_root: Path,
    dataset: str,
    problem_id: str,
    seed: int,
    max_iterations: int = 30,
    include_loop_meta: bool = False,
    problem: ProblemModel | None = None,
) -> EquivalenceReport:
    if problem is None:
        problem = _build_problem_from_yaml(repo_root, dataset, problem_id)
    old_fit, old_sol, old_trace = _run_old_with_trace(problem, seed, max_iterations, repo_root)
    new_fit, new_sol, new_trace = _run_new_with_trace(problem, seed, max_iterations)

    first_mismatch_index: int | None = None
    mismatch_old: TraceDigest | None = None
    mismatch_new: TraceDigest | None = None
    trace_match = True

    for idx, (old_item, new_item) in enumerate(zip(old_trace, new_trace)):
        if old_item != new_item:
            first_mismatch_index = idx
            mismatch_old = old_item
            mismatch_new = new_item
            trace_match = False
            break

    if trace_match and len(old_trace) != len(new_trace):
        trace_match = False
        first_mismatch_index = min(len(old_trace), len(new_trace))
        mismatch_old = old_trace[first_mismatch_index] if first_mismatch_index < len(old_trace) else None
        mismatch_new = new_trace[first_mismatch_index] if first_mismatch_index < len(new_trace) else None

    loop_meta_new: list[dict[str, Any]] | None = None
    if include_loop_meta:
        loop_meta_new = _capture_new_loop_meta(problem, seed, max_iterations)

    return EquivalenceReport(
        dataset=dataset,
        problem_id=problem_id,
        seed=int(seed),
        max_iterations=int(max_iterations),
        final_objective_old=old_fit,
        final_objective_new=new_fit,
        final_solution_match=bool(np.array_equal(old_sol, new_sol)),
        trace_length_old=len(old_trace),
        trace_length_new=len(new_trace),
        trace_match=trace_match,
        first_mismatch_index=first_mismatch_index,
        first_mismatch_old=mismatch_old,
        first_mismatch_new=mismatch_new,
        loop_meta_new=loop_meta_new,
        new_stop_reason=None,
        new_reported_eval_count=None,
    )


def write_equivalence_report(
    *,
    repo_root: Path,
    dataset: str,
    problem_id: str,
    seed: int,
    max_iterations: int = 30,
    output_path: Path | None = None,
    include_loop_meta: bool = False,
) -> Path:
    report = verify_equivalence(
        repo_root=repo_root,
        dataset=dataset,
        problem_id=problem_id,
        seed=seed,
        max_iterations=max_iterations,
        include_loop_meta=include_loop_meta,
    )
    if output_path is None:
        output_path = repo_root / "output/stage1_validation" / "bsma_equivalence_report.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(report), ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
