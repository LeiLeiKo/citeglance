"""Small Linux-side deployment helper, invoked by the desktop over SSH."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


FILES = {"Dockerfile", ".dockerignore", "compose.yaml", "server.py", "bot.py"}
ENV_NAMES = {"TELEGRAM_CHAT_ID", "PAPER_WATCH_INTERVAL_MINUTES",
             "PAPER_WATCH_DAILY_BUDGET", "PAPER_WATCH_RUN_BUDGET"}


def run(args, work=None):
    return subprocess.run(args, cwd=work, stdin=subprocess.DEVNULL, check=True)


def atomic_file(path, text, mode):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        staging = Path(handle.name)
        handle.write(text.encode("utf-8"))
    try:
        os.chmod(staging, mode)
        staging.replace(path)
    finally:
        staging.unlink(missing_ok=True)


def install_files(root, content):
    files = content["files"]
    env = content["env"]
    secrets = {"semantic_scholar_api_key": content["scholar"], "telegram_bot_token": content["token"]}
    channels = content["channels"]
    if set(files) != FILES or set(env) != ENV_NAMES or any(type(v) is not int or v < 1 for v in env.values()):
        raise ValueError("Invalid deployment payload")
    if not all(isinstance(value, str) and value and len(value) < 500000 for value in files.values()):
        raise ValueError("Invalid deployment files")
    if not isinstance(channels, dict) or not channels.get("channels"):
        raise ValueError("No search channels")
    if not all(isinstance(value, str) and value and not any(char.isspace() for char in value)
               for value in secrets.values()):
        raise ValueError("Invalid credentials")
    root.mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chmod(root, 0o700)
    secret_dir = root / ".secrets"
    secret_dir.mkdir(mode=0o700, exist_ok=True)
    os.chmod(secret_dir, 0o700)
    for name, text in files.items():
        atomic_file(root / name, text, 0o644)
    atomic_file(root / "channels.json", json.dumps(channels, ensure_ascii=False, indent=2) + "\n", 0o644)
    atomic_file(root / ".env", "".join(f"{key}={value}\n" for key, value in env.items()), 0o600)
    for name, secret in secrets.items():
        atomic_file(secret_dir / name, secret + "\n", 0o444)


def execute(action, root):
    if action not in ("check", "deploy", "status", "logs"):
        raise ValueError("Invalid deployment action")
    if sys.platform != "linux":
        raise ValueError("The cloud host must run Linux")
    docker = shutil.which("docker")
    if not docker:
        raise ValueError("Docker is missing. Choose a Docker-ready Linux image or install Docker Engine and Compose.")
    if action in ("check", "deploy"):
        run([docker, "compose", "version", "--short"])
        run([docker, "info", "--format", "{{.ServerVersion}}"])
    if action == "check":
        print("SSH, Python 3, Docker Engine and Docker Compose are ready.")
        return
    root = root.resolve()
    if action == "deploy":
        install_files(root, json.load(sys.stdin))
    if not (root / "compose.yaml").is_file():
        raise ValueError("CiteGlance has not been deployed from the client on this host.")
    compose = [docker, "compose", "--project-name", "paper-watch"]
    if action == "deploy":
        run(compose + ["config", "--quiet"], root)
        run(compose + ["up", "-d", "--build", "--force-recreate"], root)
        print("CiteGlance deployment submitted. Check container status and test /status in Telegram.")
    if action in ("deploy", "status"):
        run(compose + ["ps", "-a"], root)
    if action == "logs":
        run(compose + ["logs", "--no-color", "--tail=80", "paper-watch"], root)


if __name__ == "__main__":
    try:
        action = sys.argv[1] if len(sys.argv) == 2 else ""
        execute(action, Path.home() / ".local" / "share" / "paper-watch-managed")
    except subprocess.CalledProcessError as error:
        print(f"Docker command failed (exit {error.returncode}).", file=sys.stderr)
        sys.exit(1)
    except (ValueError, OSError, KeyError) as error:
        print(f"CiteGlance: {error}", file=sys.stderr)
        sys.exit(1)
