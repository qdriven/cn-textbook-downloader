# 项目文案（Marketing）

> 本页是 cn-textbook-downloader 的对外介绍文案，说明它解决什么问题、好处是什么。
> 可整体用于发布文章 / 项目主页，也可按段落截取：顶部一段适合 GitHub About，
> 痛点与对照表适合 README 开头。

## 一句话

GitHub 上最大的中文教材合集 [ChinaTextbook](https://github.com/TapXWorld/ChinaTextbook)（2375 个文件、43.4 GiB），用 `git clone` 拉不动，用网页逐个点要几天——现在一条命令、带进度条、断了能续。

## 关于仓库地址：原始仓库 + 镜像自动回退

教材内容的**原始仓库**是 [TapXWorld/ChinaTextbook](https://github.com/TapXWorld/ChinaTextbook)（84k+ stars，持续更新）。由于体量巨大且内容敏感，原始仓库存在被删除或不可访问的风险——工具内置了同内容镜像的自动回退：

- 默认从原始仓库下载，正常情况下你无需关心地址问题
- 原始仓库 404（被删/不可访问）时，自动按顺序尝试镜像，日志中明确提示切换到了哪个
- 任务清单记录实际使用的仓库，`resume` 会接着同一地址续传，不会混乱
- 镜像与原始仓库同源（fork 且未分叉），Git blob SHA 校验保证文件内容一致
- 也可以用 `--repo` 手动指定任意仓库地址

当前内置镜像（按尝试顺序）：

| 顺序 | 仓库 | 说明 |
|---|---|---|
| 0 | [TapXWorld/ChinaTextbook](https://github.com/TapXWorld/ChinaTextbook) | 原始仓库（默认） |
| 1 | [qdriven/ChinaTextbook](https://github.com/qdriven/ChinaTextbook) | 维护者自己的 fork，与上游同步 |
| 2 | [zixing131/ChinaTextbook](https://github.com/zixing131/ChinaTextbook) | 社区 fork，2026 年仍活跃 |
| 3 | [iab0x00/ChinaTextbook](https://github.com/iab0x00/ChinaTextbook) | 社区 fork |
| 4 | [Chiowe/ChinaTextbook-](https://github.com/Chiowe/ChinaTextbook-) | 社区 fork，star 数最多 |

## 它解决什么问题

你想把整套中小学教材下载到本地——给孩子的平板离线用、给乡村学校装一台"本地教材库"、给老师们备一份稳定的资料源。然后你遇到三堵墙：

- **墙一：仓库太大，`git clone` 直接放弃。** 43GB 的仓库，clone 到一半网络抖一下，几个小时的等待全部作废，还得从头再来。
- **墙二：网页逐个下载是体力活。** 2375 个 PDF，手动点下载要点到怀疑人生，而且教材还按章节切成了分块，下载完还要自己手动合并。
- **墙三：下载完不知道缺没缺、坏没坏。** 几千个文件，哪一个是断在半路的？哪一个是版本更新过的？没有校验，就是一本糊涂账。

## cn-textbook-downloader 怎么拆掉这三堵墙

| 痛点 | 我们的做法 |
|---|---|
| 下载中断就要重来 | **.part 断点续传** — HTTP Range 从字节级断点继续，中断的文件不浪费一个字节 |
| 版本漂移导致文件对不上 | **任务清单锁定版本** — manifest 固定 commit SHA，`resume` 永远接着同一个版本下，今天下到一半、下周继续也没问题 |
| 不知道文件是否完整 | **Git blob SHA 校验** — `cn-textbook test` 逐文件核对 SHA，缺失/大小不符/内容损坏一目了然 |
| 几千个文件没有进度感 | **Textual TUI 实时进度条** — 并发 4~8 线程，每个文件的进度、整体完成度、成功/失败统计尽在眼底 |
| 教材分块 PDF 需要手动拼 | **`--merge` 一键合并** — 下载完成后自动把分块合成完整 PDF |

## 三条命令，全会了

```bash
uv sync
uv run cn-textbook download   # 开始下载（TUI 进度界面）
uv run cn-textbook resume    # 断了？从断点继续
uv run cn-textbook test      # 校验：每个文件都在、都对
```

不需要 Docker，不需要配置文件，不需要 GitHub Token（有 `GITHUB_TOKEN` 时自动加速）。`uv` 装好即用，Windows / macOS / Linux 通用，中文输出全程无乱码。

## 谁需要它

- 🏫 **学校 / 教育机构** — 一台离线电脑装下整个教材库，不依赖网络
- 👨‍👩‍👧 **家长** — 一次性下齐，平板离线使用，告别在线看 PDF 的卡顿
- 👩‍🏫 **教师** — 稳定的本地教材源，随时校验完整性
- 📖 **公益项目** — 为网络条件有限的地区批量准备教材资源

## 为什么不用别的方案

- **`git clone`**：不支持断点续传，43GB 一次失败全部重来；且会带下整个 git 历史，占双倍空间
- **`git clone --depth 1`**：只解决历史问题，断点续传仍然没有
- **网页打包下载（CodeZip / DownGit）**：有大小上限，几千个文件必失败
- **wget 脚本**：能下载，但没有版本锁定、没有 SHA 校验、没有合并、没有进度——坏一个文件你永远不知道

**cn-textbook-downloader = 版本锁定 + 断点续传 + 完整性校验 + PDF 合并 + TUI 进度，专为"大仓库批量下载"这一件事打磨。**

## 技术上值得一提

- Python 现代工具链：`uv` + `typer` + `textual`，37 项测试全绿
- 来源抽象（`Source`）设计，未来接入 Gitee / CDN 镜像只需增加一个类
- Windows 重定向下 UTF-8 强制输出，中文日志零乱码

> ⭐ 如果它帮你省下了一个星期的手动下载，欢迎 star 支持一下。
