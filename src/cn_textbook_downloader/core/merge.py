"""PDF 分块合并：把 *.pdf.N 合并为 *.pdf，保留原分块。"""

from __future__ import annotations

import os
import re
from collections import defaultdict
from pathlib import Path

from ..formatting import log

CHUNK_SIZE = 1024 * 1024


def merge_split_pdfs(root: Path) -> int:
    groups: dict[Path, list[tuple[int, Path]]] = defaultdict(list)
    pattern = re.compile(r"^(.*\.pdf)\.(\d+)$", re.IGNORECASE)
    for path in root.rglob("*.pdf.*"):
        match = pattern.match(path.name)
        if match and path.is_file():
            output = path.with_name(match.group(1))
            groups[output].append((int(match.group(2)), path))

    merged = 0
    for output, numbered_parts in sorted(groups.items(), key=lambda pair: str(pair[0])):
        numbered_parts.sort(key=lambda pair: pair[0])
        numbers = [number for number, _ in numbered_parts]
        if numbers != list(range(1, len(numbers) + 1)):
            log(f"分块编号不连续，暂不合并：{output}")
            continue
        if output.exists():
            log(f"合并文件已存在，跳过：{output}")
            continue

        temporary = output.with_name(output.name + ".merging")
        expected_size = sum(part.stat().st_size for _, part in numbered_parts)
        try:
            with temporary.open("wb") as destination:
                for _, part in numbered_parts:
                    with part.open("rb") as source:
                        while block := source.read(CHUNK_SIZE):
                            destination.write(block)
            if temporary.stat().st_size != expected_size:
                raise IOError("合并后的文件大小不符")
            os.replace(temporary, output)
            merged += 1
            log(f"已合并：{output}（原分块仍保留）")
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
    return merged
