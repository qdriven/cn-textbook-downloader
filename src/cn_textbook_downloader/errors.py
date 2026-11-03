"""自定义异常。"""


class DownloadError(RuntimeError):
    """下载相关错误的基类。"""


class DownloadInterrupted(DownloadError):
    """用户取消下载（Ctrl+C）。临时文件保留，可续传。"""


class StateError(DownloadError):
    """任务状态（manifest）相关错误。"""
