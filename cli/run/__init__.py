"""模擬批次主入口：CLI 解析、驗證與 `executeSimulator` 編排。"""

from __future__ import annotations

from .main import main
from .support import (
    build_parser,
    createExperimentSpec,
    executeSimulator,
    parser,
    validate_execute_args,
)

__all__ = [
    "createExperimentSpec",
    "build_parser",
    "executeSimulator",
    "main",
    "parser",
    "validate_execute_args",
]
