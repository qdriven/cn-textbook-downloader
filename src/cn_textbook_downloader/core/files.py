"""文件清单数据结构。"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass


@dataclass(frozen=True)
class FileItem:
    """仓库中的一个文件（来自 GitHub git tree API）。"""

    path: str
    size: int
    sha: str

    def to_dict(self) -> dict:
        return {"path": self.path, "size": self.size, "sha": self.sha}

    @classmethod
    def from_dict(cls, data: dict) -> "FileItem":
        return cls(path=data["path"], size=data["size"], sha=data["sha"])


def filter_files(items: list[FileItem], include: list[str] | None) -> list[FileItem]:
    """按 glob 模式过滤文件路径（fnmatch 语法，如 '小学/*'）。"""
    if not include:
        return list(items)
    return [
        item
        for item in items
        if any(fnmatch.fnmatchcase(item.path, pattern) for pattern in include)
    ]
