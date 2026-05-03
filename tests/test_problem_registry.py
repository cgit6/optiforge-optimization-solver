from __future__ import annotations

from mkp.engine.problem_registry import ProblemRegistry, ProblemTypeSpec, default_problem_registry


def test_default_problem_registry_lists_mkp_and_tsp() -> None:
    registry = default_problem_registry()

    assert registry.get("mkp").encoding == "binary"
    assert registry.get("tsp").direction == "min"
    assert registry.list_problem_types() == ("mkp", "tsp")


def test_problem_registry_rejects_duplicate_problem_type() -> None:
    registry = ProblemRegistry()
    spec = ProblemTypeSpec(
        problem_type="demo",
        encoding="binary",
        direction="max",
        loader=lambda data, dataset, problem_id, path: None,  # type: ignore[return-value]
        yaml_required_fields=("problem_id",),
    )

    registry.register(spec)

    try:
        registry.register(spec)
    except ValueError as exc:
        assert "already registered" in str(exc)
    else:
        raise AssertionError("duplicate problem type was accepted")
