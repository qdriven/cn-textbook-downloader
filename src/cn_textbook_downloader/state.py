"""任务清单（manifest）：记录下载任务的仓库、版本与文件列表，供 resume 使用。

manifest 保存在目标目录的 .cn-textbook-downloader/manifest.json，
resume 命令据此固定下载版本，无需重新解析 GitHub API。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .core.files import FileItem

MANIFEST_DIR = ".cn-textbook-downloader"
MANIFEST_FILE = "manifest.json"


def manifest_path(destination: Path) -> Path:
    return destination / MANIFEST_DIR / MANIFEST_FILE


@dataclass
class Manifest:
    repo: str
    branch: str
    revision: str
    files: list[FileItem]
    created: str = ""
    updated: str = ""

    def to_dict(self) -> dict:
        return {
            "repo": self.repo,
            "branch": self.branch,
            "revision": self.revision,
            "created": self.created,
            "updated": self.updated,
            "files": [item.to_dict() for item in self.files],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Manifest":
        return cls(
            repo=data["repo"],
            branch=data["branch"],
            revision=data["revision"],
            created=data.get("created", ""),
            updated=data.get("updated", ""),
            files=[FileItem.from_dict(item) for item in data["files"]],
        )


def save_manifest(destination: Path, manifest: Manifest) -> Path:
    path = manifest_path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    manifest.updated = now
    if not manifest.created:
        manifest.created = now
    payload = json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)
    return path


def load_manifest(destination: Path) -> Manifest | None:
    path = manifest_path(destination)
    if not path.is_file():
        return None
    return Manifest.from_dict(json.loads(path.read_text(encoding="utf-8")))
