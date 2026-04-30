@dataclass(frozen=True)
class StubMaxIterationsSolver:
    """Simple solver for contract tests."""

    def solve(self, problem: ProblemModel, config: dict[str, Any], rng: np.random.Generator) -> RunResult:
        stop_condition = config.get("stop_condition", {})
        if stop_condition.get("type") != "max_iterations":
            raise ValueError("StubMaxIterationsSolver only supports stop_condition.type=max_iterations")

        max_iterations = int(stop_condition.get("max_iterations", 0))
        if max_iterations <= 0:
            raise ValueError("max_iterations must be > 0")

        best_solution = np.zeros(problem.items, dtype=int)
        best_objective = 0
        return RunResult(
            problem_id=problem.problem_id,
            solver_id=str(config.get("solver_id", "stub_solver")),
            seed=int(rng.integers(0, np.iinfo(np.int32).max)),
            best_solution=best_solution,
            best_objective=best_objective,
            feasible=True,
            evaluation_count=max_iterations,
            stop_reason="max_iterations_reached",
            runtime=0.0,
            linprog_runtime=0.0,
            error=None,
        )