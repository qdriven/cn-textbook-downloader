import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from cn_textbook_downloader.core.files import FileItem
from cn_textbook_downloader.state import Manifest, load_manifest, manifest_path, save_manifest


class ManifestTests(TestCase):
    def test_roundtrip(self):
        with TemporaryDirectory() as temporary:
            destination = Path(temporary)
            files = [FileItem("a.pdf", 1, "s1"), FileItem("b/c.pdf", 2, "s2")]
            manifest = Manifest(repo="qdriven/ChinaTextbook", branch="master", revision="abc", files=files)
            save_manifest(destination, manifest)
            loaded = load_manifest(destination)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.repo, "qdriven/ChinaTextbook")
            self.assertEqual(loaded.revision, "abc")
            self.assertEqual(loaded.files, files)
            self.assertTrue(loaded.created)
            self.assertTrue(loaded.updated)

    def test_save_updates_timestamp_and_preserves_payload(self):
        with TemporaryDirectory() as temporary:
            destination = Path(temporary)
            files = [FileItem("a.pdf", 1, "s1")]
            manifest = Manifest(repo="q/repo", branch="main", revision="abc", files=files)
            save_manifest(destination, manifest)
            first = manifest_path(destination).read_text(encoding="utf-8")
            save_manifest(destination, manifest)
            second = manifest_path(destination).read_text(encoding="utf-8")
            self.assertNotEqual(first, second)  # updated 时间戳变化
            loaded = json.loads(second)
            self.assertEqual(loaded["repo"], "q/repo")
            self.assertEqual(loaded["revision"], "abc")
            self.assertEqual(loaded["files"], [{"path": "a.pdf", "size": 1, "sha": "s1"}])

    def test_missing_manifest(self):
        with TemporaryDirectory() as temporary:
            self.assertIsNone(load_manifest(Path(temporary)))
