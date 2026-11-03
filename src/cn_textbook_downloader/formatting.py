"""通用输出与格式化工具。

log 的输出目标可通过 set_log_sink 替换（TUI 模式下重定向到界面）。
"""

from __future__ import annotations

import re
import threading
from typing import Callable

PRINT_LOCK = threading.Lock()


def _default_sink(message: str) -> None:
    with PRINT_LOCK:
        print(message, flush=True)


_sink: Callable[[str], None] = _default_sink


def set_log_sink(sink: Callable[[str], None]) -> None:
    global _sink
    _sink = sink


def restore_log_sink() -> None:
    global _sink
    _sink = _default_sink


def log(message: str) -> None:
    _sink(message)


def format_size(size: int) -> str:
    return f"{size / 1024**3:.2f} GiB" if size >= 1024**3 else f"{size / 1024**2:.2f} MiB"


def validate_repo(repo: str) -> None:
    if not re.fullmatch(r"[^/]+/[^/]+", repo):
        raise ValueError(f"仓库必须是 owner/name 格式：{repo}")
