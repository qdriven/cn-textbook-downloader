"""GitHub 下载来源：download / resume / test 三个子命令的实现。"""

from __future__ import annotations

import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Annotated, Optional

import typer

from ..config import DownloadOptions
from ..core.downloader import DownloadReport, download_all
from ..core.files import FileItem, filter_files
from ..core.github_api import list_tree, resolve_branch_sha
from ..core.merge import merge_split_pdfs
from ..core.verify import git_blob_sha, safe_destination
from ..formatting import format_size, log, validate_repo
from ..state import Manifest, load_manifest, manifest_path, save_manifest
from .base import Source

RepoOption = Annotated[str, typer.Option("--repo", help="GitHub 仓库，格式 owner/name")]
BranchOption = Annotated[str, typer.Option("--branch", help="分支或标签")]
DestinationOption = Annotated[Path, typer.Option("--dest", help="保存目录")]
IncludeOption = Annotated[Optional[list[str]], typer.Option("--include", help="只处理匹配的路径，可重复，如 --include '小学/*'")]
WorkersOption = Annotated[int, typer.Option("--workers", min=1, help="并发数")]
RetriesOption = Annotated[int, typer.Option("--retries", min=0, help="每个文件的重试次数")]
TimeoutOption = Annotated[int, typer.Option("--timeout", min=1, help="网络超时秒数")]
FastSkipOption = Annotated[bool, typer.Option("--fast-skip", help="已有文件只检查大小，跳过 SHA 校验")]
MergeOption = Annotated[bool, typer.Option("--merge", help="下载完成后合并 PDF 分块")]
TokenOption = Annotated[Optional[str], typer.Option("--token", envvar="GITHUB_TOKEN", help="GitHub 令牌，也可通过 GITHUB_TOKEN 环境变量设置")]
NoTuiOption = Annotated[bool, typer.Option("--no-tui", help="不使用 TUI，使用普通日志输出")]


class GitHubSource(Source):
    name = "github"

    def __init__(self, repo: str, branch: str, token: str | None = None, retries: int = 8, timeout: int = 60):
        self.repo = repo
        self.branch = branch
        self.token = token
        self.retries = retries
        self.timeout = timeout
        self.revision: str | None = None

    def resolve(self) -> tuple[str, list[FileItem]]:
        self.revision = resolve_branch_sha(self.repo, self.branch, self.token, self.retries, self.timeout)
        items = list_tree(self.repo, self.revision, self.token, self.retries, self.timeout)
        return self.revision, items

    def raw_url(self, item: FileItem) -> str:
        ref = self.revision or self.branch
        encoded_ref = urllib.parse.quote(ref, safe="")
        encoded_path = urllib.parse.quote(item.path, safe="/")
        return f"https://raw.githubusercontent.com/{self.repo}/{encoded_ref}/{encoded_path}"

    @classmethod
    def from_manifest(cls, manifest: Manifest, token: str | None = None) -> "GitHubSource":
        """从任务清单恢复来源：固定版本，无需访问 API。"""
        source = cls(manifest.repo, manifest.branch, token)
        source.revision = manifest.revision
        return source

    @staticmethod
    def register(app: typer.Typer) -> None:
        """注册 download / resume / test 三个命令。"""

        @app.command("download")
        def download(
            repo: RepoOption = "qdriven/ChinaTextbook",
            branch: BranchOption = "master",
            destination: DestinationOption = Path("ChinaTextbook"),
            include: IncludeOption = None,
            workers: WorkersOption = 4,
            retries: RetriesOption = 8,
            timeout: TimeoutOption = 60,
            fast_skip: FastSkipOption = False,
            merge: MergeOption = False,
            token: TokenOption = None,
            no_tui: NoTuiOption = False,
            dry_run: Annotated[bool, typer.Option("--dry-run", help="只列出匹配的文件，不下载")] = False,
        ) -> None:
            """从 GitHub 仓库下载教材（默认 TUI 模式，自动断点续传）。"""
            try:
                validate_repo(repo)
            except ValueError as exc:
                raise typer.BadParameter(str(exc)) from exc

            options = DownloadOptions(
                repo=repo, branch=branch, destination=destination,
                workers=workers, retries=retries, timeout=timeout,
                fast_skip=fast_skip, merge=merge, token=token,
                include=include or [],
            )
            source = GitHubSource(repo, branch, token, retries, timeout)
            revision, files = source.resolve()
            items = filter_files(files, options.include)
            if not items:
                raise typer.BadParameter("没有匹配的文件")

            total = sum(item.size for item in items)
            log(f"仓库：{repo}；分支：{branch}；匹配文件：{len(items)}；总大小：{format_size(total)}")
            if dry_run:
                for item in sorted(items, key=lambda i: i.path):
                    print(f"{item.size:>12}  {item.path}")
                raise typer.Exit(0)

            if load_manifest(destination) is not None:
                log(f"目录中已有任务清单，将覆盖并开始新任务：{manifest_path(destination)}")
            destination.mkdir(parents=True, exist_ok=True)
            save_manifest(destination, Manifest(repo=repo, branch=branch, revision=revision, files=items))
            log(f"任务清单已保存：{manifest_path(destination)}")

            code = _execute_download(source, items, destination, options, no_tui)
            raise typer.Exit(code)

        @app.command("resume")
        def resume(
            destination: DestinationOption = Path("ChinaTextbook"),
            include: IncludeOption = None,
            workers: WorkersOption = 4,
            retries: RetriesOption = 8,
            timeout: TimeoutOption = 60,
            fast_skip: FastSkipOption = False,
            merge: MergeOption = False,
            token: TokenOption = None,
            no_tui: NoTuiOption = False,
        ) -> None:
            """继续未完成的下载任务：从任务清单记录的版本和断点位置继续。"""
            manifest = load_manifest(destination)
            if manifest is None:
                raise typer.BadParameter(
                    f"未找到任务清单：{manifest_path(destination)}；请先运行 download"
                )
            source = GitHubSource.from_manifest(manifest, token)
            items = filter_files(manifest.files, include)
            options = DownloadOptions(
                destination=destination, workers=workers, retries=retries,
                timeout=timeout, fast_skip=fast_skip, merge=merge, token=token,
            )
            log(f"继续任务：{manifest.repo} @ {manifest.revision}；文件 {len(items)} 个")
            code = _execute_download(source, items, destination, options, no_tui)
            raise typer.Exit(code)

        @app.command("test")
        def test(
            destination: DestinationOption = Path("ChinaTextbook"),
            repo: RepoOption = "qdriven/ChinaTextbook",
            branch: BranchOption = "master",
            include: IncludeOption = None,
            verify_hashes: Annotated[bool, typer.Option("--verify-hashes", help="计算每个文件的 Git blob SHA 并校验")] = False,
            workers: WorkersOption = 8,
            token: TokenOption = None,
            retries: RetriesOption = 8,
            timeout: TimeoutOption = 60,
        ) -> None:
            """校验已下载的文件：存在性、大小，可选 SHA。"""
            from rich.console import Console
            from rich.table import Table

            console = Console()
            manifest = load_manifest(destination)
            if manifest is not None:
                source = GitHubSource.from_manifest(manifest, token)
                items = filter_files(manifest.files, include)
                log(f"使用任务清单：{manifest_path(destination)}")
            else:
                try:
                    validate_repo(repo)
                except ValueError as exc:
                    raise typer.BadParameter(str(exc)) from exc
                source = GitHubSource(repo, branch, token, retries, timeout)
                revision, files = source.resolve()
                items = filter_files(files, include)
                if not items:
                    raise typer.BadParameter("没有匹配的文件")
                log(f"未找到任务清单，已从 {repo} @ {revision} 解析文件清单")
            if not items:
                raise typer.BadParameter("没有匹配的文件")

            log(f"检查 {len(items)} 个文件 → {destination}")
            results: dict[str, str] = {}
            if verify_hashes:
                with ThreadPoolExecutor(max_workers=workers) as executor:
                    futures = {
                        executor.submit(_check_item, destination, item, True): item
                        for item in items
                    }
                    checked = 0
                    for future in as_completed(futures):
                        item = futures[future]
                        results[item.path] = future.result()[0]
                        checked += 1
                        if checked % 50 == 0:
                            log(f"已校验 {checked}/{len(items)}")
            else:
                for item in items:
                    results[item.path] = _check_item(destination, item, False)[0]

            missing = [path for path, status in results.items() if status == "missing"]
            size_bad = [path for path, status in results.items() if status == "size"]
            hash_bad = [path for path, status in results.items() if status == "hash"]
            ok = len(results) - len(missing) - len(size_bad) - len(hash_bad)

            table = Table(title=f"校验结果：{source.repo} @ {source.revision or source.branch}", expand=True)
            table.add_column("状态", style="bold")
            table.add_column("文件")
            for path in missing:
                table.add_row("[red]缺失[/red]", path)
            for path in size_bad:
                table.add_row("[yellow]大小不符[/yellow]", path)
            for path in hash_bad:
                table.add_row("[magenta]SHA 不符[/magenta]", path)
            problem_count = len(missing) + len(size_bad) + len(hash_bad)
            if problem_count > 20:
                table.add_row("[dim]…[/dim]", f"其余 {problem_count - 20} 个问题省略")
            console.print(table)

            summary = Table.grid(padding=(0, 2))
            summary.add_column(style="bold")
            summary.add_column()
            summary.add_row("总计", str(len(items)))
            summary.add_row("正常", f"[green]{ok}[/green]")
            summary.add_row("缺失", f"[red]{len(missing)}[/red]" if missing else "0")
            summary.add_row("大小不符", f"[yellow]{len(size_bad)}[/yellow]" if size_bad else "0")
            summary.add_row("SHA 不符", f"[magenta]{len(hash_bad)}[/magenta]" if hash_bad else "0")
            console.print(summary)

            if problem_count:
                log(f"发现 {problem_count} 个问题；修复后可重新运行 test 或 download 验证")
                raise typer.Exit(1)
            log("全部通过")


def _check_item(destination: Path, item: FileItem, verify_hashes: bool) -> tuple[str, int]:
    target = safe_destination(destination, item.path)
    if not target.is_file():
        return "missing", 0
    if target.stat().st_size != item.size:
        return "size", 0
    if verify_hashes and git_blob_sha(target) != item.sha:
        return "hash", 0
    return "ok", item.size


def _execute_download(source: GitHubSource, items: list[FileItem], destination: Path, options: DownloadOptions, no_tui: bool) -> int:
    total = sum(item.size for item in items)
    log(f"版本：{source.repo} @ {source.revision or source.branch}")
    log(f"保存目录：{destination}")
    log(f"文件数：{len(items)}；总大小：{format_size(total)}；并发：{options.workers}")

    if no_tui:
        report = download_all(
            destination, source, items,
            workers=options.workers, retries=options.retries,
            timeout=options.timeout, fast_skip=options.fast_skip,
        )
        _report_result(report, merge=options.merge, destination=destination)
        return _exit_code(report)

    from ..tui.download_app import DownloaderApp

    app = DownloaderApp(
        source, items, destination,
        workers=options.workers, retries=options.retries,
        timeout=options.timeout, fast_skip=options.fast_skip,
        merge=options.merge,
    )
    return int(app.run() or 0)


def _report_result(report: DownloadReport, *, merge: bool, destination: Path) -> None:
    log(
        f"下载结束：新下载 {report.downloaded}，跳过 {report.skipped}，失败 {len(report.failed)}"
    )
    if report.interrupted:
        log("下载已取消；.part 临时文件保留，运行 resume 可继续")
    if report.failed:
        examples = "；".join(f"{path}: {error}" for path, error in report.failed[:5])
        log(f"有 {len(report.failed)} 个文件失败，可重新运行 resume 续传。示例：{examples}")
    if merge and not report.interrupted:
        merged = merge_split_pdfs(destination)
        log(f"合并完成：新增 {merged} 个 PDF；原分块未删除")


def _exit_code(report: DownloadReport) -> int:
    if report.interrupted:
        return 130
    return 1 if report.failed else 0
