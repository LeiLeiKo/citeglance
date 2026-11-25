# Paper Watch · 论文追踪

Paper Watch 是一个 Windows 学术论文追踪客户端。按研究主题设置检索频道，定时查找近期论文，在同一个窗口阅读摘要、核对关键词、收藏论文和保存译文。

The Windows desktop app tracks new research papers across configurable search channels. It supports scheduled searches, local history and favorites, and on-demand abstract translation.

![Paper Watch 的论文库。左侧显示按频道检索到的论文，右侧显示来源、命中的检索词和摘要。](docs/images/library.png)

*界面预览使用示例数据。*

## 功能

| 功能 | 用法 |
| --- | --- |
| 定时检索 | 客户端运行期间自动检索，默认每 24 小时一次。间隔可按分钟、小时或天调整，也可暂停。页面显示上次启动及下次预计检索时间。 |
| 自定义频道 | 按 A／B 组词组交叉匹配，支持可选的领域限定、单频道屏蔽词和全局屏蔽词。 |
| 本地论文库 | 查看标题、作者、发表日期、来源关键词、学科分类和摘要。检索结果自动去重，可收藏并查看历史。 |
| 摘要翻译 | 通过 DeepL、OpenAI 兼容服务或 LibreTranslate 翻译摘要，可选简体中文、日语和英语。已有译文保存在本机。 |
| 三语界面 | 简体中文、English、日本語可即时切换，选择会记住。 |
| 可选云端运行 | 可用 Docker 在 Linux 服务器常驻，从 Telegram 随时查询状态或触发检索，也可用 GitHub Actions 定时发送简报。 |

## 快速开始

1. 下载并解压源码，确认已安装 **Python 3.10+** 和随标准安装提供的 **Tkinter**。
2. 双击 `launch_client.cmd`。也可以在项目目录运行 `python -X utf8 desktop.py`。
3. 在「API 与设置」选择论文检索来源。使用 Semantic Scholar 时，填入该服务发放的 API Key 并保存。
4. 回到「论文库」，选择频道并点击「检索新论文」。要调整自动检索间隔，打开「定时检索」。

## 检索来源

- **Semantic Scholar** 提供论文检索、摘要和学科分类。字段是否返回取决于该条记录。
- **OpenAlex** 提供论文元数据和索引关键词。API Key 用于持续使用及翻页。
- **Crossref** 支持无需密钥的公开检索。摘要由元数据提供方提交，覆盖因论文而异。
- **自定义 JSON** 支持常见 REST API 的 GET／POST、密钥认证、字段映射及游标分页。接口可用的检索语法及元数据范围取决于服务。

预置频道面向 AR 虚拟扩展屏、电竞与体育观赛、AR 周边提示与视觉注意力，以及电竞观众动机与眼动。可在客户端替换成自己的研究主题。

## 本地运行与云端部署

| 方式 | 运行条件 | 结果 |
| --- | --- | --- |
| Windows 客户端 | 客户端打开且设备处于唤醒状态，支持最小化 | 本地历史、收藏与译文 |
| Docker 常驻服务 | Linux 服务器保持在线，由 Docker 管理进程 | Telegram 简报，以及 `/status` 和 `/search` 指令 |
| GitHub Actions | 启用后由 GitHub 执行，默认每天日本时间 09:07 | Telegram 简报 |

[使用指南、API 配置与 GitHub Actions 部署](docs/usage.md) · [Linux 服务器常驻部署](docs/server.md)
