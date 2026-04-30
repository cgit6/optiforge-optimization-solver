"""題庫轉換 CLI：解析命令列並選擇轉換函數。"""

from __future__ import annotations

from .main import build_parser, main
from .register import get_converter, list_converters, register_converter

__all__ = [
    "build_parser",
    "get_converter",
    "list_converters",
    "main",
    "register_converter",
]
