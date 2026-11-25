"""Always-on Semantic Scholar tracker with private Telegram commands."""

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import re
import signal
import sqlite3
import sys
from threading import Event, Lock, Thread
import time

import bot


DAY_SECONDS = 86400
HEALTH_MAX_AGE = 100
LOG = logging.getLogger("paper-watch")


def setting_int(name, default, minimum, maximum):
    raw = os.environ.get(name, str(default))
    if not re.fullmatch(r"[0-9]+", raw) or not minimum <= int(raw) <= maximum:
        raise ValueError(f"{name} must be an integer from {minimum} to {maximum}")
    return int(raw)


def setting_secret(name):
    path = os.environ.get(name + "_FILE")
    try:
        value = Path(path).read_text(encoding="utf-8").strip() if path else os.environ.get(name, "").strip()
    except OSError:
        raise ValueError(f"Could not read {name}_FILE") from None
    if not value or any(char.isspace() for char in value):
        raise ValueError(f"Set {name} or {name}_FILE")
    return value


@dataclass(frozen=True)
class Settings:
    api_key: str
    token: str
    chat_id: int
    interval_minutes: int
    daily_budget: int
    run_budget: int
    lookback_days: int

    @classmethod
    def from_env(cls):
        token = setting_secret("TELEGRAM_BOT_TOKEN")
        if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]+", token):
            raise ValueError("TELEGRAM_BOT_TOKEN has an invalid format")
        return cls(
            setting_secret("SEMANTIC_SCHOLAR_API_KEY"), token,
            setting_int("TELEGRAM_CHAT_ID", 0, 1, 2**53 - 1),
            setting_int("PAPER_WATCH_INTERVAL_MINUTES", 1440, 1, 525600),
            setting_int("PAPER_WATCH_DAILY_BUDGET", 20, 1, 10000),
            setting_int("PAPER_WATCH_RUN_BUDGET", 20, 1, 200),
            setting_int("PAPER_WATCH_LOOKBACK_DAYS", 14, 1, 365),
        )


class Store:
    def __init__(self, database):
        self.database = database
        database.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS requests(sent REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS request_time ON requests(sent);
                """
            )

    def connect(self):
        return sqlite3.connect(self.database, timeout=6, isolation_level=None)

    def get(self, key, fallback=None):
        with closing(self.connect()) as con:
            row = con.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else fallback

    def put(self, key, value):
        with closing(self.connect()) as con:
            con.execute("INSERT OR REPLACE INTO state(key,value) VALUES(?,?)", (key, json.dumps(value)))

    def usage(self, now):
        with closing(self.connect()) as con:
            return con.execute(
                "SELECT count(*), min(sent), max(sent) FROM requests WHERE sent>?", (now - DAY_SECONDS,)
            ).fetchone()

    def charge(self, now, limit):
        with closing(self.connect()) as con:
            con.execute("BEGIN IMMEDIATE")
            con.execute("DELETE FROM requests WHERE sent<=?", (now - DAY_SECONDS,))
            used = con.execute("SELECT count(*) FROM requests").fetchone()[0]
            if used >= limit:
                con.rollback()
                return False
            con.execute("INSERT INTO requests(sent) VALUES(?)", (now,))
            con.commit()
            return True


class AlwaysOn:
    def __init__(self, settings, store, channels, excludes, telegram=bot.telegram_call):
        if not channels:
            raise ValueError("Configure at least one search channel")
        if len(channels) > min(settings.daily_budget, settings.run_budget):
            raise ValueError("The per-run and daily budgets must each cover one request per channel")
        self.settings = settings
        self.store = store
        self.channels = channels
        self.excludes = excludes
        self.telegram = telegram
        self.stop = Event()
        self.search_lock = Lock()
        self.worker = None

    def telegram_request(self, method, **params):
        return self.telegram(self.settings.token, method, **params)

    def send(self, message):
        return self.telegram_request("sendMessage", chat_id=self.settings.chat_id, text=message,
                                     link_preview_options={"is_disabled": True})

    def next_due(self):
        last = self.store.get("last_started")
        return 0 if last is None else last + self.settings.interval_minutes * 60

    def budget_remaining(self, now):
        used, _, _ = self.store.usage(now)
        return max(0, self.settings.daily_budget - used)

    def start_round(self, *, automatic=False):
        if self.stop.is_set():
            return "stopped"
        if not self.search_lock.acquire(blocking=False):
            return "busy"
        started = False
        try:
            now = time.time()
            if automatic and now < self.next_due():
                return "waiting"
            budget = min(self.settings.run_budget, self.budget_remaining(now))
            if budget < len(self.channels):
                return "quota"
            self.store.put("last_started", now)
            self.worker = Thread(target=self.finish_round, args=(budget,), daemon=True)
            self.worker.start()
            started = True
            return "started"
        finally:
            if not started:
                self.search_lock.release()

    def charge_request(self):
        now = time.time()
        _, _, last = self.store.usage(now)
        if last is not None and self.stop.wait(max(0, last + 1.05 - now)):
            raise bot.ServiceError("服务正在停止")
        if self.stop.is_set():
            raise bot.ServiceError("服务正在停止")
        if not self.store.charge(time.time(), self.settings.daily_budget):
            raise bot.ServiceError("过去 24 小时的 API 请求额度已用完")

    def finish_round(self, budget):
        try:
            search = bot.PaperSearch(self.settings.api_key, budget=budget, before_request=self.charge_request)
            today = datetime.now(bot.JAPAN_TIME).date()
            state = self.store.get("tracking", {"reported": [], "last_complete": {}})
            papers, failures, complete = bot.scan(
                self.channels, state, today, search, lookback=self.settings.lookback_days
            )
            if self.stop.is_set():
                return
            reported = set(state["reported"])
            rows = bot.ranked_papers(papers, self.channels, self.excludes, reported)
            for i, (message, keys) in enumerate(bot.report_chunks(today, rows, failures, search.used)):
                if i and self.stop.wait(1.05):
                    return
                self.send(message)
                if keys:
                    reported.update(keys)
                    state["reported"] = sorted(reported)
                    self.store.put("tracking", state)
            state["last_complete"].update(dict.fromkeys(complete, today.isoformat()))
            self.store.put("tracking", state)
            self.store.put("last_result", "部分频道未完成" if failures else "完成")
            LOG.info("search completed: %s requests, %s new papers, %s incomplete channels",
                     search.used, len(rows), len(failures))
        except bot.ServiceError as error:
            self.store.put("last_result", "检索或发送简报失败")
            LOG.warning("search or delivery failed (%s)", error.status or type(error).__name__)
        except Exception as error:
            LOG.error("search interrupted (%s)", type(error).__name__)
            self.store.put("last_result", "检索执行失败")
        finally:
            self.search_lock.release()

    def status(self):
        now = time.time()
        due = self.next_due()
        used, oldest, _ = self.store.usage(now)
        if self.settings.daily_budget - used < len(self.channels) and oldest is not None:
            scheduling = "等待过去 24 小时的请求额度恢复"
        elif due > now:
            scheduling = f"下次自动检索约 {datetime.fromtimestamp(due, bot.JAPAN_TIME):%Y-%m-%d %H:%M JST}"
        else:
            scheduling = "自动检索已到期"
        current = " · 正在检索" if self.search_lock.locked() else ""
        outcome = self.store.get("last_result", "尚无记录")
        return (f"论文追踪在线{current}\n{scheduling}\n"
                f"过去 24 小时的请求 · {used}/{self.settings.daily_budget}\n上次结果 · {outcome}")

    def update_offset(self):
        cursor = self.store.get("telegram_cursor", {})
        if time.time() - cursor.get("seen", 0) >= 6 * DAY_SECONDS:
            return 0
        return cursor.get("offset", 0)

    def handle_updates(self, updates):
        offset = self.update_offset()
        for update in sorted(updates, key=lambda entry: entry["update_id"]):
            index = update["update_id"]
            if index < offset:
                continue
            offset = index + 1
            self.store.put("telegram_cursor", {"offset": offset, "seen": time.time()})
            message = update.get("message") or {}
            chat = message.get("chat") or {}
            sender = message.get("from") or {}
            if (chat.get("type") != "private" or chat.get("id") != self.settings.chat_id
                    or sender.get("id") != self.settings.chat_id):
                continue
            command = (message.get("text") or "").strip().partition(" ")[0].partition("@")[0]
            if command in ("/start", "/help"):
                self.send("论文追踪 Bot\n/status 查看状态和用量\n/search 立即检索全部频道")
            elif command == "/status":
                self.send(self.status())
            elif command == "/search":
                result = self.start_round()
                self.send({
                    "started": "已启动检索，完成后会在这里发送简报。",
                    "busy": "当前已在检索，完成后会发送简报。",
                    "quota": "过去 24 小时的剩余额度不足以检索全部频道。请用 /status 查看。",
                    "stopped": "服务正在停止。",
                }[result])

    def run(self):
        delay = 1
        while not self.stop.is_set():
            try:
                updates = self.telegram_request("getUpdates", timeout=12,
                                                offset=self.update_offset(),
                                                allowed_updates=["message"])
                if not isinstance(updates, list):
                    raise bot.ServiceError("Telegram returned an invalid update list")
                if self.stop.is_set():
                    break
                self.store.put("poll_ok", time.time())
                self.handle_updates(updates)
                self.start_round(automatic=True)
                delay = 1
            except bot.ServiceError as error:
                LOG.warning("Telegram request failed (%s)", error.status or type(error).__name__)
                self.stop.wait(max(delay, error.retry_after))
                delay = min(delay * 2, 60)
        if self.worker:
            self.worker.join(timeout=20)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    database = Path(os.environ.get("PAPER_WATCH_DATA_DIR", "data")) / "server.sqlite3"
    if sys.argv[1:] == ["--healthcheck"]:
        if not database.is_file():
            return 1
        last_poll = Store(database).get("poll_ok", 0)
        return 0 if 0 <= time.time() - last_poll < HEALTH_MAX_AGE else 1
    if sys.argv[1:]:
        print("Usage: python server.py [--healthcheck]", file=sys.stderr)
        return 2
    try:
        settings = Settings.from_env()
        channels, excludes = bot.load_channels()
        service = AlwaysOn(settings, Store(database), channels, excludes)
    except (ValueError, OSError, sqlite3.Error) as error:
        LOG.error("Startup failed: %s", error)
        return 1
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: service.stop.set())
    LOG.info("Paper Watch started: %s channels, interval %s minutes", len(channels), settings.interval_minutes)
    service.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
