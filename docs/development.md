# 开发指南

## 环境搭建

需要 [uv](https://docs.astral.sh/uv/)（Python 3.10+）。

```bash
uv sync                 # 创建 .venv 并安装依赖
uv run pytest           # 运行测试
uv run cn-textbook --help
```

常用命令：

```bash
uv add <package>        # 添加运行时依赖
uv add --dev <package>  # 添加开发依赖（写入 dependency-groups）
uv run pytest -q        # 测试
```

## 测试

测试位于 `tests/`，使用 pytest + unittest 风格，网络请求全部 mock：

```bash
uv run pytest            # 全部
uv run pytest -q tests/test_downloader.py   # 单个模块
```

覆盖点：

- `test_verify.py` — Git blob SHA、安全路径、.part 校验、合并 PDF 检测
- `test_merge.py` — PDF 分块合并
- `test_downloader.py` — 单文件下载、断点续传（Range）、重试、并发汇总、取消
- `test_github_source.py` — URL 构造、分支 → SHA、清单截断
- `test_state.py` — manifest 读写
- `test_cli.py` — 命令注册、帮助、test 命令端到端（本地 manifest）

## 添加新的下载来源

当前只有 GitHub，`download` / `resume` / `test` 是根命令。新增来源时不要让来源名
占用子命令；建议给现有命令增加 `--source` 选项，或新增独立命令，并复用 `Source` 抽象：

1. 在 `sources/` 新建 `oss.py`，继承 `Source` 实现两个方法：

   ```python
   class OSSSource(Source):
       name = "oss"

       def resolve(self) -> tuple[str, list[FileItem]]:
           # 拉取对象清单，返回 (版本标识, FileItem 列表)
           ...

       def raw_url(self, item: FileItem) -> str:
           # 返回可 Range 请求的下载地址
           ...
   ```

2. 在 `sources/__init__.py` 中导出，并在命令层按 `--source` 选择来源；
   下载引擎只依赖 `resolve()` / `raw_url()`，无需改动 `core/downloader.py`。

3. 不要在 `register_sources` 中重复注册同名的 `download` / `resume` / `test` 命令。

## 代码约定

- Python 3.10+，`from __future__ import annotations`
- 所有网络请求集中在 `core/`，引擎不感知具体来源
- 日志统一走 `formatting.log`（可被 TUI 重定向）
- 无第三方依赖的纯逻辑模块（verify / merge / state / retry）保持可单测
