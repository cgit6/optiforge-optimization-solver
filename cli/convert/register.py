from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from ...converter import parse_weish_dat

ConverterFn = Callable[[Path], dict[str, Any]]

_CONVERTERS: dict[str, ConverterFn] = {}


def register_converter(name: str) -> Callable[[ConverterFn], ConverterFn]:
    normalized = name.strip()
    if not normalized:
        raise ValueError("converter name cannot be empty")

    def decorator(func: ConverterFn) -> ConverterFn:
        if normalized in _CONVERTERS:
            raise ValueError(f"Converter already registered: {normalized}")
        _CONVERTERS[normalized] = func
        return func

    return decorator


def get_converter(name: str) -> ConverterFn:
    normalized = name.strip()
    try:
        return _CONVERTERS[normalized]
    except KeyError as exc:
        raise KeyError(f"Unknown converter: {normalized}") from exc


def list_converters() -> tuple[str, ...]:
    return tuple(sorted(_CONVERTERS.keys()))


register_converter("weish")(parse_weish_dat)
