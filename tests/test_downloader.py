import hashlib
import threading
import urllib.error
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from cn_textbook_downloader.core.downloader import download_all, download_file
from cn_textbook_downloader.core.files import FileItem
from cn_textbook_downloader.core.verify import git_blob_sha


def _blob_sha(data: bytes) -> str:
    digest = hashlib.sha1(f"blob {len(data)}\0".encode())
    digest.update(data)
    return digest.hexdigest()


class FakeSource:
    """测试用的下载来源：URL 由文件路径拼接，不发起真实网络请求。"""

    def __init__(self, prefix: str = "http://example.invalid/raw/"):
        self._prefix = prefix

    def raw_url(self, item: FileItem) -> str:
        return self._prefix + item.path


class FakeResponse:
    def __init__(self, data: bytes, status: int = 200, headers: dict | None = None):
        self._data = data
        self._offset = 0
        self.status = status
        self.headers = headers or {}

    def read(self, size: int = -1) -> bytes:
        if self._offset >= len(self._data):
            return b""
        if size is None or size < 0:
            chunk = self._data[self._offset:]
        else:
            chunk = self._data[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class DownloadFileTests(TestCase):
    def test_existing_merged_pdf_prevents_network(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "sample.pdf").write_bytes(b"%PDF-test")
            item = FileItem(path="sample.pdf.1", size=4, sha="unused")
            with patch("urllib.request.urlopen", side_effect=AssertionError("不应发起下载")):
                result = download_file(root, FakeSource(), item, 0, 1, False)
            self.assertEqual(result, "skipped")
            self.assertFalse((root / "sample.pdf.1").exists())

    def test_existing_valid_file_skips(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            content = b"hello"
            (root / "sample.txt").write_bytes(content)
            item = FileItem(path="sample.txt", size=5, sha=git_blob_sha(root / "sample.txt"))
            with patch("urllib.request.urlopen", side_effect=AssertionError("不应发起下载")):
                result = download_file(root, FakeSource(), item, 0, 1, False)
            self.assertEqual(result, "skipped")

    def test_existing_file_wrong_sha_redownloads(self):
        """已有文件大小相同但内容不符时重新下载。"""
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            correct = b"correct!"
            wrong = b"wrong-!!"  # 与 correct 同为 8 字节，SHA 不同
            (root / "sample.txt").write_bytes(wrong)
            item = FileItem(path="sample.txt", size=len(correct), sha=_blob_sha(correct))
            response = FakeResponse(correct)
            with patch("urllib.request.urlopen", return_value=response):
                result = download_file(root, FakeSource(), item, 0, 1, False)
            self.assertEqual(result, "downloaded")
            self.assertEqual((root / "sample.txt").read_bytes(), correct)

    def test_resume_from_partial(self):
        """断点续传：.part 已有部分内容时，Range 请求补齐剩余部分。"""
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            content = bytes(range(256)) * 4  # 1024 字节
            (root / "sample.txt.part").write_bytes(content[:100])
            item = FileItem(path="sample.txt", size=len(content), sha=_blob_sha(content))
            remaining = content[100:]
            response = FakeResponse(
                remaining,
                status=206,
                headers={"Content-Range": f"bytes 100-{len(content) - 1}/{len(content)}"},
            )
            with patch("urllib.request.urlopen", return_value=response) as opener:
                result = download_file(root, FakeSource(), item, 0, 1, False)
            self.assertEqual(result, "downloaded")
            self.assertEqual((root / "sample.txt").read_bytes(), content)
            request = opener.call_args.args[0]
            self.assertEqual(request.headers["Range"], "bytes=100-")

    def test_retries_then_succeeds(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            content = b"retry-me"
            item = FileItem(path="sample.txt", size=len(content), sha=_blob_sha(content))
            response = FakeResponse(content)
            with (
                patch("urllib.request.urlopen", side_effect=[urllib.error.URLError("boom"), response]),
                patch("cn_textbook_downloader.core.downloader.time.sleep"),
            ):
                result = download_file(root, FakeSource(), item, 2, 1, False)
            self.assertEqual(result, "downloaded")


class DownloadAllTests(TestCase):
    def test_download_all_counts(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            contents = {"a.txt": b"aaa", "b.txt": b"bbbb"}
            items = [FileItem(path, len(data), _blob_sha(data)) for path, data in contents.items()]

            def fake_urlopen(request, timeout=None):
                name = request.full_url.rsplit("/", 1)[-1]
                return FakeResponse(contents[name])

            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                report = download_all(
                    root, FakeSource(), items, workers=2, retries=0, timeout=1, fast_skip=False
                )
            self.assertEqual(report.downloaded, 2)
            self.assertEqual(report.failed, [])
            self.assertEqual((root / "a.txt").read_bytes(), b"aaa")
            self.assertEqual((root / "b.txt").read_bytes(), b"bbbb")

    def test_cancel_marks_interrupted(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            items = [FileItem("a.txt", 3, _blob_sha(b"aaa"))]
            cancel = threading.Event()
            cancel.set()
            report = download_all(
                root, FakeSource(), items, workers=1, retries=0, timeout=1,
                fast_skip=False, cancel=cancel,
            )
            self.assertTrue(report.interrupted)
            self.assertFalse((root / "a.txt").exists())
