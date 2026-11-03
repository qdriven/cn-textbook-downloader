from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from cn_textbook_downloader.core.merge import merge_split_pdfs


class MergeTests(TestCase):
    def test_merge_chunks(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "sample.pdf.1").write_bytes(b"%PDF-test-")
            (root / "sample.pdf.2").write_bytes(b"content")
            self.assertEqual(merge_split_pdfs(root), 1)
            self.assertEqual((root / "sample.pdf").read_bytes(), b"%PDF-test-content")
            self.assertTrue((root / "sample.pdf.1").is_file())  # 原分块保留

    def test_skips_existing_merged(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "sample.pdf").write_bytes(b"%PDF-existing")
            (root / "sample.pdf.1").write_bytes(b"%PDF-test")
            self.assertEqual(merge_split_pdfs(root), 0)

    def test_non_consecutive_numbers_skipped(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "sample.pdf.1").write_bytes(b"a")
            (root / "sample.pdf.3").write_bytes(b"b")
            self.assertEqual(merge_split_pdfs(root), 0)
            self.assertFalse((root / "sample.pdf").exists())
