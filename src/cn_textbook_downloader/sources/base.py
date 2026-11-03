"""下载来源的基类接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..core.files import FileItem


class Source(ABC):
    """一个下载来源（如 GitHub）需要实现两个能力：

    1. resolve：把用户指定的位置解析为固定版本 + 文件清单；
    2. raw_url：为清单中的每个文件生成下载地址。

    新增来源时继承本类，并在命令层接入（参考 ``sources/github.py`` 的
    ``download`` / ``resume`` / ``test`` 实现）。
    """

    name: str = ""

    @abstractmethod
    def resolve(self) -> tuple[str, list[FileItem]]:
        """返回 (版本标识, 文件清单)。"""

    @abstractmethod
    def raw_url(self, item: FileItem) -> str:
        """返回文件的下载地址。"""
