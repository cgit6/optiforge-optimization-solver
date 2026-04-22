"""pytest 插件：從專案子目錄啟動時，自動補上 <rootdir>/tests 作為收集路徑。"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def pytest_load_initial_conftests(
    early_config: Any,
    parser: Any,
    args: list[str],
) -> None:
    root = getattr(early_config, "rootpath", None)
    if root is None:
        return
    root = Path(root).resolve()
    inv = early_config.invocation_params.dir.resolve()
    if inv == root:
        return
    ns = early_config.known_args_namespace
    if getattr(ns, "help", False) or getattr(ns, "version", False):
        return
    if ns.file_or_dir:
        return
    tests = root / "tests"
    if not tests.is_dir():
        return
    args.insert(0, str(tests))
