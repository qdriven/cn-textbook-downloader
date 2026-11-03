import asyncio
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from textual.worker_manager import WorkerManager

from cn_textbook_downloader.core.files import FileItem
from cn_textbook_downloader.tui.download_app import DownloaderApp


def _blob_sha(data: bytes) -> str:
    digest = hashlib.sha1(f"blob {len(data)}\0".encode())
    digest.update(data)
    return digest.hexdigest()


class FakeSource:
    repo = "example/repo"
    branch = "main"
    revision = "deadbeef"

    def raw_url(self, item: FileItem) -> str:
        return "http://example.invalid/raw/" + item.path


class FakeResponse:
    def __init__(self, data: bytes):
        self._data = data
        self._offset = 0
        self.status = 200
        self.headers = {}

    def read(self, size: int = -1) -> bytes:
        if self._offset >= len(self._data):
            return b""
        chunk = self._data[self._offset :]
        if size is not None and size >= 0:
            chunk = self._data[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class DownloaderAppTests(TestCase):
    def test_worker_count_does_not_shadow_textual_worker_manager(self):
        """回归：自定义的 _workers 会覆盖 Textual 的 WorkerManager，退出时崩溃。"""
        app = DownloaderApp(
            FakeSource(), [], Path("unused"),
            workers=4, retries=0, timeout=1, fast_skip=False, merge=False,
        )
        self.assertIsInstance(app.workers, WorkerManager)

    def test_downloads_and_exits_cleanly(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            content = b"hello"
            item = FileItem("a.txt", len(content), _blob_sha(content))
            app = DownloaderApp(
                FakeSource(), [item], root,
                workers=1, retries=0, timeout=1, fast_skip=False, merge=False,
            )

            async def run() -> None:
                async with app.run_test() as pilot:
                    for _ in range(200):
                        if app._exit_renderables or not app.is_running:
                            break
                        await pilot.pause(0.02)

            with patch("urllib.request.urlopen", return_value=FakeResponse(content)):
                asyncio.run(run())
            self.assertEqual((root / "a.txt").read_bytes(), content)
