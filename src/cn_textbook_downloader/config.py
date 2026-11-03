"""下载选项。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DownloadOptions:
    repo: str = "TapXWorld/ChinaTextbook"
    branch: str = "master"
    destination: Path = Path("ChinaTextbook")
    workers: int = 4
    retries: int = 8
    timeout: int = 60
    include: list[str] = field(default_factory=list)
    fast_skip: bool = False
    merge: bool = False
    token: str | None = None
