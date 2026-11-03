"""下载来源注册表：目前只有 GitHub，直接把 download/resume/test 注册到根命令。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .github import GitHubSource

if TYPE_CHECKING:
    import typer


def register_sources(app: "typer.Typer") -> None:
    """把各来源的 download/resume/test 命令注册到应用。"""
    GitHubSource.register(app)
