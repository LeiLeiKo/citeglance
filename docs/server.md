# Linux 服务器常驻部署

[返回项目首页](../README.md)

Docker 版本在 Linux 云服务器上常驻运行。它使用 Semantic Scholar 检索 `channels.json` 中的频道，把简报发到指定的 Telegram 私聊。这个服务通过 Telegram 长轮询接收命令，只需服务器能够向 Semantic Scholar 和 Telegram 发起 HTTPS 请求。

| Telegram 指令 | 用途 |
| --- | --- |
| `/status` | 查看在线状态、下次预计检索、近期请求用量和上次结果 |
| `/search` | 请求立即检索全部频道，完成后接收简报 |
| `/help` | 查看指令说明 |

## 1. 准备服务器和私人 Bot

- 使用一台持续在线、可运行 Docker Engine 和 Compose 插件的 Linux 服务器。Ubuntu 可按 [Docker 官方安装指南](https://docs.docker.com/engine/install/ubuntu/)安装。
- 在 Telegram 中通过 `@BotFather` 创建 Bot，打开私聊并发送 `/start`。可以在现有 Windows 客户端目录运行 `python -X utf8 bot.py --chat-id`，从隐藏输入框输入 Bot Token，获取自己的数字私聊 ID。
- 将源码包解压到服务器，或在服务器配置好私有仓库访问后克隆此项目。以下命令均在服务器的项目根目录运行。
- 同一个 Bot Token 保留一个长轮询进程。若用同一枚 Semantic Scholar Key 运行其他定时器，服务器无法统计那些调用。切换部署方式时，可以先关闭原有 GitHub Actions 日程或桌面定时检索。

## 2. 配置服务器

复制模板并编辑非密钥设置：

~~~~bash
cp .env.example .env
nano .env
~~~~

填写 `TELEGRAM_CHAT_ID`。`PAPER_WATCH_INTERVAL_MINUTES` 默认是 `1440`，即每 24 小时一轮。要每小时检索，可改为 `60`。`PAPER_WATCH_DAILY_BUDGET` 默认是滚动 24 小时 `20` 次，两种触发方式共用这个额度，分页和重试也计入。四个频道每轮基础需 4 次请求，按每小时检索的基础用量是 96 次／24 小时。额度不足时，服务会等待额度恢复。

以下 Bash 命令会提示你分别粘贴两项密钥，输入时隐藏。密钥文件所在目录仅当前服务器账户可访问，文件设为容器内的非 root 用户可读。

~~~~bash
install -d -m 700 .secrets
(umask 077
read -rsp 'Semantic Scholar API Key: ' PAPER_WATCH_INPUT
printf '\n'
printf '%s\n' "$PAPER_WATCH_INPUT" > .secrets/semantic_scholar_api_key
read -rsp 'Telegram Bot Token: ' PAPER_WATCH_INPUT
printf '\n'
printf '%s\n' "$PAPER_WATCH_INPUT" > .secrets/telegram_bot_token
chmod 444 .secrets/semantic_scholar_api_key .secrets/telegram_bot_token)
~~~~

## 3. 启动并验证

~~~~bash
docker compose up -d --build
docker compose ps
docker compose logs --tail=50 paper-watch
~~~~

在 Telegram 私聊中发 `/status` 验证响应。首次启动且额度充足时，会自动检索一轮。容器可随 Docker 重启恢复，SQLite 数据卷保存检索进度、已报告论文、请求额度和 Telegram 更新位置。

## 更新与维护

- 修改 `channels.json` 或 `.env` 后运行 `docker compose up -d --force-recreate`。更新代码后运行 `docker compose up -d --build`。
- 查看运行日志用 `docker compose logs -f paper-watch`，暂停服务用 `docker compose stop`，之后可用 `docker compose start` 恢复。保留名为 `paper-watch-data` 的数据卷可延续去重和用量记录。
- 若日志反复出现 Telegram `409`，检查这个 Token 是否还被另一个实例或 webhook 使用。若出现 `401`，核对 Telegram Bot Token 与 Semantic Scholar API Key 分别对应的密钥文件。
- 默认没有将容器端口发布到公网。常驻版本的交互入口是 Telegram 私聊。
