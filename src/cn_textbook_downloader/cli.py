"""命令行入口：typer 应用，download / resume / test 三个主命令。"""

from __future__ import annotations

import sys
from typing import Annotated

import typer

from . import __version__
from .sources import register_sources

app = typer.Typer(
    name="cn-textbook",
    help="下载 ChinaTextbook 教材仓库：支持断点续传、校验与 PDF 分块合并。",
    no_args_is_help=True,
    add_completion=False,
)

register_sources(app)


@app.callback(invoke_without_command=True)
def _root(
    version: Annotated[bool, typer.Option("--version", help="显示版本号")] = False,
) -> None:
    """下载教材仓库的命令行工具。"""
    if version:
        typer.echo(f"cn-textbook {__version__}")
        raise typer.Exit(0)


def main() -> None:
    # 输出被重定向或非交互运行时（例如录制终端演示），Windows 会把 Python 的
    # 文本输出回退到本地代码页（中文系统为 gbk），中文会变成乱码。
    # 这里统一把标准输出/标准错误切到 UTF-8，保证中文在任何场景下都正常显示。
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass
    try:
        app()
    except KeyboardInterrupt:
        from .formatting import log

        log("已中断；重新运行 resume 可继续。")
        raise SystemExit(130)
