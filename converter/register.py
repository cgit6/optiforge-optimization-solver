from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any
# 定義解析函數的介面(輸入: 題目路徑, 輸出: ???)
ConverterFn = Callable[[Path], dict[str, Any]]

# 內部的解析函數表
_CONVERTERS: dict[str, ConverterFn] = {}

# 註冊解析函數到 _CONVERTERS 表中
def register(name: str) -> Callable[[ConverterFn], ConverterFn]:
    normalized = name.strip()
    if not normalized:
        raise ValueError("converter name cannot be empty")

    def decorator(func: ConverterFn) -> ConverterFn:
        if normalized in _CONVERTERS:
            raise ValueError(f"Converter already registered: {normalized}")
        _CONVERTERS[normalized] = func
        return func

    return decorator

# 利用命令行參數來找解析函數
def getConverter(name: str) -> ConverterFn:
    normalized = name.strip()
    try:
        return _CONVERTERS[normalized]
    except KeyError as exc:
        raise KeyError(f"未知的解析 key 值: {normalized}") from exc

# 獲取解析函數清單
def listConverters() -> tuple[str, ...]:
    return tuple(sorted(_CONVERTERS.keys()))
