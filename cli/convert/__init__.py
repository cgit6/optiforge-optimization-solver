"""題庫轉換 CLI：解析命令列並選擇轉換函數。"""

from __future__ import annotations

from ...converter import getConverter, listConverters, register as _register
from .main import build, main
from .register import parseCb, parseGk, parseHp, parsePb, parsePet, parseSent, parseWeing, parseWeish

register = _register

__all__ = [
    "build",
    "getConverter",
    "listConverters",
    "main",
    "parseCb",
    "parseGk",
    "parseHp",
    "parsePb",
    "parsePet",
    "parseSent",
    "parseWeing",
    "parseWeish",
    "register", # 註冊
]
