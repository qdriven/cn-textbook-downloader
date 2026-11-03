from unittest import TestCase
from unittest.mock import patch

from cn_textbook_downloader.core.files import FileItem
from cn_textbook_downloader.sources.github import GitHubSource


class GitHubSourceTests(TestCase):
    def test_raw_url_uses_revision_and_quotes_path(self):
        source = GitHubSource("qdriven/ChinaTextbook", "master")
        source.revision = "abc123"
        item = FileItem(path="初中/数学 课本.pdf", size=1, sha="x")
        url = source.raw_url(item)
        self.assertEqual(
            url,
            "https://raw.githubusercontent.com/qdriven/ChinaTextbook/abc123/"
            "%E5%88%9D%E4%B8%AD/%E6%95%B0%E5%AD%A6%20%E8%AF%BE%E6%9C%AC.pdf",
        )

    def test_raw_url_falls_back_to_branch(self):
        source = GitHubSource("q/repo", "main")
        item = FileItem(path="a.pdf", size=1, sha="x")
        self.assertEqual(
            source.raw_url(item), "https://raw.githubusercontent.com/q/repo/main/a.pdf"
        )

    def test_resolve_pins_branch_sha(self):
        source = GitHubSource("qdriven/ChinaTextbook", "master", "token")
        with patch("cn_textbook_downloader.core.github_api.request_json") as request_json:
            request_json.side_effect = [
                {"sha": "deadbeef"},
                {
                    "tree": [
                        {"path": "a.pdf", "size": 1, "sha": "s1", "type": "blob"},
                        {"path": "dir", "type": "tree"},
                    ],
                    "truncated": False,
                },
            ]
            revision, files = source.resolve()
        self.assertEqual(revision, "deadbeef")
        self.assertEqual(source.revision, "deadbeef")
        self.assertEqual(files, [FileItem("a.pdf", 1, "s1")])

    def test_truncated_tree_raises(self):
        source = GitHubSource("q/repo", "main")
        with patch(
            "cn_textbook_downloader.core.github_api.request_json",
            return_value={"sha": "x", "tree": [], "truncated": True},
        ):
            with self.assertRaises(RuntimeError):
                source.resolve()

    def test_from_manifest_pins_revision(self):
        from cn_textbook_downloader.core.files import FileItem as FI
        from cn_textbook_downloader.state import Manifest

        manifest = Manifest(repo="q/repo", branch="main", revision="sha1", files=[FI("a.pdf", 1, "s")])
        source = GitHubSource.from_manifest(manifest, "token")
        self.assertEqual(source.revision, "sha1")
        self.assertEqual(source.token, "token")
