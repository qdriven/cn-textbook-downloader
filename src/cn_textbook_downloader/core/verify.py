"""文件校验与安全路径处理。"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path, PurePosixPath

CHUNK_SIZE = 1024 * 1024


def safe_destination(root: Path, repo_path: str) -> Path:
    """把仓库内路径映射为本地路径，拒绝绝对路径与目录穿越。"""
    pure_path = PurePosixPath(repo_path)
    if pure_path.is_absolute() or ".." in pure_path.parts or not pure_path.parts:
        raise ValueError(f"不安全的仓库路径：{repo_path}")
    destination = root.joinpath(*pure_path.parts)
    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination


def git_blob_sha(path: Path) -> str:
    """计算文件内容的 Git blob SHA-1（与 GitHub tree API 的 sha 字段一致）。"""
    digest = hashlib.sha1(f"blob {path.stat().st_size}\0".encode())
    with path.open("rb") as file:
        while block := file.read(CHUNK_SIZE):
            digest.update(block)
    return digest.hexdigest()


def existing_merged_pdf_for_chunk(chunk_path: Path) -> Path | None:
    """分块对应的合并 PDF 已存在且带有 PDF 文件头时返回其路径。"""
    match = re.match(r"^(.*\.pdf)\.\d+$", chunk_path.name, re.IGNORECASE)
    if not match:
        return None
    merged = chunk_path.with_name(match.group(1))
    if not merged.is_file() or merged.stat().st_size < 5:
        return None
    with merged.open("rb") as file:
        return merged if file.read(5) == b"%PDF-" else None


def verify_part(part: Path, target: Path, expected_size: int, expected_sha: str) -> None:
    """校验临时文件的大小与 SHA，通过后原子替换为正式文件。"""
    if part.stat().st_size != expected_size:
        raise IOError(f"文件大小不符：{part.stat().st_size} != {expected_size}")
    actual_sha = git_blob_sha(part)
    if actual_sha != expected_sha:
        part.unlink(missing_ok=True)
        raise IOError(f"Git blob 校验失败：{actual_sha} != {expected_sha}")
    os.replace(part, target)
