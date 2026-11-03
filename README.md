# cn-textbook-downloader

从 GitHub 下载 [ChinaTextbook](https://github.com/TapXWorld/ChinaTextbook) 教材仓库（2375 个文件、43.4 GiB）的命令行工具——**一条命令、带进度条、断了能续**。

- **download** — 启动下载任务（TUI 进度界面，自动断点续传）
- **resume** — 继续未完成的下载任务（manifest 锁定版本，`.part` 字节级续传）
- **test** — 校验已下载的文件（存在性 / 大小 / Git blob SHA）

默认从原始仓库 [TapXWorld/ChinaTextbook](https://github.com/TapXWorld/ChinaTextbook) 下载；原始仓库 404（被删或不可访问）时自动按顺序尝试镜像，也可用 `--repo` 手动指定。镜像清单见 [docs/usage.md](docs/usage.md#镜像仓库)。

## 它解决什么问题

一个 43GB 的教材仓库，`git clone` 拉不动、网页逐个点要几天、下载完还不知道缺没缺坏没坏。cn-textbook-downloader 一次解决：

| 痛点 | 做法 |
|---|---|
| 下载中断就要重来 | `.part` 断点续传，HTTP Range 从字节级断点继续 |
| 版本漂移文件对不上 | manifest 锁定 commit SHA，`resume` 永远接着同一版本 |
| 不知道文件是否完整 | `test` 逐文件核对 Git blob SHA，缺失/损坏一目了然 |
| 几千个文件没有进度感 | Textual TUI 实时进度条，并发下载统计尽在眼底 |
| 教材分块 PDF 要手动拼 | `--merge` 下载完成后一键合并 |

完整的痛点分析与方案对比见 [docs/marketing.md](docs/marketing.md)。

## 演示

![cn-textbook 使用演示](docs/cn-textbook-demo.gif)

## 快速开始

需要 [uv](https://docs.astral.sh/uv/) 与 Python 3.10+，Windows / macOS / Linux 通用：

```bash
uv sync

uv run cn-textbook download          # TUI 下载
uv run cn-textbook resume           # 断点续传
uv run cn-textbook test             # 校验
```

下载来源为 GitHub，命令为 `download` / `resume` / `test`；来源逻辑通过 `Source` 抽象接入，详见 [docs/architecture.md](docs/architecture.md)。

完整文档见 [docs/](docs/index.md)。
