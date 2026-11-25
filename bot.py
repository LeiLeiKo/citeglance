import argparse
from collections import deque
from datetime import date, datetime, timedelta, timezone
import getpass
import json
import os
from pathlib import Path
import re
import sys
import time
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen


ROOT = Path(__file__).resolve().parent
STATE_FILE = ROOT / "state.json"
SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"
FIELDS = "title,abstract,publicationDate,year,venue,url,externalIds,authors"
REQUEST_BUDGET = 20
APP_NAME = "CiteGlance"
APP_TITLE = "CiteGlance · 文献雷达"
JAPAN_TIME = timezone(timedelta(hours=9))


class ServiceError(Exception):
    def __init__(self, label, status=None, retry_after=""):
        super().__init__(label)
        self.status = status
        self.retry_after = int(retry_after) if retry_after.isdecimal() else 0


class RejectRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_json(url, *, service, headers=None, body=None, redirects=True):
    headers = dict(headers or {})
    if body is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(body).encode("utf-8")
    request = Request(url, data=body, headers=headers)
    open_request = urlopen if redirects else build_opener(RejectRedirect()).open
    try:
        with open_request(request, timeout=20) as response:
            return json.load(response)
    except HTTPError as error:
        status = error.code
        retry_after = error.headers.get("Retry-After", "")
        error.close()
        raise ServiceError(f"{service} HTTP {status}", status, retry_after) from None
    except (URLError, TimeoutError, OSError):
        raise ServiceError(f"{service} 网络连接失败") from None
    except (ValueError, UnicodeError):
        raise ServiceError(f"{service} 返回了无法解析的结果") from None


class PaperSearch:
    def __init__(self, api_key, *, fields=FIELDS, budget=REQUEST_BUDGET, before_request=None):
        self.api_key = api_key
        self.fields = fields
        self.budget = budget
        self.before_request = before_request
        self.used = 0
        self.last_started = None

    def page(self, query, start, today, token):
        params = {
            "query": query,
            "publicationDateOrYear": f"{start}:{today}",
            "fields": self.fields,
            "sort": "publicationDate:desc",
        }
        if token:
            params["token"] = token
        url = f"{SEARCH_URL}?{urlencode(params)}"
        for attempt in range(3):
            if self.used >= self.budget:
                raise ServiceError(f"已用完本次运行的 {self.budget} 次请求预算")
            if self.last_started is not None:
                time.sleep(max(0, self.last_started + 1.05 - time.monotonic()))
            if self.before_request is not None:
                self.before_request()
            self.last_started = time.monotonic()
            self.used += 1
            try:
                result = request_json(
                    url, service="Semantic Scholar", headers={"x-api-key": self.api_key}
                )
                if not isinstance(result, dict) or not isinstance(result.get("data"), list):
                    raise ServiceError("Semantic Scholar 返回的检索结果缺少 data")
                return result
            except ServiceError as error:
                retryable = error.status in {None, 429, 500, 502, 503, 504}
                if not retryable or attempt == 2 or error.retry_after > 45:
                    raise
                if self.used < self.budget:
                    time.sleep(max(error.retry_after, 2 ** (attempt + 1)))


def match_text(value):
    return " ".join(re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", value).casefold()))


def phrase_pattern(phrase):
    # Allow punctuation and hyphen variation via normalized text, plus simple plurals.
    phrase = match_text(phrase)
    suffix = "" if phrase.endswith("s") else "s?"
    return re.compile(r"\b" + re.escape(phrase) + suffix + r"\b")


def matching_terms(patterns, normalized_title, normalized_abstract):
    return [
        phrase for phrase, pattern in patterns
        if pattern.search(normalized_title) or pattern.search(normalized_abstract)
    ]


def load_channels(config=None):
    if config is None:
        config = json.loads((ROOT / "channels.json").read_text(encoding="utf-8"))
    channels = []
    for value in config["channels"]:
        channel = dict(value)
        groups = []
        for group in ("a", "b"):
            groups.append(
                "(" + " | ".join(json.dumps(term, ensure_ascii=False) for term in channel[group]) + ")"
            )
            channel[group + "_patterns"] = [
                (term, phrase_pattern(term)) for term in channel[group]
            ]
        if channel.get("focus"):
            groups.append(
                "(" + " | ".join(json.dumps(term, ensure_ascii=False) for term in channel["focus"]) + ")"
            )
        channel["query"] = " + ".join(groups)
        for group in ("focus", "exclude"):
            channel[group + "_patterns"] = [
                (term, phrase_pattern(term)) for term in channel.get(group, [])
            ]
        channels.append(channel)
    exclude = [(term, phrase_pattern(term)) for term in config.get("exclude", [])]
    return channels, exclude


def load_state():
    if not STATE_FILE.exists():
        return {"reported": [], "last_complete": {}}
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def save_state(state):
    temp_file = STATE_FILE.with_suffix(".tmp")
    temp_file.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temp_file.replace(STATE_FILE)


def scan(channels, state, today, search, *, lookback=14, query_for=None):
    papers = []
    failures = []
    complete = []
    queue = deque((channel, None, False) for channel in channels)
    baseline = today - timedelta(days=lookback - 1)
    deferred = deque()
    budget = search.budget
    while queue or deferred:
        if queue:
            channel, token, retried = queue.popleft()
        else:
            channel, token, due = deferred.popleft()
            if search.used < budget:
                time.sleep(max(0, due - time.monotonic()))
            retried = True
        if search.used >= budget:
            failures.append((channel["id"], "已达请求预算"))
            continue
        last = state["last_complete"].get(str(channel["id"]))
        start = min(baseline, date.fromisoformat(last)) if last else baseline
        try:
            query = query_for(channel) if query_for else channel["query"]
            page = search.page(query, start, today, token)
        except ServiceError as error:
            if error.status == 429 and not error.retry_after and not retried:
                deferred.append((channel, token, time.monotonic() + 15))
                continue
            failures.append((channel["id"], str(error)))
            continue
        papers.extend(page["data"])
        next_token = page.get("token")
        if next_token and next_token != token:
            queue.append((channel, next_token, retried))
        elif next_token:
            failures.append((channel["id"], "检索返回重复的分页标记"))
        else:
            complete.append(str(channel["id"]))
    return papers, failures, complete


def paper_ids(paper):
    title = match_text(paper["title"])
    identifiers = {"title:" + title}
    if paper.get("paperId"):
        identifiers.add("s2:" + paper["paperId"])
    external = paper.get("externalIds") or {}
    doi = (external.get("DOI") or "").strip()
    if doi:
        identifiers.add("doi:" + doi.casefold())
    if external.get("ArXiv"):
        arxiv = re.sub(r"v[0-9]+$", "", external["ArXiv"], flags=re.I)
        identifiers.add("arxiv:" + arxiv.casefold())
    return identifiers, doi


def is_preprint(paper):
    venue = match_text(paper.get("venue") or "")
    external = paper.get("externalIds") or {}
    doi = (external.get("DOI") or "").lower()
    return bool(
        venue.startswith("arxiv")
        or doi.startswith("10.48550/arxiv.")
        or (external.get("ArXiv") and not venue and not doi)
    )


def ranked_papers(papers, channels, exclude, reported):
    candidates = []
    for paper in papers:
        if not isinstance(paper, dict) or not paper.get("title"):
            continue
        title = match_text(paper["title"])
        abstract = match_text(paper.get("abstract") or "")
        if matching_terms(exclude, title, abstract):
            continue
        matches = []
        for channel in channels:
            if matching_terms(channel["exclude_patterns"], title, abstract):
                continue
            focus = channel["focus_patterns"]
            if focus and not matching_terms(focus, title, abstract):
                continue
            terms_a = matching_terms(channel["a_patterns"], title, abstract)
            terms_b = matching_terms(channel["b_patterns"], title, abstract)
            if terms_a and terms_b:
                matches.append((channel["id"], terms_a[0], terms_b[0]))
        if matches:
            identifiers, doi = paper_ids(paper)
            candidates.append((paper, matches, identifiers, doi))

    # Prefer venue versions when the same preprint is also in today's results.
    candidates.sort(
        key=lambda row: (
            not is_preprint(row[0]),
            bool(row[3]),
            row[0].get("publicationDate") or "",
        ),
        reverse=True,
    )
    selected = []
    known = set(reported)
    for paper, matches, identifiers, doi in candidates:
        if not identifiers.isdisjoint(known):
            for existing in selected:
                if not existing[2].isdisjoint(identifiers):
                    existing[2].update(identifiers)
                    matched_ids = {match[0] for match in existing[1]}
                    existing[1].extend(match for match in matches if match[0] not in matched_ids)
                    known.update(identifiers)
                    break
            continue
        known.update(identifiers)
        selected.append((paper, matches, identifiers, doi))

    def display_priority(row):
        paper, matches, _, _ = row
        pavanatto = any(
            "pavanatto" in match_text(author.get("name") or "")
            for author in (paper.get("authors") or [])
        )
        primary = min(match[0] for match in matches)
        return -primary, primary == 1 and pavanatto, paper.get("publicationDate") or ""

    return sorted(selected, key=display_priority, reverse=True)


def format_entry(row):
    paper, matches, identifiers, doi = row
    title = " ".join(paper["title"].split())
    publication = paper.get("publicationDate") or f"{paper.get('year') or '未知年份'}（日期不详）"
    venue = "预印本" if is_preprint(paper) else (paper.get("venue") or "发表渠道未确认")
    channels = "；".join(
        f"频道 {number} 命中 {term_a} × {term_b}" for number, term_a, term_b in sorted(matches)
    )
    link = f"https://doi.org/{quote(doi, safe='/')}" if doi else (paper.get("url") or "")
    lines = [title, f"{publication} · {venue}", channels]
    if link:
        lines.append(link)
    return "\n".join(lines), identifiers


def report_chunks(today, rows, failures, used):
    heading = f"{APP_TITLE}｜{today}（日本时间）\n本次新发现 {len(rows)} 篇 · Semantic Scholar 请求 {used} 次"
    if failures:
        heading += "\n检索未完成：" + "；".join(
            f"频道 {number}（{reason}）" for number, reason in sorted(failures)
        )
    if not rows:
        heading += "\n" + ("其余结果中暂无新论文。" if failures else "本次无符合条件的新论文。")
    message = heading
    keys = set()
    for row in rows:
        entry, identifiers = format_entry(row)
        # Count UTF-16 units conservatively and reserve room below Telegram's 4096 limit.
        raw = entry.encode("utf-16-le")
        if len(raw) > 6600:
            entry = raw[:6598].decode("utf-16-le", errors="ignore") + "…"
        if len((message + "\n\n" + entry).encode("utf-16-le")) > 7600:
            yield message, keys
            message = f"{APP_TITLE}｜{today}（续）"
            keys = set()
        message += "\n\n" + entry
        keys.update(identifiers)
    yield message, keys


def telegram_call(token, method, **params):
    if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]+", token):
        raise ServiceError("Telegram Bot Token 格式无效")
    data = request_json(
        f"https://api.telegram.org/bot{token}/{method}", service="Telegram", body=params
    )
    if not isinstance(data, dict) or not data.get("ok"):
        raise ServiceError("Telegram 未确认操作成功")
    return data["result"]


def main():
    parser = argparse.ArgumentParser(description=f"{APP_NAME} · Semantic Scholar 论文追踪")
    argparse_modes = parser.add_mutually_exclusive_group()
    argparse_modes.add_argument("--chat-id", action="store_true", help="安全查询 Telegram 私聊 ID")
    argparse_modes.add_argument("--dry-run", action="store_true", help="只在终端预览")
    args = parser.parse_args()

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if args.chat_id:
        token = token or getpass.getpass("Telegram Bot Token（输入时隐藏）：").strip()
        updates = telegram_call(token, "getUpdates", allowed_updates=["message"])
        private_ids = {
            chat["id"] for update in updates
            if (chat := update.get("message", {}).get("chat", {})).get("type") == "private"
        }
        if not private_ids:
            raise ServiceError("没有发现私聊。请在 Telegram 向机器人发送 /start 后重试。")
        for chat_id in sorted(private_ids):
            print(chat_id)
        return 0

    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "").strip()
    if not api_key:
        raise ServiceError("请配置 SEMANTIC_SCHOLAR_API_KEY")
    dry_run = args.dry_run or os.getenv("PAPER_WATCH_DRY_RUN", "").lower() == "true"
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not dry_run and (not token or not re.fullmatch(r"[1-9][0-9]*", chat_id)):
        raise ServiceError("请配置 TELEGRAM_BOT_TOKEN 和数字格式的 Telegram 私聊 ID")

    today = datetime.now(JAPAN_TIME).date()
    channels, excluded = load_channels()
    state = load_state()
    search = PaperSearch(api_key)
    papers, failures, complete = scan(channels, state, today, search)
    reported = set(state["reported"])
    rows = ranked_papers(papers, channels, excluded, reported)
    for index, (message, keys) in enumerate(report_chunks(today, rows, failures, search.used)):
        if dry_run:
            print(message)
            continue
        if index:
            time.sleep(1.05)
        telegram_call(
            token, "sendMessage", chat_id=int(chat_id), text=message,
            link_preview_options={"is_disabled": True},
        )
        if keys:
            reported.update(keys)
            state["reported"] = sorted(reported)
            save_state(state)
    if not dry_run and complete:
        state["last_complete"].update(dict.fromkeys(complete, today.isoformat()))
        save_state(state)
    if failures:
        print("至少一个频道检索未完成，请查看简报。", file=sys.stderr)
        return 1
    print(f"完成。新发现 {len(rows)} 篇，检索请求 {search.used} 次。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ServiceError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
