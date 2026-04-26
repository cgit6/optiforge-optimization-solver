from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

ConverterFn = Callable[[Path], dict[str, Any]]

_CONVERTER_REGISTRY: dict[str, ConverterFn] = {}


def register_converter(name: str) -> Callable[[ConverterFn], ConverterFn]:
    """Register a converter function by name."""
    normalized = name.strip()
    if not normalized:
        raise ValueError("converter name cannot be empty")

    def decorator(func: ConverterFn) -> ConverterFn:
        if normalized in _CONVERTER_REGISTRY:
            raise ValueError(f"Converter '{normalized}' already registered")
        _CONVERTER_REGISTRY[normalized] = func
        return func

    return decorator


def get_converter(name: str) -> ConverterFn:
    normalized = name.strip()
    if normalized not in _CONVERTER_REGISTRY:
        raise KeyError(f"Unknown converter: {normalized}")
    return _CONVERTER_REGISTRY[normalized]


def list_converters() -> tuple[str, ...]:
    return tuple(sorted(_CONVERTER_REGISTRY.keys()))
