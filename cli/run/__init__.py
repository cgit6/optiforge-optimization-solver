"""模擬批次主入口：CLI 解析、驗證與 `executeSimulator` 編排。"""

from __future__ import annotations

from .main import parser, create_experiment_spec, main
from .support import (
    executeSimulator,
    preflight_validate,
    validate_execute_args,
)

__all__ = [
    "parser",
    "create_experiment_spec",
    "executeSimulator",
    "main",
    "preflight_validate",
    "validate_execute_args",
]
