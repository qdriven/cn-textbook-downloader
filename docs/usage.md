# 使用指南

三个主命令：`download`（下载）、`resume`（继续任务）、`test`（校验）。
下载来源为 GitHub，命令不再带来源子命令。

通用约定：

- `GITHUB_TOKEN` 环境变量或 `--token` 提供 GitHub 令牌（可选，可提高 API 限额）
- 所有命令的 `--dest` 默认是当前目录下的 `ChinaTextbook`
- 下载中断（Ctrl+C / 断网 / 关机）后，重新运行同一命令即可续传

## download — 启动下载任务

默认使用 TUI（Textual）展示进度，`--no-tui` 切换为普通日志输出。

```bash
cn-textbook download
cn-textbook download --repo TapXWorld/ChinaTextbook --branch master --dest ./ChinaTextbook
```

选项：

| 选项 | 默认值 | 说明 |
| --- | --- | --- |
| `--repo` | `TapXWorld/ChinaTextbook` | GitHub 仓库，格式 owner/name；默认原始仓库，不可用时自动尝试镜像 |
| `--branch` | `master` | 分支或标签 |
| `--dest` | `ChinaTextbook` | 保存目录 |
| `--include` | 无 | 只下载匹配的路径，可重复，如 `--include '小学/*' --include README.md` |
| `--workers` | 4 | 并发下载数 |
| `--retries` | 8 | 每个文件的重试次数 |
| `--timeout` | 60 | 网络超时秒数 |
| `--fast-skip` | 关 | 已有文件只检查大小，跳过 SHA 校验（更快） |
| `--merge` | 关 | 全部下载成功后合并 PDF 分块（保留原分块） |
| `--token` | `GITHUB_TOKEN` | GitHub 令牌 |
| `--no-tui` | 关 | 不使用 TUI，普通日志输出 |
| `--dry-run` | 关 | 只列出匹配的文件，不下载 |

示例：

```bash
# 只下载小学目录并合并 PDF
cn-textbook download --include '小学/*' --merge

# 先看清单不下载
cn-textbook download --dry-run
```

下载开始时会在目标目录写入任务清单
`.cn-textbook-downloader/manifest.json`（记录仓库、版本、文件列表），供 `resume` 使用。

## resume — 继续未完成的下载任务

读取目标目录中的任务清单，固定原版本继续下载。未完成的文件通过 `.part` 断点续传，
已完成文件自动跳过。

```bash
cn-textbook resume
cn-textbook resume --dest ./ChinaTextbook --workers 8
```

选项：`--dest`、`--include`、`--workers`、`--retries`、`--timeout`、`--fast-skip`、`--merge`、`--token`、`--no-tui`（同 download）。

> 若目标目录没有任务清单，`resume` 会提示先运行 `download`。

## test — 校验已下载的文件

检查目标目录中每个文件的存在性与大小；`--verify-hashes` 额外计算 Git blob SHA-1 校验。
优先使用任务清单（无网络请求）；没有清单时从 GitHub 解析当前版本。

```bash
cn-textbook test
cn-textbook test --dest ./ChinaTextbook --verify-hashes
```

选项：`--dest`、`--repo`、`--branch`、`--include`、`--verify-hashes`、`--workers`（校验并发数）、`--token`、`--retries`、`--timeout`。

输出为问题文件表格与汇总（总计 / 正常 / 缺失 / 大小不符 / SHA 不符）；
发现问题时退出码为 1，全部通过时为 0。

## 镜像仓库

教材内容的原始仓库是 [TapXWorld/ChinaTextbook](https://github.com/TapXWorld/ChinaTextbook)。
由于体量巨大（43.4 GiB）且内容敏感，原始仓库存在被删除或不可访问的风险，
工具内置了同内容镜像的自动回退机制：

- **默认**从原始仓库（顺序 0）下载；
- 原始仓库返回 404（被删 / 不可访问 / 分支不存在）时，**自动按顺序尝试镜像**，
  日志会明确提示「仓库 xxx 不可用（404），尝试镜像…」和「已切换到镜像仓库：xxx」；
- 其他错误（如 403 限流、网络超时）**不会**触发回退，按原有重试逻辑处理；
- 回退成功后，任务清单（manifest）记录实际使用的仓库，`resume` 接着同一地址续传；
- 镜像与原始仓库同源（fork 且未分叉），Git blob SHA 校验保证文件内容一致；
- 需要手动定制时可用 `--repo` 手动指定任意仓库地址（含镜像或你自己的 fork）。

内置镜像清单（按尝试顺序，定义在 `sources/github.py` 的 `MIRROR_REPOS`）：

| 顺序 | 仓库 | 最近推送 | 说明 |
| --- | --- | --- | --- |
| 0 | [TapXWorld/ChinaTextbook](https://github.com/TapXWorld/ChinaTextbook) | 2026-10 | 原始仓库，84k+ stars |
| 1 | [qdriven/ChinaTextbook](https://github.com/qdriven/ChinaTextbook) | 2026-10 | 维护者 fork，与上游同步 |
| 2 | [zixing131/ChinaTextbook](https://github.com/zixing131/ChinaTextbook) | 2026-08 | 社区 fork |
| 3 | [iab0x00/ChinaTextbook](https://github.com/iab0x00/ChinaTextbook) | 2025-10 | 社区 fork |
| 4 | [Chiowe/ChinaTextbook-](https://github.com/Chiowe/ChinaTextbook-) | 2025-05 | 社区 fork，star 数最多（572） |

> 镜像清单可通过 GitHub 的 fork 列表核实：
> `https://api.github.com/repos/TapXWorld/ChinaTextbook/forks?sort=stargazers`
> 如需增删镜像，修改 `MIRROR_REPOS` 即可，顺序即尝试顺序。

## 环境变量

| 变量 | 说明 |
| --- | --- |
| `GITHUB_TOKEN` | GitHub 令牌，等价于 `--token` |

## 退出码

| 码 | 含义 |
| --- | --- |
| 0 | 成功 |
| 1 | 有文件失败或校验发现问题 |
| 2 | 参数错误 |
| 130 | 用户中断（Ctrl+C） |
