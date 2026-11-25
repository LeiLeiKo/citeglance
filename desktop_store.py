"""Desktop preferences, protected API keys and paper history."""

import base64
from contextlib import closing
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile

from bot import match_text, paper_ids


INTERVAL_SECONDS = {"分钟": 60, "小时": 3600, "天": 86400}
DEFAULT_SETTINGS = {
    "provider": "Semantic Scholar", "lookback": 14, "budget": 20,
    "custom": {}, "translator": "关闭", "translation_endpoint": "",
    "translation_model": "", "language": "简体中文", "channel": "全部频道",
    "ui_language": "zh",
    "auto_enabled": True, "auto_interval": 1, "auto_unit": "天",
}
DATA_DIRECTORY = Path(os.getenv("LOCALAPPDATA") or (Path.home() / ".local" / "share")) / "PaperWatch"


def read_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as file:
        temporary = Path(file.name)
        try:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.write("\n")
        except Exception:
            file.close()
            temporary.unlink(missing_ok=True)
            raise
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def saved_settings(directory):
    settings = {**DEFAULT_SETTINGS, **read_json(directory / "settings.json", {})}
    interval = settings["auto_interval"]
    if type(interval) is not int or not 1 <= interval <= 365:
        settings["auto_interval"] = DEFAULT_SETTINGS["auto_interval"]
    if settings["auto_unit"] not in tuple(INTERVAL_SECONDS):
        settings["auto_unit"] = DEFAULT_SETTINGS["auto_unit"]
    if type(settings["auto_enabled"]) is not bool:
        settings["auto_enabled"] = DEFAULT_SETTINGS["auto_enabled"]
    return settings


class DataBlob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]


def dpapi(data, *, decrypt=False):
    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source = DataBlob(len(data), buffer)
    result = DataBlob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [
        ctypes.POINTER(DataBlob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DataBlob),
    ]
    function.restype = wintypes.BOOL
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(result)):
        raise ctypes.WinError(ctypes.get_last_error())
    free = ctypes.WinDLL("kernel32").LocalFree
    free.argtypes = [ctypes.c_void_p]
    free.restype = ctypes.c_void_p
    try:
        return ctypes.string_at(result.data, result.size)
    finally:
        free(result.data)


class Secrets:
    def __init__(self, directory):
        self.path = directory / "credentials.json"
        self.session = {}

    def contains(self, slot):
        return slot in self.session or slot in read_json(self.path, {})

    def get(self, slot, fallback=""):
        if slot in self.session:
            return self.session[slot]
        protected = read_json(self.path, {}).get(slot)
        if not protected or os.name != "nt":
            return fallback
        try:
            return dpapi(base64.b64decode(protected, validate=True), decrypt=True).decode("utf-8")
        except (OSError, ValueError):
            raise ValueError("无法解密保存的密钥，请在设置中重新输入。") from None

    def update(self, slot, key, *, remember, clear):
        if not key and not clear:
            return
        existing = read_json(self.path, {})
        if key and remember and os.name == "nt":
            try:
                existing[slot] = base64.b64encode(dpapi(key.encode("utf-8"))).decode("ascii")
            except OSError:
                raise ValueError("Windows 无法保存加密密钥。可以取消记住密钥后再试。") from None
        else:
            existing.pop(slot, None)
        if self.path.exists() or existing:
            write_json(self.path, existing)
        if key:
            self.session[slot] = key
        else:
            self.session.pop(slot, None)


def clean_terms(value):
    return list(dict.fromkeys(phrase.strip() for phrase in re.split(r"[\n,，;；]+", value) if phrase.strip()))


def validate_channels(config):
    if not isinstance(config, dict) or not isinstance(config.get("channels"), list):
        raise ValueError("频道文件需要包含 channels 数组。")
    identifiers = set()
    next_id = config.get("next_channel_id", 1)
    if type(next_id) is not int or next_id < 1:
        raise ValueError("next_channel_id 需要是正整数。")
    for row in config["channels"]:
        identifier = row.get("id") if isinstance(row, dict) else None
        if type(identifier) is not int or identifier < 1 or identifier in identifiers:
            raise ValueError("每个频道需使用唯一且大于零的数字 ID。")
        identifiers.add(identifier)
        if not isinstance(row.get("name"), str) or not row["name"].strip():
            raise ValueError(f"频道 {identifier} 缺少名称。")
        for key in ("a", "b", "focus", "exclude"):
            terms = row.get(key, [])
            if not isinstance(terms, list) or any(not isinstance(x, str) or not match_text(x) for x in terms):
                raise ValueError(f"频道 {identifier} 的 {key} 包含无效词组。")
            if key in ("a", "b") and not terms:
                raise ValueError(f"频道 {identifier} 的 A、B 组各需要至少一个词组。")
    excluded = config.get("exclude", [])
    if not isinstance(excluded, list) or any(not isinstance(x, str) or not match_text(x) for x in excluded):
        raise ValueError("全局屏蔽词列表包含无效词组。")
    return config


def translation_key(paper, language):
    text = paper.get("abstract") or ""
    return language + ":" + hashlib.sha256(text.encode("utf-8")).hexdigest()


class Library:
    def __init__(self, database):
        self.database = database
        database.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS papers (
                    id INTEGER PRIMARY KEY,
                    payload TEXT NOT NULL,
                    appeared TEXT NOT NULL,
                    favorite INTEGER NOT NULL DEFAULT 0,
                    translations TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS identities (
                    identity TEXT PRIMARY KEY,
                    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS search_schedule (
                    id INTEGER PRIMARY KEY CHECK(id = 1),
                    last_started REAL NOT NULL
                );
                """
            )

    def connect(self):
        con = sqlite3.connect(self.database, timeout=10, isolation_level=None)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        return con

    def last_search_started(self):
        with closing(self.connect()) as con:
            row = con.execute("SELECT last_started FROM search_schedule WHERE id=1").fetchone()
            return row["last_started"] if row is not None else None

    def start_search_round(self, now, minimum_interval=0):
        # A single statement claims a due round even if two client windows wake together.
        with closing(self.connect()) as con:
            result = con.execute(
                """
                INSERT INTO search_schedule(id, last_started) VALUES(1, ?)
                ON CONFLICT(id) DO UPDATE SET last_started=excluded.last_started
                WHERE search_schedule.last_started <= excluded.last_started - ?
                """,
                (now, minimum_interval),
            )
            return result.rowcount == 1

    def ingest(self, rows, sources):
        timestamp = datetime.now(timezone.utc).isoformat()
        ids = []
        with closing(self.connect()) as con:
            con.execute("BEGIN IMMEDIATE")
            for paper, matches, aliases, _ in rows:
                paper_id = self.upsert(con, paper, matches, aliases, sources, timestamp)
                if paper_id not in ids:
                    ids.append(paper_id)
            con.commit()
        return ids

    def upsert(self, con, paper, matches, aliases, sources, timestamp):
        keys = sorted(aliases or paper_ids(paper)[0])
        query = ",".join("?" for _ in keys)
        previous = con.execute(
            f"SELECT DISTINCT p.* FROM papers p JOIN identities i ON p.id=i.paper_id "
            f"WHERE i.identity IN ({query}) ORDER BY p.id", keys
        ).fetchall()
        payload = {
            **paper, "sources": [paper.get("source") or sources], "matches": matches,
        }
        combined = {match[0]: match for match in matches}
        first = timestamp
        favorite = False
        translations = {}
        for old in previous:
            stored = json.loads(old["payload"])
            first = min(first, old["appeared"])
            favorite |= bool(old["favorite"])
            translations.update(json.loads(old["translations"]))
            payload["sources"] = list(dict.fromkeys(payload["sources"] + stored["sources"]))
            for key in ("abstract", "publicationDate", "year", "venue", "url", "authors", "keywords", "fieldsOfStudy", "s2FieldsOfStudy", "externalIds"):
                if not payload.get(key) and stored.get(key):
                    payload[key] = stored[key]
                    if key == "keywords":
                        payload["keyword_source"] = stored.get("keyword_source", "")
            for match in stored["matches"]:
                combined.setdefault(match[0], match)
        payload["matches"] = list(combined.values())
        encoded = json.dumps(payload, ensure_ascii=False)
        if previous:
            paper_id = previous[0]["id"]
            for old in previous[1:]:
                con.execute("UPDATE identities SET paper_id=? WHERE paper_id=?", (paper_id, old["id"]))
                con.execute("DELETE FROM papers WHERE id=?", (old["id"],))
            con.execute(
                "UPDATE papers SET payload=?, appeared=?, favorite=?, translations=? WHERE id=?",
                (encoded, first, favorite, json.dumps(translations, ensure_ascii=False), paper_id),
            )
        else:
            paper_id = con.execute("INSERT INTO papers(payload, appeared) VALUES(?, ?)", (encoded, first)).lastrowid
        con.executemany("INSERT OR IGNORE INTO identities(identity, paper_id) VALUES(?, ?)",
                        ((key, paper_id) for key in keys))
        return paper_id

    def list(self, ids=None, favorites=False):
        if ids is not None and not ids:
            return []
        with closing(self.connect()) as con:
            sql = "SELECT * FROM papers"
            if favorites:
                sql += " WHERE favorite=1"
            rows = con.execute(sql + " ORDER BY appeared DESC, id DESC").fetchall()
        records = {
            row["id"]: {**json.loads(row["payload"]), "record_id": row["id"],
                        "favorite": bool(row["favorite"]), "translations": json.loads(row["translations"])}
            for row in rows
        }
        return list(records.values()) if ids is None else [records[key] for key in ids if key in records]

    def set_favorite(self, key, flag):
        with closing(self.connect()) as con:
            con.execute("UPDATE papers SET favorite=? WHERE id=?", (int(flag), key))

    def set_translation(self, key, cache_key, value):
        with closing(self.connect()) as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT translations FROM papers WHERE id=?", (key,)).fetchone()
            if row is not None:
                translations = json.loads(row["translations"])
                translations[cache_key] = value
                con.execute("UPDATE papers SET translations=? WHERE id=?",
                            (json.dumps(translations, ensure_ascii=False), key))
            con.commit()
