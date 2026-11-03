"""重试退避策略。"""

from __future__ import annotations


def retry_delay(attempt: int, response=None) -> float:
    """指数退避；服务器给出 Retry-After 时优先使用。"""
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after and retry_after.isdigit():
            return min(float(retry_after), 120.0)
    return min(2**attempt, 60)
