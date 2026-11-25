"""Deploy the bundled service through the user's Windows OpenSSH client."""

import base64
from dataclasses import dataclass
import ipaddress
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess

import bot


FILES = ("Dockerfile", ".dockerignore", "compose.yaml", "server.py", "bot.py")
ACTIONS = ("check", "deploy", "status", "logs")
DEFAULT_PROFILE = {
    "host": "", "user": "ubuntu", "port": 22, "identity": "", "chat_id": "",
    "minutes": 1440, "daily_time": "", "budget": 20,
}


def checked_int(value, low, high, message):
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError(message) from None
    if not low <= number <= high:
        raise ValueError(message)
    return number


@dataclass(frozen=True)
class Target:
    host: str
    user: str
    port: int
    identity: str

    @classmethod
    def from_fields(cls, fields):
        host = fields["host"].strip()
        if host.startswith("[") and host.endswith("]"):
            host = host[1:-1]
        try:
            if "%" in host:
                raise ValueError()
            host = str(ipaddress.ip_address(host))
        except ValueError:
            labels = host.rstrip(".").split(".")
            if len(host) > 253 or not all(
                re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", label)
                for label in labels
            ):
                raise ValueError("请输入有效的服务器 IP 或域名。") from None
            host = host.lower()
        user = fields["user"].strip()
        if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_.-]{0,31}", user):
            raise ValueError("请输入有效的 SSH 用户名。")
        port = checked_int(fields["port"], 1, 65535, "SSH 端口需为 1–65535 的整数。")
        identity = fields["identity"].strip()
        if identity and not Path(identity).expanduser().is_file():
            raise ValueError("找不到指定的 SSH 私钥文件。")
        return cls(host, user, port, str(Path(identity).expanduser().resolve()) if identity else "")

    @property
    def identity_slot(self):
        return f"{self.user}@{self.host}:{self.port}"

    def ssh_args(self, *, interactive=False):
        executable = shutil.which("ssh")
        if not executable:
            raise ValueError("找不到 OpenSSH 客户端。请启用 Windows 的 OpenSSH Client。")
        args = [
            executable, "-p", str(self.port), "-o", "ConnectTimeout=12", "-o", "ForwardAgent=no",
            "-o", "ClearAllForwardings=yes", "-o",
            "StrictHostKeyChecking=ask" if interactive else "StrictHostKeyChecking=yes",
            "-o", "BatchMode=no" if interactive else "BatchMode=yes",
        ]
        if self.identity:
            args.extend(["-o", "IdentitiesOnly=yes", "-i", self.identity])
        if not interactive:
            args.extend(["-T", "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=3"])
        return args + ["-l", self.user, self.host]


def open_ssh_window(target):
    if not hasattr(subprocess, "CREATE_NEW_CONSOLE"):
        raise ValueError("请在终端运行 SSH，确认服务器指纹并完成首次连接。")
    subprocess.Popen(target.ssh_args(interactive=True), creationflags=subprocess.CREATE_NEW_CONSOLE)


def load_deployment(root, channels, telegram_token, scholar_key, fields):
    token = telegram_token.strip()
    key = scholar_key.strip()
    if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]+", token):
        raise ValueError("请填写有效的 Telegram Bot Token。")
    if not key or any(char.isspace() or ord(char) < 32 for char in key):
        raise ValueError("请填写 Semantic Scholar API Key，或先在客户端保存该密钥。")
    chat = checked_int(fields["chat_id"], 1, 2**53 - 1, "请输入数字格式的 Telegram 私聊 ID。")
    daily_time = fields.get("daily_time", "").strip()
    if daily_time and not bot.valid_daily_time(daily_time):
        raise ValueError("请输入 24 小时制的检索时间，格式为 HH:MM（如 09:30）。")
    minutes = DEFAULT_PROFILE["minutes"]
    if not daily_time:
        minutes = checked_int(fields["minutes"], 1, 525600, "检索间隔需为 1–525600 分钟。")
    budget = checked_int(fields["budget"], 1, 10000, "每日请求上限需为 1–10000 的整数。")
    channel_count = len(channels["channels"])
    if not 1 <= channel_count <= min(budget, bot.REQUEST_BUDGET):
        raise ValueError("请配置至少一个频道，并让每日及每轮额度覆盖全部频道。")
    try:
        files = {name: (root / name).read_text(encoding="utf-8") for name in FILES}
    except OSError:
        raise ValueError("当前客户端缺少云端部署文件，请使用完整新版安装包。") from None
    env = {
        "TELEGRAM_CHAT_ID": chat,
        "PAPER_WATCH_INTERVAL_MINUTES": minutes,
        "PAPER_WATCH_DAILY_TIME": daily_time,
        "PAPER_WATCH_DAILY_BUDGET": budget,
        "PAPER_WATCH_RUN_BUDGET": bot.REQUEST_BUDGET,
    }
    return {"files": files, "channels": channels, "token": token, "scholar": key, "env": env}


def private_chat_id(token):
    if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]+", token):
        raise ValueError("请填写有效的 Telegram Bot Token。")
    try:
        updates = bot.telegram_call(token, "getUpdates", timeout=0, allowed_updates=["message"])
    except bot.ServiceError as error:
        if error.status == 409:
            raise ValueError("这个 Bot 已被其它实例使用，请手动填写现有私聊 ID。") from None
        raise
    if not isinstance(updates, list):
        raise ValueError("Telegram 未返回有效的私聊记录。")
    ids = set()
    for item in updates:
        message = item.get("message") or {}
        chat = message.get("chat") or {}
        if chat.get("type") == "private" and chat.get("id") == (message.get("from") or {}).get("id"):
            ids.add(chat["id"])
    if len(ids) != 1:
        raise ValueError("请先在 Telegram 私聊机器人发送 /start，再获取私聊 ID。多个私聊时请手动填写。")
    return ids.pop()


def run_remote(root, target, action, payload=None):
    if action not in ACTIONS:
        raise ValueError("Invalid deployment action")
    try:
        helper = (root / "cloud_remote.py").read_bytes()
    except OSError:
        raise ValueError("当前客户端缺少云端部署文件，请使用完整新版安装包。") from None
    encoded = base64.b64encode(helper).decode("ascii")
    python = f'import base64; exec(compile(base64.b64decode("{encoded}"), "<paper-watch>", "exec"))'
    command = "python3 -c " + shlex.quote(python) + " " + action
    request = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload else b""
    try:
        run = subprocess.run(
            target.ssh_args() + [command], input=request, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=720 if action == "deploy" else 45,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=False,
        )
    except subprocess.TimeoutExpired:
        raise ValueError("服务器操作超时。请先查看状态和日志，再决定是否重试。") from None
    output = run.stdout.decode("utf-8", errors="replace")
    if payload:
        for secret in (payload["scholar"], payload["token"]):
            output = output.replace(secret, "********")
    output = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", output)
    if run.returncode == 255:
        output = output[:4000]
        if re.search(r"host key|REMOTE HOST IDENTIFICATION", output, re.I):
            raise ValueError("SSH 主机指纹未确认或已变化。请核对服务器指纹后再连接。")
        if "Permission denied" in output:
            raise ValueError("SSH 密钥登录失败。请确认服务器已添加公钥，需口令的私钥可先加载到 SSH Agent。")
    return run.returncode == 0, output.strip()[-24000:]
