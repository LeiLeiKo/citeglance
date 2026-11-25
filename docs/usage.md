# Paper Watch 使用与部署指南

[返回项目首页](../README.md)

## Windows 客户端

双击 `launch_client.cmd`。也可以在项目目录运行 `python -X utf8 desktop.py`。需要 Python 3.10 或更新版本，以及 Python 安装时附带的 Tkinter。无需安装 Python 第三方包。

在窗口右上角的「界面语言」选择简体中文、English 或日本語。界面会立即切换并记住选择。摘要翻译的目标语言在「API 与设置」单独设置。

### 客户端定时检索

默认每 24 小时检索一轮。在「定时检索」中可以设置分钟、小时或天为单位的间隔，或暂停定时检索。点击「保存定时设置」后立即应用。客户端使用当前保存的检索来源，自动检索所有频道，结果可在「检索历史」查看。

客户端保持打开且电脑处于唤醒状态时，最小化窗口也可继续定时。上次全频道检索的启动时间会记住，重开时已到期会运行一轮。手动搜索全部频道也会重新计算下一次时间。界面会以日本时间显示上次启动以及下次预计时间。每轮沿用「API 与设置」的请求预算，提高频率会增加每天的请求量。

![定时检索页，显示间隔设置、上次检索启动时间与下次预计时间。](images/schedule.png)

需要关机后仍能定时检索时，可部署文末的 GitHub 工作流。

1. 打开「API 与设置」，选择 **Semantic Scholar**，把已经获批的 API Key 填在「检索 API Key」，然后点「保存设置」。勾选「记住本次输入的密钥」会用 Windows DPAPI 加密保存。密钥绑定到对应服务，自定义服务还会绑定到其配置的接口地址。
2. 回到「论文库」，选一个频道或「全部频道」，点「检索新论文」。点击论文可以查看摘要、来源提供的关键词、学科分类和实际命中的检索词。OpenAlex 提供的是索引关键词。Semantic Scholar 有摘要和学科分类字段，论文记录缺失的信息会在界面明确标注。
3. 在「频道与屏蔽词」新增、删除或修改频道。A、B 两组各需要命中至少一个词组。「领域限定」可选，填写后还须命中其中一项。「仅此频道的屏蔽词」和「全局屏蔽词」分别生效。
4. 收藏、检索结果和已完成的译文会保存在此 Windows 用户的 `%LOCALAPPDATA%\PaperWatch`。频道设置写入项目里的 `channels.json`。如果希望 GitHub 定时任务采用桌面调整后的频道，提交这个文件以及本版本的 `bot.py` 到部署仓库。

### 摘要翻译

在「API 与设置」选翻译服务和目标语言，保存后，在论文详情点「翻译摘要」。目前可以翻成简体中文、日语或英语。原文和译文都会显示，重新打开已翻译的论文可以读到本机缓存。

| 服务 | 需要填写 |
| --- | --- |
| DeepL | 该服务发放的 API Key，以及 API Free 或 Pro 的完整 `/v2/translate` 地址 |
| OpenAI 兼容 | 完整 `/chat/completions` 地址、平台的模型名，以及服务要求的 API Key。本机运行的兼容服务也可配置 |
| LibreTranslate | 完整 `/translate` 地址。本机运行时可用默认的 `http://127.0.0.1:5000/translate`，所选语言需已安装。密钥取决于服务配置 |

Semantic Scholar 是检索服务。点击翻译时，客户端只把当前摘要发送给所选翻译服务。选择本机翻译服务可以在本地完成这一步。客户端自身不包含翻译模型。

### 检索 API

客户端内置 Semantic Scholar、OpenAlex 和 Crossref。Crossref 可用公开接口，按 A 组词获取候选并在客户端筛选，覆盖受候选结果与摘要可用性影响。OpenAlex 无密钥模式仅查第一页，接口可能限流。各来源对搜索语法、结果量、摘要和关键词的覆盖存在差异。

对于其他返回 JSON 的 HTTP API，选「自定义 JSON」并编辑配置框。界面自带示例，按目标 API 文档调整这些字段：

- `endpoint` 与 `method` 设置完整地址和 `GET` 或 `POST`。远程地址使用 HTTPS，本机地址可以使用 HTTP。
- `params` 与 `body` 设置查询参数和 POST JSON 请求体。可用 `{query}`、`{start_date}`、`{end_date}`、`{cursor}`。
- `auth` 设置密钥在请求头、查询参数或 JSON 请求体中的位置，并配置字段名及前缀。密钥填入独立的「检索 API Key」输入框。
- `items` 和 `next` 是列表和下一页标记的路径，例如 `results` 和 `meta.next_cursor`。`map` 关联论文标题、摘要、关键词等字段。`authors[].name` 可读取数组中所有对象的 `name`。根数组用 `$`。
- `query_style` 支持 `boolean`（AND / OR）、`semantic`（加号 / 竖线）或 `keywords`（空格分隔）。客户端仍会按频道规则过滤返回的标题和摘要。

需要 OAuth 登录、专有签名或 XML 响应的服务，需要新增一个专用适配器。GitHub 托管的原有定时工作流继续使用 Semantic Scholar 和 Telegram。下面是云端部署步骤。

## GitHub 云端运行

启用定时任务后，GitHub Actions 每天 **09:07（日本时间）**运行，检索 Semantic Scholar 的论文元数据，并把简报送到 Telegram 私聊。选择第 7 分钟是为了避开整点的调度高峰。GitHub 定时任务可能延后，简报也受论文收录时间影响。

四个检索频道、A／B 组和黑名单位于 `channels.json`。每次运行通常发出 4 次检索请求，最多 20 次，包含翻页和重试。一次手动运行有独立预算。向 Semantic Scholar 发出的所有请求至少间隔 1.05 秒。程序只用 Python 标准库，要求 Python 3.10 或更新版本。

## 1. 创建 Telegram Bot

1. 在 Telegram 给官方 `@BotFather` 发送 `/newbot`，按提示创建并保存 Token。
2. 打开你刚创建的机器人私聊，发送 `/start`。
3. 解压项目，在项目目录打开终端并运行以下命令。它会以隐藏输入的方式读取 Token，然后显示机器人近期收到消息的私聊 ID。首次设置时，建议只有你自己向它发 `/start`。

~~~~powershell
python bot.py --chat-id
~~~~

## 2. 部署到 GitHub

1. 创建一个 **Private** GitHub 仓库。提交解压后的**目录内容**到默认分支，保留隐藏的 `.github/workflows/paper-watch.yml`。确认默认分支允许工作流写入 `state.json`，并且组织策略允许该工作流使用 `contents: write`。
2. 在仓库的 **Settings → Secrets and variables → Actions → New repository secret** 添加以下三个值。

   | Secret | 值 |
   | --- | --- |
   | `SEMANTIC_SCHOLAR_API_KEY` | Semantic Scholar 发放的 API Key |
   | `TELEGRAM_BOT_TOKEN` | BotFather 发放的 Token |
   | `TELEGRAM_CHAT_ID` | 上一步取得的私聊 ID |

3. 到 **Actions → 每日论文追踪 → Run workflow**。首次保持「仅检索并预览，不发送 Telegram」勾选，在运行日志看检索结果。这一步需要 Semantic Scholar API Key。
4. 确认结果后，可以手动取消预览勾选运行一次，验证 Telegram 能收到简报。要启用日程，在 **Settings → Secrets and variables → Actions → Variables** 添加仓库变量 `PAPER_WATCH_CLOUD_ENABLED`，值设为 `true`。启用后每天由 GitHub 运行。重复手动运行会产生额外 API 请求。

云端密钥通过 GitHub Secrets 配置。桌面端可以使用 Windows 加密保存。云端工作流会把去重记录提交到仓库。个人使用时可在私有仓库中部署。

## 检索和简报

- 四个频道分别执行「A 组任一词组 AND B 组任一词组」。程序再检查标题、摘要和黑名单。第三频道使用限定词组，如 visual attention 和 cognitive load。
- 首次回看最近 14 个自然日。以后继续滚动回看，若任务长时间漏跑，则按各频道上次成功日期补查。检索用 Semantic Scholar 的出版日期字段，因此缺少精确日期或延迟收录超过窗口的论文可能遗漏。
- 同一篇论文通过 DOI、Semantic Scholar ID、arXiv ID 或规范化标题去重。跨频道结果合成一条。标题相同的预印本和正式版在同一轮出现时优先采用正式版。
- 简报包含论文标题、出版日期、渠道、匹配词组和 DOI 或 Semantic Scholar 链接。第一频道优先展示符合条件的 Pavanatto 论文，通过 AR 虚拟屏与混合显示词组追踪同类研究。
- Telegram 确认收到消息后才保存其论文记录。若某个频道的检索未完成，简报会标明，GitHub 运行状态也会显示失败。若 Telegram 已接收消息但运行在保存状态前中断，下一次可能重复推送这一批。
- 可在 `.github/workflows/paper-watch.yml` 修改定时。默认 20 次是**每轮**预算，改为每小时运行前请重新核算预计的每日请求量。

参考：[Semantic Scholar API](https://api.semanticscholar.org/api-docs) · [Telegram Bot API](https://core.telegram.org/bots/api) · [GitHub Actions 定时工作流](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onschedule)
