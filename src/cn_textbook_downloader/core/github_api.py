"""GitHub API 封装：解析分支版本、获取文件树。"""

from __future__ import annotations

import http.client
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from ..formatting import log
from .files import FileItem
from .retry import retry_delay

USER_AGENT = "cn-textbook-downloader/0.1"


def request_json(url: str, token: str | None, retries: int, timeout: int) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    for attempt in range(retries + 1):
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError) as exc:
            if isinstance(exc, urllib.error.HTTPError) and exc.code == 404:
                raise  # 404 是永久错误（仓库/分支不存在），重试无意义
            if attempt >= retries:
                raise
            response = exc if isinstance(exc, urllib.error.HTTPError) else None
            delay = retry_delay(attempt, response)
            log(f"GitHub API 请求失败，{delay:.0f} 秒后重试：{exc}")
            time.sleep(delay)
    raise RuntimeError("GitHub API 请求失败")


def resolve_branch_sha(repo: str, branch: str, token: str | None, retries: int, timeout: int) -> str:
    """把分支名解析为提交 SHA，下载时固定版本，续传时保持一致。"""
    url = f"https://api.github.com/repos/{repo}/commits/{urllib.parse.quote(branch, safe='')}"
    commit = request_json(url, token, retries, timeout)
    return commit["sha"]


def list_tree(repo: str, revision: str, token: str | None, retries: int, timeout: int) -> list[FileItem]:
    url = (
        f"https://api.github.com/repos/{repo}/git/trees/"
        f"{urllib.parse.quote(revision, safe='')}?recursive=1"
    )
    tree = request_json(url, token, retries, timeout)
    if tree.get("truncated"):
        raise RuntimeError("GitHub 返回的文件清单被截断，请使用 --include 分目录下载")
    return [
        FileItem(path=item["path"], size=item["size"], sha=item["sha"])
        for item in tree.get("tree", [])
        if item.get("type") == "blob"
    ]
