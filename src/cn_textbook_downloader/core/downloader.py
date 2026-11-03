"""并发下载引擎：断点续传、校验与取消。"""

from __future__ import annotations

import http.client
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ..errors import DownloadInterrupted
from ..formatting import log
from .files import FileItem
from .retry import retry_delay
from .verify import existing_merged_pdf_for_chunk, git_blob_sha, safe_destination, verify_part

USER_AGENT = "cn-textbook-downloader/0.1"
CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class DownloadEvent:
    """进度事件：phase 为 start（开始下载某文件）或 done（某文件完成）。"""

    phase: str
    done_files: int
    total_files: int
    current: str
    downloaded_bytes: int
    total_bytes: int


@dataclass
class DownloadReport:
    total_files: int
    total_bytes: int
    downloaded: int
    skipped: int
    downloaded_bytes: int
    failed: list[tuple[str, str]] = field(default_factory=list)
    interrupted: bool = False
    merged: int = 0

    @property
    def finished_files(self) -> int:
        return self.downloaded + self.skipped


def download_file(
    root: Path,
    source,
    item: FileItem,
    retries: int,
    timeout: int,
    fast_skip: bool,
    cancel: threading.Event | None = None,
) -> str:
    """下载单个文件，返回 "downloaded" 或 "skipped"。

    - 已完成（大小 + SHA 校验通过）的文件直接跳过，实现断点续传；
    - .part 临时文件保存中断进度，下次通过 Range 请求从断点继续；
    - 分块对应的合并 PDF 已存在时跳过该分块。
    """
    expected_size = item.size
    expected_sha = item.sha
    target = safe_destination(root, item.path)
    part = target.with_name(target.name + ".part")

    merged = existing_merged_pdf_for_chunk(target)
    if merged is not None:
        log(f"合并 PDF 已存在，跳过分块：{item.path}")
        return "skipped"

    if target.exists():
        if target.stat().st_size == expected_size:
            if fast_skip or git_blob_sha(target) == expected_sha:
                return "skipped"
            log(f"已有文件校验失败，重新下载：{item.path}")
        else:
            log(f"已有文件大小变化，重新下载：{item.path}")

    if part.exists() and part.stat().st_size > expected_size:
        part.unlink()

    url = source.raw_url(item)

    for attempt in range(retries + 1):
        if cancel is not None and cancel.is_set():
            raise DownloadInterrupted("下载已取消")
        try:
            offset = part.stat().st_size if part.exists() else 0
            if offset == expected_size:
                part.touch()
                verify_part(part, target, expected_size, expected_sha)
                return "downloaded"

            headers = {"User-Agent": USER_AGENT}
            if offset:
                headers["Range"] = f"bytes={offset}-"
            request = urllib.request.Request(url, headers=headers)

            with urllib.request.urlopen(request, timeout=timeout) as response:
                append = offset > 0 and response.status == 206
                if offset and not append:
                    offset = 0
                if append:
                    content_range = response.headers.get("Content-Range", "")
                    if not content_range.startswith(f"bytes {offset}-"):
                        raise IOError(f"服务器返回了错误的 Content-Range：{content_range}")

                with part.open("ab" if append else "wb") as file:
                    while block := response.read(CHUNK_SIZE):
                        if cancel is not None and cancel.is_set():
                            raise DownloadInterrupted("下载已取消")
                        file.write(block)

            if part.stat().st_size != expected_size:
                raise IOError(
                    f"下载不完整：{part.stat().st_size}/{expected_size} 字节，下次将继续"
                )
            verify_part(part, target, expected_size, expected_sha)
            return "downloaded"

        except DownloadInterrupted:
            raise
        except (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError, ValueError) as exc:
            if isinstance(exc, urllib.error.HTTPError) and exc.code == 416:
                part.unlink(missing_ok=True)
            if attempt >= retries:
                raise
            response = exc if isinstance(exc, urllib.error.HTTPError) else None
            delay = retry_delay(attempt, response)
            log(f"失败后将重试：{item.path}；{delay:.0f} 秒后；{exc}")
            time.sleep(delay)

    raise RuntimeError(f"下载失败：{item.path}")


def download_all(
    root: Path,
    source,
    items: list[FileItem],
    *,
    workers: int,
    retries: int,
    timeout: int,
    fast_skip: bool,
    progress: Callable[[DownloadEvent], None] | None = None,
    cancel: threading.Event | None = None,
) -> DownloadReport:
    """并发下载全部文件。progress 回调可来自任意线程（TUI 负责线程安全）。"""
    total_files = len(items)
    total_bytes = sum(item.size for item in items)
    counts = {"downloaded": 0, "skipped": 0}
    done_bytes = 0
    failed: list[tuple[str, str]] = []
    interrupted = False

    def emit(phase: str, path: str) -> None:
        if progress is None:
            return
        progress(
            DownloadEvent(
                phase=phase,
                done_files=counts["downloaded"] + counts["skipped"],
                total_files=total_files,
                current=path,
                downloaded_bytes=done_bytes,
                total_bytes=total_bytes,
            )
        )

    def worker(item: FileItem) -> str:
        emit("start", item.path)
        return download_file(root, source, item, retries, timeout, fast_skip, cancel)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(worker, item): item for item in items}
        try:
            for future in as_completed(futures):
                item = futures[future]
                try:
                    result = future.result()
                    counts[result] += 1
                    done_bytes += item.size
                    emit("done", item.path)
                except DownloadInterrupted:
                    interrupted = True
                except Exception as exc:
                    failed.append((item.path, str(exc)))
                    log(f"最终失败：{item.path}；{exc}")
                    emit("done", item.path)
        finally:
            if interrupted and cancel is not None:
                executor.shutdown(wait=False, cancel_futures=True)

    return DownloadReport(
        total_files=total_files,
        total_bytes=total_bytes,
        downloaded=counts["downloaded"],
        skipped=counts["skipped"],
        downloaded_bytes=done_bytes,
        failed=failed,
        interrupted=interrupted,
    )
