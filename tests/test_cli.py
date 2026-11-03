import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from typer.testing import CliRunner

from cn_textbook_downloader.cli import app
from cn_textbook_downloader.core.files import FileItem
from cn_textbook_downloader.state import Manifest, save_manifest


def _blob_sha(data: bytes) -> str:
    digest = hashlib.sha1(f"blob {len(data)}\0".encode())
    digest.update(data)
    return digest.hexdigest()


runner = CliRunner()


class CliTests(TestCase):
    def test_root_help(self):
        result = runner.invoke(app, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("download", result.output)
        self.assertIn("resume", result.output)
        self.assertIn("test", result.output)

    def test_version(self):
        result = runner.invoke(app, ["--version"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("cn-textbook", result.output)

    def test_download_github_help(self):
        result = runner.invoke(app, ["download", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("--repo", result.output)
        self.assertIn("--dest", result.output)

    def test_resume_github_help(self):
        result = runner.invoke(app, ["resume", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("--dest", result.output)

    def test_test_github_help(self):
        result = runner.invoke(app, ["test", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("--verify-hashes", result.output)

    def test_test_command_against_local_manifest(self):
        with TemporaryDirectory() as temporary:
            destination = Path(temporary)
            (destination / "a.txt").write_bytes(b"hello")
            files = [FileItem("a.txt", 5, _blob_sha(b"hello"))]
            save_manifest(
                destination,
                Manifest(repo="q/repo", branch="main", revision="abc", files=files),
            )
            result = runner.invoke(app, ["test", "--dest", str(destination)])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("正常", result.output)
            # 表格需要撑满终端宽度，否则长标题会被挤成竖排
            self.assertIn("校验结果：q/repo @ abc", result.output)

    def test_test_command_reports_missing(self):
        with TemporaryDirectory() as temporary:
            destination = Path(temporary)
            files = [FileItem("missing.txt", 5, "s")]
            save_manifest(
                destination,
                Manifest(repo="q/repo", branch="main", revision="abc", files=files),
            )
            result = runner.invoke(app, ["test", "--dest", str(destination)])
            self.assertEqual(result.exit_code, 1)
            self.assertIn("缺失", result.output)

    def test_resume_without_manifest_fails(self):
        with TemporaryDirectory() as temporary:
            result = runner.invoke(app, ["resume", "--dest", str(Path(temporary))])
            self.assertEqual(result.exit_code, 2)
            self.assertIn("任务清单", result.output)
