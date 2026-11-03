from hashlib import sha1
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from cn_textbook_downloader.core.verify import (
    existing_merged_pdf_for_chunk,
    git_blob_sha,
    safe_destination,
    verify_part,
)


class VerifyTests(TestCase):
    def test_git_blob_sha_matches_git_hash(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "sample.txt"
            path.write_bytes(b"hello")
            self.assertEqual(git_blob_sha(path), "b6fc4c620b67d95f953a5c1c1230aaab5db5a1b0")

    def test_git_blob_sha_streams_large_files(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "large.bin"
            data = b"a" * (3 * 1024 * 1024 + 7)  # 跨多个 CHUNK_SIZE
            path.write_bytes(data)
            expected = sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
            self.assertEqual(git_blob_sha(path), expected)

    def test_existing_merged_pdf(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "sample.pdf").write_bytes(b"%PDF-test")
            merged = existing_merged_pdf_for_chunk(root / "sample.pdf.1")
            self.assertEqual(merged, root / "sample.pdf")

    def test_existing_merged_pdf_invalid_header(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "sample.pdf").write_bytes(b"not-a-pdf")
            self.assertIsNone(existing_merged_pdf_for_chunk(root / "sample.pdf.1"))

    def test_existing_merged_pdf_missing(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertIsNone(existing_merged_pdf_for_chunk(root / "sample.pdf.1"))

    def test_safe_destination(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = safe_destination(root, "小学/数学/课本.pdf")
            self.assertEqual(target, root / "小学" / "数学" / "课本.pdf")
            self.assertTrue(target.parent.is_dir())

    def test_safe_destination_rejects_traversal_and_absolute(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            for bad in ("../evil.pdf", "/abs/path.pdf", ".."):
                with self.assertRaises(ValueError):
                    safe_destination(root, bad)

    def test_verify_part_replaces_atomically(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            part = root / "part"
            target = root / "target"
            part.write_bytes(b"hello")
            verify_part(part, target, 5, git_blob_sha(part))
            self.assertEqual(target.read_bytes(), b"hello")
            self.assertFalse(part.exists())

    def test_verify_part_rejects_bad_sha(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            part = root / "part"
            part.write_bytes(b"hello")
            with self.assertRaises(IOError):
                verify_part(part, root / "target", 5, "wrong")
            self.assertFalse(part.exists())  # 校验失败时删除临时文件
