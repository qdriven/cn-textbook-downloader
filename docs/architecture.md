# 架构设计

## 模块结构

```
src/cn_textbook_downloader/
├── cli.py            # typer 入口：download / resume / test 三个命令
├── config.py         # DownloadOptions（命令选项的汇总）
├── formatting.py     # 日志输出（可重定向到 TUI）、大小格式化
├── errors.py         # 自定义异常
├── state.py          # 任务清单 manifest 的读写
├── core/
│   ├── github_api.py # GitHub API：分支 → SHA、git tree 文件清单
│   ├── files.py      # FileItem 数据结构、include 过滤
│   ├── verify.py     # Git blob SHA 校验、安全路径、.part 校验
│   ├── downloader.py # 并发下载引擎：断点续传、重试、取消
│   ├── merge.py      # PDF 分块合并（*.pdf.N → *.pdf）
│   └── retry.py      # 指数退避 + Retry-After
├── sources/
│   ├── base.py       # Source 抽象基类（插件接口）
│   └── github.py     # GitHub 来源 + 三个命令的实现
└── tui/
    └── download_app.py # Textual TUI
```

## 命令组织

主命令固定三个：`download`、`resume`、`test`。当前下载来源只有 GitHub，
因此命令直接挂在根应用上，不再设来源子命令：

```
cn-textbook download ...
cn-textbook resume ...
cn-textbook test ...
```

来源通过 `sources/base.py` 的 `Source` 抽象类接入，只需实现两个方法：

- `resolve()`：把用户指定的位置（如仓库 + 分支）解析为**固定版本 + 文件清单**
- `raw_url(item)`：为每个文件生成下载地址

`sources/__init__.py` 的 `register_sources` 负责登记来源命令。下载引擎
（`core/downloader.py`）只依赖 `Source` 的两个方法，与具体来源无关；如果以后
加入其他来源，建议通过 `--source` 选项或新增独立命令区分，不要占用同名子命令。

## 断点续传原理

下载引擎对每个文件使用两阶段落盘：

1. 先写入 `文件名.part` 临时文件；
2. 下载完成后校验大小与 Git blob SHA-1，通过后原子替换为正式文件。

中断后重新运行：

- 正式文件已存在且大小、SHA 一致 → 直接跳过；
- `.part` 存在 → 用 HTTP `Range: bytes=offset-` 从断点续传，并校验
  `Content-Range` 起始偏移；
- `.part` 大小超过预期 → 删除重下。

`download` 与 `resume` 都执行同一套引擎逻辑；区别是版本来源：

- `download` 访问 GitHub API 解析分支 → 提交 SHA，下载固定版本，并把
  （仓库、分支、SHA、文件清单）写入目标目录的
  `.cn-textbook-downloader/manifest.json`；
- `resume` 读取 manifest，不访问 API，继续原任务（若 manifest 不存在则提示先下载）。

合并 PDF（`--merge`）在下载全部完成后执行：扫描 `*.pdf.N` 分块，编号连续且
无既有合并文件时合并为 `*.pdf`，原分块保留。

## TUI 与线程模型

`tui/download_app.py` 的 `DownloaderApp` 把下载引擎放在后台线程运行，
通过 `call_from_thread` 更新界面（进度条、当前文件、日志）。引擎的日志输出
通过 `formatting.set_log_sink` 重定向到 TUI 的日志面板，避免污染终端。

Ctrl+C 触发 `quit_task`：设置取消事件 → 引擎在下一个 1 MiB 分块边界停止
（`.part` 保留）→ 退出。退出码 130。

`--no-tui` 时引擎直接在调用线程运行，日志输出到标准输出，适合 CI 或无终端环境。

## 校验与安全

- `safe_destination` 拒绝绝对路径与 `..` 目录穿越；
- 每个文件以 GitHub tree API 的 `sha` 为基准做 Git blob SHA-1 校验，
  与仓库内容严格一致；
- `--fast-skip` 可只查大小跳过 SHA 计算（大仓库首次跳过更快）；
- `test` 命令支持存在性 / 大小 / SHA 三级检查，问题文件以表格列出。
