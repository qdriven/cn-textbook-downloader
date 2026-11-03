"""下载任务的 Textual TUI。"""

from __future__ import annotations

import threading

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, ProgressBar, RichLog, Static

from ..core.downloader import DownloadEvent, DownloadReport, download_all
from ..core.merge import merge_split_pdfs
from ..formatting import format_size, restore_log_sink, set_log_sink


class DownloaderApp(App):
    """TUI：下载引擎在后台线程运行，通过 call_from_thread 更新界面。

    Ctrl+C 取消下载：.part 临时文件保留，之后可用 resume 续传。
    """

    TITLE = "ChinaTextbook 下载"
    CSS = """
    #summary {
        padding: 1 2;
        color: $text;
    }
    #current {
        padding: 0 2;
        color: $text-muted;
    }
    #log {
        border: round $accent;
        height: 1fr;
    }
    """
    BINDINGS = [Binding("ctrl+c", "quit_task", "退出")]

    def __init__(self, source, items, destination, *, workers, retries, timeout, fast_skip, merge):
        super().__init__()
        self._source = source
        self._items = list(items)
        self._destination = destination
        # 不能用 _workers：Textual 的 App._workers 是内部 WorkerManager
        self._worker_count = workers
        self._retries = retries
        self._timeout = timeout
        self._fast_skip = fast_skip
        self._merge = merge
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Static(self._summary_text(), id="summary")
        yield ProgressBar(total=len(self._items), id="progress")
        yield Static("准备开始…", id="current")
        yield RichLog(wrap=True, markup=False, id="log")
        yield Footer()

    def _summary_text(self) -> str:
        total = sum(item.size for item in self._items)
        ref = self._source.revision or self._source.branch
        return (
            f"仓库：{self._source.repo} @ {ref}\n"
            f"保存目录：{self._destination}\n"
            f"文件数：{len(self._items)}；总大小：{format_size(total)}；并发：{self._worker_count}"
        )

    def on_mount(self) -> None:
        set_log_sink(self._log_line)
        total = sum(item.size for item in self._items)
        self._log(f"开始下载：{len(self._items)} 个文件，共 {format_size(total)} → {self._destination}")
        self._thread = threading.Thread(target=self._run_engine, name="download-engine", daemon=True)
        self._thread.start()

    def on_unmount(self) -> None:
        restore_log_sink()

    def quit_task(self) -> None:
        """Ctrl+C：通知引擎停止并退出。"""
        self._cancel.set()
        if self._thread is not None:
            self._thread.join(timeout=3)
        restore_log_sink()
        self.exit(130)

    def _run_engine(self) -> None:
        def progress(event: DownloadEvent) -> None:
            self._post(self._on_progress, event)

        try:
            report = download_all(
                self._destination,
                self._source,
                self._items,
                workers=self._worker_count,
                retries=self._retries,
                timeout=self._timeout,
                fast_skip=self._fast_skip,
                progress=progress,
                cancel=self._cancel,
            )
            if self._merge and not report.interrupted:
                merged = merge_split_pdfs(self._destination)
                report.merged = merged
                self._post(self._log, f"合并完成：新增 {merged} 个 PDF；原分块未删除")
            self._post(self._on_finished, report)
        except Exception as exc:
            self._post(self._on_error, exc)

    def _post(self, callback, *args) -> None:
        try:
            self.call_from_thread(callback, *args)
        except Exception:
            pass  # App 已退出时忽略

    def _log_line(self, message: str) -> None:
        self._post(self._log, message)

    def _log(self, message: str) -> None:
        self.query_one("#log", RichLog).write(Text(message))

    def _on_progress(self, event: DownloadEvent) -> None:
        if event.phase == "start":
            self.query_one("#current", Static).update(f"正在下载：{event.current}")
        else:
            self.query_one("#progress", ProgressBar).update(progress=event.done_files)
            self.query_one("#current", Static).update(
                f"已完成 {event.done_files}/{event.total_files}；最近：{event.current}"
            )

    def _on_error(self, exc: Exception) -> None:
        self._log(f"发生错误：{exc}")
        restore_log_sink()
        self.exit(1)

    def _on_finished(self, report: DownloadReport) -> None:
        self.query_one("#progress", ProgressBar).update(progress=report.finished_files)
        if report.interrupted:
            self._log("下载已取消；.part 临时文件保留，重新运行 resume 可继续")
        self._log(
            f"完成：新下载 {report.downloaded}，跳过 {report.skipped}，失败 {len(report.failed)}"
        )
        for path, error in report.failed[:10]:
            self._log(f"失败：{path}；{error}")
        if report.failed:
            self._log("修复网络问题后运行 resume 可继续")
        restore_log_sink()
        if report.interrupted:
            self.exit(130)
            return
        code = 1 if report.failed else 0
        # 完成后停留一会儿，让进度条 100% 和汇总结果可见
        self.set_timer(1.0, lambda: self.exit(code))
