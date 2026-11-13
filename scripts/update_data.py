#!/usr/bin/env python3
"""Build same-origin JSON for the Arsenal info center.

News, podcasts, and fixtures are fetched here (GitHub Actions or a local run).
The browser only reads the JSON files this script writes. football-data.org is
not a source in v1: a failed API-Football fetch keeps the last good cache
instead of quietly switching providers.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

SH = ZoneInfo("Asia/Shanghai")
UA = (
    "arsenal-info-center/1.0 "
    "(+https://github.com/tulifulegend/arsenal-info-center; "
    "personal non-commercial; titles, short excerpts, links)"
)
API_BASE = "https://v3.football.api-sports.io"
TEAM_ID = 42
DAILY_REQUEST_CAP = 80
EXCERPT_LIMIT = 150
NEWS_PER_SOURCE = 15
PODCAST_PER_KIND = 6
MAX_BYTES = 12_000_000
FULL_INTERVAL = timedelta(hours=8)
WINDOW_INTERVAL = timedelta(minutes=25)
FAIL_BACKOFF = timedelta(hours=2)

NEWS_SOURCES = (
    {
        "id": "arseblog",
        "name": "Arseblog",
        "url": "https://arseblog.com/feed/",
    },
    {
        "id": "guardian",
        "name": "卫报",
        "url": "https://www.theguardian.com/football/arsenal/rss",
    },
)
PODCAST_URL = "https://rss.acast.com/arseblog"

# League Cup is the cup we should already see in a normal season dump.
CUP_IDS = {2, 3, 45, 48, 528, 848}
FINISHED = {"FT", "AET", "PEN", "AWD", "WO"}
SCHEDULED = {"NS", "TBD"}
CANCELLED = {"CANC", "ABD"}
POSTPONED = {"PST"}
INPLAY = {"1H", "HT", "2H", "ET", "BT", "P", "LIVE", "INT", "SUSP"}

COMP_BY_ID = {
    39: "英超",
    2: "欧冠",
    3: "欧联",
    848: "欧协联",
    45: "足总杯",
    48: "联赛杯",
    528: "社区盾",
    531: "欧洲超级杯",
}
COMP_BY_NAME = (
    ("premier league", "英超"),
    ("champions league", "欧冠"),
    ("europa conference", "欧协联"),
    ("conference league", "欧协联"),
    ("europa league", "欧联"),
    ("fa cup", "足总杯"),
    ("efl cup", "联赛杯"),
    ("carabao", "联赛杯"),
    ("league cup", "联赛杯"),
    ("community shield", "社区盾"),
    ("super cup", "欧洲超级杯"),
    ("friendly", "友谊赛"),
)

TEAM_ZH = {
    "arsenal": "阿森纳",
    "manchester united": "曼联",
    "manchester city": "曼城",
    "liverpool": "利物浦",
    "chelsea": "切尔西",
    "tottenham": "热刺",
    "tottenham hotspur": "热刺",
    "newcastle": "纽卡斯尔",
    "newcastle united": "纽卡斯尔",
    "aston villa": "阿斯顿维拉",
    "brighton": "布莱顿",
    "brighton and hove albion": "布莱顿",
    "west ham": "西汉姆",
    "west ham united": "西汉姆",
    "crystal palace": "水晶宫",
    "brentford": "布伦特福德",
    "fulham": "富勒姆",
    "wolves": "狼队",
    "wolverhampton wanderers": "狼队",
    "everton": "埃弗顿",
    "nottingham forest": "诺丁汉森林",
    "bournemouth": "伯恩茅斯",
    "afc bournemouth": "伯恩茅斯",
    "leicester": "莱斯特城",
    "leicester city": "莱斯特城",
    "ipswich": "伊普斯维奇",
    "ipswich town": "伊普斯维奇",
    "southampton": "南安普顿",
    "leeds": "利兹联",
    "leeds united": "利兹联",
    "burnley": "伯恩利",
    "sunderland": "桑德兰",
    "luton": "卢顿",
    "luton town": "卢顿",
    "sheffield united": "谢菲尔德联",
    "sheffield utd": "谢菲尔德联",
    "hull city": "赫尔城",
    "real madrid": "皇家马德里",
    "barcelona": "巴塞罗那",
    "atletico madrid": "马德里竞技",
    "bayern munich": "拜仁慕尼黑",
    "bayern munchen": "拜仁慕尼黑",
    "borussia dortmund": "多特蒙德",
    "paris saint germain": "巴黎圣日耳曼",
    "inter": "国际米兰",
    "ac milan": "AC米兰",
    "juventus": "尤文图斯",
    "napoli": "那不勒斯",
    "roma": "罗马",
    "lazio": "拉齐奥",
    "atalanta": "亚特兰大",
    "benfica": "本菲卡",
    "porto": "波尔图",
    "sporting cp": "葡萄牙体育",
    "sporting": "葡萄牙体育",
    "ajax": "阿贾克斯",
    "psv eindhoven": "PSV埃因霍温",
    "feyenoord": "费耶诺德",
    "celtic": "凯尔特人",
    "rangers": "流浪者",
    "galatasaray": "加拉塔萨雷",
    "bayer leverkusen": "勒沃库森",
    "rb leipzig": "莱比锡",
    "marseille": "马赛",
    "lyon": "里昂",
    "monaco": "摩纳哥",
    "villarreal": "比利亚雷亚尔",
    "real sociedad": "皇家社会",
    "athletic club": "毕尔巴鄂竞技",
    "sevilla": "塞维利亚",
    "girona": "赫罗纳",
    "slavia prague": "布拉格斯拉维亚",
    "slavia praha": "布拉格斯拉维亚",
    "shakhtar donetsk": "顿涅茨克矿工",
    "club brugge": "布鲁日",
    "sporting braga": "布拉加",
    "olympiacos": "奥林匹亚科斯",
    "fiorentina": "佛罗伦萨",
}

VENUE_ZH = {
    "emirates stadium": "酋长球场",
    "wembley stadium": "温布利球场",
}

BOILERPLATE = (
    re.compile(r"\s*The post .+ appeared first on Arseblog.*$", re.I),
    re.compile(r"\s*Continue reading\.{3}.*$", re.I),
    re.compile(r"\s*Read more\.{3}.*$", re.I),
)

SCORE_DISCLAIMER = "比分来自最近一次成功更新，不是实时比分。"


class FetchError(Exception):
    pass


class ApiError(Exception):
    pass


class QuotaError(Exception):
    pass


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.skip_depth += 1
        if tag in {"p", "br", "div", "li", "h1", "h2", "h3", "tr"}:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.skip_depth:
            self.skip_depth -= 1
        if tag in {"p", "div", "li"}:
            self.parts.append(" ")

    def handle_data(self, data):
        if self.skip_depth == 0:
            self.parts.append(data)

    def text(self) -> str:
        return re.sub(r"\s+", " ", "".join(self.parts)).strip()


def log(message: str) -> None:
    print(message, flush=True)


def local_name(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def redact(text: str, secret: str) -> str:
    if not text:
        return ""
    cleaned = text
    if secret:
        cleaned = cleaned.replace(secret, "[redacted]")
        encoded = urllib.parse.quote(secret, safe="")
        if encoded:
            cleaned = cleaned.replace(encoded, "[redacted]")
    return cleaned


def parse_iso(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            try:
                dt = parsedate_to_datetime(text)
            except (TypeError, ValueError, IndexError, OverflowError):
                return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def to_shanghai_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(SH).isoformat(timespec="seconds")


def current_season(now: datetime) -> int:
    local = now.astimezone(SH)
    return local.year if local.month >= 7 else local.year - 1


def expect_cups(now: datetime) -> bool:
    # June and July are the gap between seasons. August through May should
    # already include League Cup or European ties in a full-season dump.
    return now.astimezone(SH).month not in (6, 7)


def stable_id(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def normalize_punctuation(text: str) -> str:
    # Curly quotes and ellipses are often missing from fallback CJK fonts.
    return text.translate(
        str.maketrans(
            {
                "\u2018": "'",
                "\u2019": "'",
                "\u201c": '"',
                "\u201d": '"',
                "\u2013": "-",
                "\u2014": "-",
                "\u00a0": " ",
                "\u2026": "...",
            }
        )
    )


def strip_html(raw: str) -> str:
    if not raw:
        return ""
    text = raw.strip()
    if "&lt;" in text and "<" not in text:
        text = html.unescape(text)
    try:
        parser = TextExtractor()
        parser.feed(text)
        parser.close()
        plain = parser.text()
    except Exception:
        plain = re.sub(r"(?is)<(script|style)\b.*?>.*?</\1>", " ", text)
        plain = re.sub(r"(?s)<[^>]+>", " ", plain)
        plain = html.unescape(plain)
        plain = re.sub(r"\s+", " ", plain).strip()
    for pattern in BOILERPLATE:
        plain = pattern.sub("", plain)
    return normalize_punctuation(plain).strip()


def excerpt(raw: str, limit: int = EXCERPT_LIMIT) -> str:
    text = strip_html(raw)
    if not text:
        return "（来源未提供摘要）"
    if len(text) <= limit:
        return text
    cut = text[:limit]
    window = cut[-40:]
    breaks = [window.rfind(mark) for mark in (" ", "。", "，", ",", ".", "、")]
    idx = max(breaks)
    if idx >= 12:
        cut = cut[: len(cut) - 40 + idx]
        return cut.rstrip(" ，,。.;；:：") + "..."


def element_markup(child) -> str:
    parts: list[str] = []
    if child.text:
        parts.append(child.text)
    for sub in list(child):
        parts.append(ET.tostring(sub, encoding="unicode"))
        if sub.tail:
            parts.append(sub.tail)
    return "".join(parts)


def child_fields(element) -> dict:
    fields: dict[str, str] = {}
    for child in list(element):
        key = local_name(child.tag)
        if key in fields or key in {"encoded", "content"}:
            # content:encoded and media:content are the full body or media.
            # v1 keeps a short excerpt from description/summary only.
            continue
        if key in {"description", "summary"}:
            fields[key] = element_markup(child)
        else:
            fields[key] = "".join(child.itertext()).strip()
    return fields


def find_channel(root):
    for element in root.iter():
        if local_name(element.tag) == "channel":
            return element
    return root


def iter_items(root):
    for element in root.iter():
        if local_name(element.tag) == "item":
            yield element


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def empty_news() -> dict:
    return {
        "fetchedAt": None,
        "sourceUpdatedAt": None,
        "sourceTimeLabel": "订阅源更新时间",
        "stale": False,
        "message": "还没有新闻数据。",
        "items": [],
        "sources": [],
    }


def empty_podcasts() -> dict:
    return {
        "fetchedAt": None,
        "sourceUpdatedAt": None,
        "sourceTimeLabel": "订阅源更新时间",
        "stale": False,
        "message": "还没有播客数据。",
        "items": [],
    }


def empty_fixtures() -> dict:
    return {
        "available": False,
        "stale": False,
        "fetchedAt": None,
        "attemptedAt": None,
        "sourceUpdatedAt": None,
        "sourceTimeLabel": "接口未提供单独的发布时间",
        "message": "赛程暂时不可用。",
        "scoreDisclaimer": SCORE_DISCLAIMER,
        "coverage": {
            "season": None,
            "seasonLabel": None,
            "checked": False,
            "complete": False,
            "competitions": [],
            "missing": [],
            "warning": None,
        },
        "nextMatch": None,
        "upcoming": [],
        "results": [],
        "matches": [],
    }


def empty_meta(now: datetime) -> dict:
    return {
        "utcDate": now.astimezone(timezone.utc).date().isoformat(),
        "requests": 0,
        "lastFixturesAttempt": None,
        "lastFixturesSuccess": None,
        "consecutiveFailures": 0,
        "lastMode": None,
        "remaining": None,
    }


def default_http_get(url: str, headers: dict, timeout: int = 45):
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = read_limited(response)
            return response.status, {k.lower(): v for k, v in response.headers.items()}, body
    except urllib.error.HTTPError as exc:
        body = exc.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            body = body[:MAX_BYTES]
        return exc.code, {k.lower(): v for k, v in exc.headers.items()}, body
    except urllib.error.URLError as exc:
        raise FetchError(str(exc.reason)) from exc
    except TimeoutError as exc:
        raise FetchError("超时") from exc


def read_limited(response) -> bytes:
    chunks = []
    total = 0
    while True:
        chunk = response.read(65536)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_BYTES:
            raise FetchError("响应过大")
        chunks.append(chunk)
    return b"".join(chunks)


def fetch_bytes(url: str, headers: dict, http_get, attempts: int = 2):
    last_error = "未知错误"
    for attempt in range(attempts):
        try:
            status, response_headers, body = http_get(url, headers)
        except FetchError as exc:
            last_error = str(exc)
            if attempt + 1 < attempts:
                continue
            raise
        if status == 200 and body:
            stripped = body.lstrip().lower()
            if stripped.startswith(b"<!doctype html") or stripped.startswith(b"<html"):
                last_error = "源返回了网页而不是订阅数据"
                if attempt + 1 < attempts:
                    continue
                raise FetchError(last_error)
            return status, response_headers, body
        last_error = f"HTTP {status}"
        if status < 500 and status != 429:
            break
    raise FetchError(last_error)


def parse_feed(body: bytes):
    if body.startswith(b"\xef\xbb\xbf"):
        body = body[3:]
    if body[:2] == b"\x1f\x8b":
        try:
            body = gzip.decompress(body)
        except OSError as exc:
            raise FetchError("订阅源压缩内容无法解压") from exc
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise FetchError(f"RSS 无法解析：{exc}") from exc
    channel = find_channel(root)
    channel_fields = child_fields(channel) if channel is not None else {}
    items = [child_fields(item) for item in iter_items(root)]
    return channel_fields, items


def http_link(fields: dict) -> str:
    link = (fields.get("link") or "").strip()
    if link.startswith("http://") or link.startswith("https://"):
        return link
    guid = (fields.get("guid") or "").strip()
    if guid.startswith("http://") or guid.startswith("https://"):
        return guid
    return ""


def source_time(channel_fields: dict, dates: list[datetime]) -> datetime | None:
    built = parse_iso(channel_fields.get("lastBuildDate")) or parse_iso(
        channel_fields.get("pubDate")
    )
    newest = max(dates) if dates else None
    if built and newest:
        return max(built, newest)
    return built or newest


def news_item(source: dict, fields: dict) -> dict | None:
    title = strip_html(fields.get("title") or "")[:300]
    url = http_link(fields)
    published = parse_iso(fields.get("pubDate"))
    if not title or not url or published is None:
        return None
    summary_raw = fields.get("description") or ""
    return {
        "id": stable_id(url),
        "title": title,
        "summary": excerpt(summary_raw),
        "source": source["name"],
        "sourceId": source["id"],
        "url": url,
        "publishedAt": to_shanghai_iso(published),
    }


def update_news(old: dict, now: datetime, http_get) -> dict:
    old_items = list((old or {}).get("items") or [])
    merged: list[dict] = []
    reports = []
    newest_times: list[datetime] = []
    for source in NEWS_SOURCES:
        try:
            _status, _headers, body = fetch_bytes(
                source["url"],
                {"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml"},
                http_get,
            )
            channel_fields, raw_items = parse_feed(body)
            parsed = []
            dates = []
            for fields in raw_items:
                # Never read content:encoded. child_fields only keeps the first
                # description/summary and ignores encoded.
                item = news_item(source, fields)
                if item is None:
                    continue
                parsed.append(item)
                stamp = parse_iso(item["publishedAt"])
                if stamp:
                    dates.append(stamp)
            if not parsed:
                raise FetchError("订阅源里没有可用条目")
            parsed.sort(key=lambda item: item["publishedAt"], reverse=True)
            kept = parsed[:NEWS_PER_SOURCE]
            merged.extend(kept)
            stamp = source_time(channel_fields, dates)
            if stamp:
                newest_times.append(stamp)
            reports.append(
                {
                    "id": source["id"],
                    "name": source["name"],
                    "ok": True,
                    "stale": False,
                    "keptCache": False,
                    "count": len(kept),
                    "fetchedAt": to_shanghai_iso(now),
                    "sourceUpdatedAt": to_shanghai_iso(stamp) if stamp else None,
                    "error": None,
                }
            )
            log(f"news {source['id']} ok {len(kept)}")
        except (FetchError, ApiError, OSError, ValueError) as exc:
            cached = [item for item in old_items if item.get("sourceId") == source["id"]]
            merged.extend(cached)
            previous = next(
                (
                    row
                    for row in (old or {}).get("sources") or []
                    if row.get("id") == source["id"]
                ),
                {},
            )
            reports.append(
                {
                    "id": source["id"],
                    "name": source["name"],
                    "ok": False,
                    "stale": bool(cached),
                    "keptCache": bool(cached),
                    "count": len(cached),
                    "fetchedAt": previous.get("fetchedAt"),
                    "sourceUpdatedAt": previous.get("sourceUpdatedAt"),
                    "error": str(exc)[:240],
                }
            )
            log(f"news {source['id']} failed cache={len(cached)} {exc}")
    merged.sort(key=lambda item: item.get("publishedAt") or "", reverse=True)
    deduped = []
    seen = set()
    for item in merged:
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        deduped.append(item)
    stale = any(row["keptCache"] for row in reports)
    messages = []
    for row in reports:
        if row["ok"]:
            messages.append(f"{row['name']}已更新")
        elif row["keptCache"]:
            messages.append(f"{row['name']}更新失败，仍显示该来源上次缓存")
        else:
            messages.append(f"{row['name']}更新失败，暂时没有该来源的条目")
    any_success = any(row["ok"] for row in reports)
    previous_stamp = parse_iso((old or {}).get("sourceUpdatedAt"))
    if previous_stamp:
        newest_times.append(previous_stamp)
    source_updated = max(newest_times) if newest_times else None
    if any_success:
        fetched_at = to_shanghai_iso(now)
    else:
        fetched_at = (old or {}).get("fetchedAt")
    return {
        "fetchedAt": fetched_at,
        "sourceUpdatedAt": to_shanghai_iso(source_updated) if source_updated else (old or {}).get("sourceUpdatedAt"),
        "sourceTimeLabel": "订阅源里最新内容的时间",
        "stale": stale,
        "message": "。".join(messages) + ("。" if messages else ""),
        "items": deduped,
        "sources": reports,
    }


def classify_podcast(title: str, url: str) -> str | None:
    blob = f"{title} {url}".lower()
    if any(token in blob for token in ("patreon", "patron-only", "patrons only", "members only")):
        return None
    host = urllib.parse.urlparse(url).netloc.lower()
    if host.endswith("patreon.com"):
        return None
    if not (host.endswith("acast.com") or host.endswith("arseblog.com")):
        return None
    lowered = title.lower()
    if "women" in lowered and "arsecast" in lowered:
        return "women"
    if "extra" in lowered and "arsecast" in lowered:
        return "extra"
    if re.match(r"^episode\s+\d+\b", lowered):
        return "episode"
    return None


def duration_zh(raw: str) -> str:
    if not raw:
        return ""
    parts = raw.strip().split(":")
    try:
        numbers = [int(part) for part in parts]
    except ValueError:
        return ""
    if len(numbers) == 3:
        hours, minutes, _seconds = numbers
        if hours:
            return f"{hours}小时{minutes}分"
        return f"{minutes}分"
    if len(numbers) == 2:
        minutes, _seconds = numbers
        return f"{minutes}分"
    return ""


PODCAST_SHOW = {
    "episode": "Arsecast 正集",
    "extra": "Arsecast Extra",
    "women": "Arsecast 女足",
}


def update_podcasts(old: dict, now: datetime, http_get) -> dict:
    try:
        _status, _headers, body = fetch_bytes(
            PODCAST_URL,
            {"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml"},
            http_get,
            attempts=2,
        )
        channel_fields, raw_items = parse_feed(body)
        grouped = {"episode": [], "extra": [], "women": []}
        dates = []
        for fields in raw_items:
            title = strip_html(fields.get("title") or "")[:300]
            url = http_link(fields)
            published = parse_iso(fields.get("pubDate"))
            if not title or not url or published is None:
                continue
            kind = classify_podcast(title, url)
            if kind is None:
                continue
            dates.append(published)
            grouped[kind].append(
                {
                    "id": stable_id(url),
                    "title": title,
                    "summary": excerpt(fields.get("summary") or fields.get("description") or ""),
                    "show": PODCAST_SHOW[kind],
                    "kind": kind,
                    "url": url,
                    "publishedAt": to_shanghai_iso(published),
                    "duration": duration_zh(fields.get("duration") or ""),
                }
            )
        kept = []
        for kind in ("episode", "extra", "women"):
            rows = sorted(grouped[kind], key=lambda item: item["publishedAt"], reverse=True)
            kept.extend(rows[:PODCAST_PER_KIND])
        kept.sort(key=lambda item: item["publishedAt"], reverse=True)
        if not any(item["kind"] == "episode" for item in kept) or not any(
            item["kind"] == "extra" for item in kept
        ):
            raise FetchError("订阅源里没有同时识别出正集和 Extra")
        stamp = source_time(channel_fields, dates)
        log(
            "podcasts ok "
            + " ".join(f"{kind}={sum(1 for item in kept if item['kind']==kind)}" for kind in grouped)
        )
        return {
            "fetchedAt": to_shanghai_iso(now),
            "sourceUpdatedAt": to_shanghai_iso(stamp) if stamp else None,
            "sourceTimeLabel": "订阅源里最新节目的时间",
            "stale": False,
            "message": "Arsecast 已更新。",
            "items": kept,
        }
    except (FetchError, OSError, ValueError) as exc:
        if old and old.get("items"):
            kept = dict(old)
            kept["stale"] = True
            kept["message"] = f"播客更新失败，仍在显示上次成功缓存的数据。{str(exc)[:180]}"
            log(f"podcasts failed cache={len(old.get('items') or [])} {exc}")
            return kept
        log(f"podcasts failed empty {exc}")
        payload = empty_podcasts()
        payload["message"] = f"播客暂时不可用。{str(exc)[:180]}"
        payload["attemptedAt"] = to_shanghai_iso(now)
        return payload


def norm_name(name: str) -> str:
    text = name.lower().replace("&", " and ").replace(".", " ")
    text = re.sub(r"\b(fc|afc|cf)\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def team_names(name: str) -> tuple[str, str]:
    zh = TEAM_ZH.get(norm_name(name or ""))
    if zh:
        return zh, name
    return name or "未知球队", ""


def competition_zh(league_id, name: str) -> str:
    if league_id in COMP_BY_ID:
        return COMP_BY_ID[league_id]
    lowered = (name or "").lower()
    for needle, label in COMP_BY_NAME:
        if needle in lowered:
            return label
    return name or "赛事"


def round_zh(raw: str) -> str:
    if not raw:
        return ""
    lowered = raw.lower()
    numbered = re.search(r"(\d+)", raw)
    named = (
        ("quarter-final", "1/4决赛"),
        ("semi-final", "半决赛"),
        ("round of 16", "16强"),
        ("round of 32", "32强"),
        ("8th finals", "16强"),
        ("league stage", "联赛阶段"),
        ("group stage", "小组赛"),
        ("knockout round play-offs", "淘汰赛附加赛"),
        ("knockout", "淘汰赛"),
        ("final", "决赛"),
    )
    for needle, label in named:
        if needle in lowered:
            return label
    if "regular season" in lowered and numbered:
        return f"第{numbered.group(1)}轮"
    return raw


def venue_names(name: str) -> tuple[str, str]:
    if not name:
        return "", ""
    zh = VENUE_ZH.get(name.lower().strip())
    if zh:
        return zh, name
    return name, ""


def status_of(short: str) -> tuple[str, str]:
    code = (short or "").upper()
    if code in FINISHED:
        labels = {
            "FT": "已结束",
            "AET": "已结束（加时）",
            "PEN": "已结束（点球）",
            "AWD": "已结束（裁定）",
            "WO": "已结束（弃权）",
        }
        return "finished", labels.get(code, "已结束")
    if code in SCHEDULED:
        return "scheduled", "时间待定" if code == "TBD" else "未开始"
    if code in POSTPONED:
        return "postponed", "推迟"
    if code in CANCELLED:
        return "cancelled", "取消" if code == "CANC" else "腰斩"
    if code in INPLAY:
        labels = {
            "HT": "中场休息（比分停在上次更新）",
            "INT": "中断（比分停在上次更新）",
            "SUSP": "暂停（比分停在上次更新）",
            "BT": "加时中场（比分停在上次更新）",
            "P": "点球大战（比分停在上次更新）",
            "ET": "加时进行中（比分停在上次更新）",
        }
        return "inplay", labels.get(code, "比赛可能进行中（比分停在上次更新）")
    return "scheduled", code or "未开始"


def is_cup_match(match: dict) -> bool:
    if match.get("competitionId") in CUP_IDS:
        return True
    raw = (match.get("competitionRaw") or "").lower()
    return any(
        token in raw
        for token in ("cup", "champions league", "europa", "shield", "league cup", "carabao")
    )


def parse_fixture_item(item: dict) -> dict | None:
    fixture = item.get("fixture") or {}
    league = item.get("league") or {}
    teams = item.get("teams") or {}
    goals = item.get("goals") or {}
    home = teams.get("home") or {}
    away = teams.get("away") or {}
    home_id = home.get("id")
    away_id = away.get("id")
    home_raw = home.get("name") or ""
    away_raw = away.get("name") or ""
    arsenal_home = home_id == TEAM_ID or "arsenal" in home_raw.lower()
    arsenal_away = away_id == TEAM_ID or "arsenal" in away_raw.lower()
    if not arsenal_home and not arsenal_away:
        return None
    kickoff = parse_iso(fixture.get("date"))
    if kickoff is None or fixture.get("id") is None:
        return None
    status, status_text = status_of((fixture.get("status") or {}).get("short") or "")
    home_goals = goals.get("home")
    away_goals = goals.get("away")
    score = None
    if status in {"finished", "inplay"} and home_goals is not None and away_goals is not None:
        score = {"home": int(home_goals), "away": int(away_goals)}
    home_zh, home_en = team_names(home_raw)
    away_zh, away_en = team_names(away_raw)
    venue_raw = ((fixture.get("venue") or {}).get("name")) or ""
    venue_zh, venue_en = venue_names(venue_raw)
    league_id = league.get("id")
    league_name = league.get("name") or ""
    return {
        "id": fixture.get("id"),
        "competition": competition_zh(league_id, league_name),
        "competitionRaw": league_name,
        "competitionId": league_id,
        "round": round_zh(league.get("round") or ""),
        "roundRaw": league.get("round") or "",
        "kickoff": to_shanghai_iso(kickoff),
        "status": status,
        "statusText": status_text,
        "home": home_zh,
        "homeEn": home_en,
        "away": away_zh,
        "awayEn": away_en,
        "arsenalSide": "home" if arsenal_home else "away",
        "score": score,
        "venue": venue_zh,
        "venueEn": venue_en,
        "season": league.get("season"),
    }


def annotate_fixture_views(matches: list[dict]) -> dict:
    ordered = sorted(matches, key=lambda match: match.get("kickoff") or "")
    results = [match for match in ordered if match.get("status") == "finished"]
    results = list(reversed(results[-8:]))
    pool = [
        match
        for match in ordered
        if match.get("status") in {"scheduled", "postponed", "inplay"}
    ]
    next_match = next((match for match in pool if match.get("status") == "inplay"), None)
    if next_match is None:
        next_match = next((match for match in pool if match.get("status") == "scheduled"), None)
    if next_match is None and pool:
        next_match = pool[0]
    upcoming = []
    for match in pool:
        if next_match and match.get("id") == next_match.get("id"):
            continue
        if match.get("status") in {"scheduled", "postponed"}:
            upcoming.append(match)
        if len(upcoming) >= 4:
            break
    if results:
        source_at = results[0].get("kickoff")
        source_label = "最近一场已结束比赛的开球时间（接口没有单独的发布时间）"
    elif next_match:
        source_at = next_match.get("kickoff")
        source_label = "下一场开球时间（接口没有单独的发布时间）"
    else:
        source_at = None
        source_label = "接口没有单独的发布时间"
    return {
        "matches": ordered,
        "results": results,
        "nextMatch": next_match,
        "upcoming": upcoming,
        "sourceUpdatedAt": source_at,
        "sourceTimeLabel": source_label,
    }


def in_match_window(matches: list[dict], now: datetime) -> bool:
    for match in matches:
        if match.get("status") == "cancelled":
            continue
        kickoff = parse_iso(match.get("kickoff"))
        if match.get("status") == "inplay":
            if kickoff and abs(now - kickoff) <= timedelta(hours=6):
                return True
            continue
        if kickoff and (kickoff - timedelta(hours=2)) <= now <= (kickoff + timedelta(hours=3)):
            return True
    return False


def choose_fixture_mode(meta: dict, fixtures: dict, now: datetime, force: bool) -> str:
    if force:
        return "full"
    matches = fixtures.get("matches") or []
    last_attempt = parse_iso(meta.get("lastFixturesAttempt"))
    last_success = parse_iso(meta.get("lastFixturesSuccess"))
    failures = int(meta.get("consecutiveFailures") or 0)
    if not matches or last_success is None:
        if last_attempt and failures >= 1 and now - last_attempt < FAIL_BACKOFF:
            return "skip"
        return "full"
    since_attempt = (now - last_attempt) if last_attempt else timedelta(days=99)
    since_success = now - last_success
    if in_match_window(matches, now) and failures < 2:
        if since_attempt < WINDOW_INTERVAL:
            return "skip"
        if since_success < FULL_INTERVAL:
            return "narrow"
        return "full"
    if since_attempt < FULL_INTERVAL and since_success < FULL_INTERVAL:
        return "skip"
    return "full"


def budget_left(meta: dict) -> int:
    local = DAILY_REQUEST_CAP - int(meta.get("requests") or 0)
    remaining = meta.get("remaining")
    if isinstance(remaining, int):
        return max(0, min(local, remaining))
    return max(0, local)


def roll_meta(meta: dict, now: datetime) -> dict:
    today = now.astimezone(timezone.utc).date().isoformat()
    if meta.get("utcDate") != today:
        meta["utcDate"] = today
        meta["requests"] = 0
        meta["remaining"] = None
    meta["requests"] = int(meta.get("requests") or 0)
    meta["consecutiveFailures"] = int(meta.get("consecutiveFailures") or 0)
    return meta


def error_text(payload) -> str:
    if not isinstance(payload, dict):
        return "接口返回的不是 JSON 对象"
    errors = payload.get("errors")
    if not errors:
        return ""
    if isinstance(errors, list):
        return "；".join(str(item) for item in errors if item)[:400]
    if isinstance(errors, dict):
        parts = [f"{key}: {value}" for key, value in errors.items() if value]
        return "；".join(parts)[:400]
    return str(errors)[:400]


def access_blocked(message: str) -> bool:
    lowered = message.lower()
    return any(token in lowered for token in ("plan", "free", "access", "subscription", "season"))


def rate_limited(status: int, message: str) -> bool:
    lowered = message.lower()
    return status == 429 or "too many requests" in lowered or "rate limit" in lowered


def api_get(path: str, params: dict, secret: str, meta: dict, http_get) -> dict:
    if budget_left(meta) <= 0:
        raise QuotaError("已达到每日免费额度保护")
    url = API_BASE + path + "?" + urllib.parse.urlencode(params)
    try:
        status, headers, body = http_get(
            url,
            {
                "Accept": "application/json",
                "User-Agent": UA,
                "x-apisports-key": secret,
            },
        )
    except FetchError as exc:
        meta["requests"] += 1
        raise ApiError(str(exc)) from exc
    meta["requests"] += 1
    remaining = headers.get("x-ratelimit-requests-remaining")
    if remaining is not None and str(remaining).isdigit():
        meta["remaining"] = int(remaining)
        if int(remaining) <= 0:
            meta["requests"] = DAILY_REQUEST_CAP
    text = body.decode("utf-8", errors="replace")
    lowered = text.lstrip().lower()
    if lowered.startswith("<!doctype html") or lowered.startswith("<html"):
        raise ApiError(f"HTTP {status}，接口返回了网页")
    try:
        payload = json.loads(text) if text else {}
    except json.JSONDecodeError as exc:
        raise ApiError("接口返回的不是 JSON") from exc
    message = error_text(payload)
    if rate_limited(status, message):
        meta["requests"] = DAILY_REQUEST_CAP
        raise QuotaError(message or f"HTTP {status}")
    if status != 200:
        raise ApiError(message or f"HTTP {status}")
    if message:
        if access_blocked(message):
            raise ApiError(message)
        raise ApiError(message)
    return payload


def competitions_from_fixtures(matches: list[dict]) -> list[dict]:
    found = {}
    for match in matches:
        key = match.get("competitionId") or match.get("competitionRaw")
        row = found.setdefault(
            key,
            {
                "id": match.get("competitionId"),
                "name": match.get("competitionRaw") or match.get("competition"),
                "nameZh": match.get("competition"),
                "matches": 0,
            },
        )
        row["matches"] += 1
    return list(found.values())


def assess_coverage(matches: list[dict], leagues_payload: dict | None, season: int, now: datetime, leagues_error: str | None) -> dict:
    present_ids = {match.get("competitionId") for match in matches}
    competitions = competitions_from_fixtures(matches)
    missing = []
    checked = leagues_payload is not None and not leagues_error
    if leagues_payload is not None:
        for entry in leagues_payload.get("response") or []:
            league = entry.get("league") or {}
            league_id = league.get("id")
            name = league.get("name") or str(league_id)
            if league_id not in present_ids:
                missing.append(competition_zh(league_id, name))
    seasons = {match.get("season") for match in matches if match.get("season") is not None}
    have_cups = any(is_cup_match(match) for match in matches)
    warning_parts = []
    if season not in seasons:
        shown = "、".join(str(item) for item in sorted(seasons)) or "无"
        warning_parts.append(
            f"预期赛季是 {season}/{season + 1}，接口返回的赛季是 {shown}。页面不会拿别的赛季冒充本赛季。"
        )
    if missing:
        warning_parts.append(
            "接口列出了这些赛事，但没有返回任何场次："
            + "、".join(missing)
            + "。页面没有把缺口补上。"
        )
    if expect_cups(now) and not have_cups:
        warning_parts.append(
            "本赛季按理应已有联赛杯、足总杯或欧洲赛事，这次却没有看到任何杯赛场次。"
            "这通常是免费套餐的赛季范围不完整。页面不会猜测，也不会因此改用付费计划。"
        )
    elif leagues_error:
        warning_parts.append("场次已更新，但没能拉到赛事清单做逐项核对：" + leagues_error[:120])
    elif not checked:
        warning_parts.append("这次没有拉到赛事清单，所以还不能确认杯赛是否齐全。")
    warning = "".join(warning_parts) or None
    complete = bool(
        checked
        and not missing
        and season in seasons
        and (have_cups or not expect_cups(now))
        and not warning
    )
    return {
        "season": season,
        "seasonLabel": f"{season}/{season + 1}",
        "checked": checked,
        "complete": complete,
        "competitions": competitions,
        "missing": missing,
        "warning": warning,
    }


def fixtures_from_payload(payload: dict) -> list[dict]:
    matches = []
    for item in payload.get("response") or []:
        match = parse_fixture_item(item)
        if match is not None:
            matches.append(match)
    if (payload.get("response") or []) and not matches:
        raise ApiError("接口有返回，但其中没有阿森纳一场比赛，已拒绝这份数据")
    return matches


def merge_matches(existing: list[dict], updates: list[dict]) -> list[dict]:
    by_id = {match["id"]: match for match in existing}
    for match in updates:
        by_id[match["id"]] = match
    return list(by_id.values())


def apply_views(base: dict, matches: list[dict]) -> dict:
    views = annotate_fixture_views(matches)
    base.update(views)
    base["available"] = bool(matches)
    return base


def fail_fixtures(old: dict | None, message: str, now: datetime) -> dict:
    if old and old.get("matches"):
        kept = dict(old)
        kept["stale"] = True
        kept["available"] = True
        kept["scoreDisclaimer"] = SCORE_DISCLAIMER
        kept["attemptedAt"] = to_shanghai_iso(now)
        kept["message"] = "赛程更新失败，仍在显示上次成功缓存的数据。" + message
        return kept
    payload = empty_fixtures()
    payload["attemptedAt"] = to_shanghai_iso(now)
    payload["message"] = message
    payload["stale"] = False
    return payload


def missing_key_fixtures(old: dict | None, now: datetime) -> dict:
    message = "还没有配置 API_FOOTBALL_KEY。新闻和播客不受影响。密钥只会放在 GitHub Actions 的密钥里，不会写进网页。"
    if old and old.get("matches"):
        kept = dict(old)
        kept["stale"] = True
        kept["available"] = True
        kept["scoreDisclaimer"] = SCORE_DISCLAIMER
        kept["attemptedAt"] = to_shanghai_iso(now)
        kept["message"] = "这次没有读到 API_FOOTBALL_KEY，仍在显示上次成功缓存的赛程。"
        return kept
    payload = empty_fixtures()
    payload["message"] = message
    payload["attemptedAt"] = to_shanghai_iso(now)
    return payload


def update_fixtures(old: dict, meta: dict, now: datetime, secret: str, force: bool, http_get) -> tuple[dict, str]:
    existing = old or empty_fixtures()
    if not secret:
        log("fixtures skipped: no API_FOOTBALL_KEY")
        return missing_key_fixtures(existing if existing.get("matches") else None, now), "unavailable"
    mode = choose_fixture_mode(meta, existing, now, force)
    meta["lastMode"] = mode
    if mode == "skip":
        log("fixtures skipped by schedule")
        return existing, "skip"
    if budget_left(meta) <= 0:
        log("fixtures held by daily cap")
        kept = dict(existing)
        if kept.get("matches"):
            kept["message"] = "今天的免费请求额度保护已触发，赛程暂停更新，仍显示上次成功的数据。"
            kept["quotaHeld"] = True
        else:
            kept = empty_fixtures()
            kept["message"] = "今天的免费请求额度保护已触发，暂时不能请求赛程。"
            kept["quotaHeld"] = True
        return kept, "quota"
    season = current_season(now)
    meta["lastFixturesAttempt"] = to_shanghai_iso(now)
    try:
        if mode == "narrow":
            start = (now.astimezone(timezone.utc) - timedelta(days=1)).date().isoformat()
            end = (now.astimezone(timezone.utc) + timedelta(days=2)).date().isoformat()
            payload = api_get(
                "/fixtures",
                {"team": TEAM_ID, "from": start, "to": end},
                secret,
                meta,
                http_get,
            )
            updates = fixtures_from_payload(payload)
            if not updates:
                raise ApiError("比赛窗口内的请求没有返回场次")
            matches = merge_matches(existing.get("matches") or [], updates)
            refreshed = dict(existing)
            apply_views(refreshed, matches)
            refreshed["stale"] = False
            refreshed["quotaHeld"] = False
            refreshed["fetchedAt"] = to_shanghai_iso(now)
            refreshed["attemptedAt"] = to_shanghai_iso(now)
            warning = (refreshed.get("coverage") or {}).get("warning")
            refreshed["message"] = "赛程已按比赛窗口更新。" + (warning or "")
            meta["lastFixturesSuccess"] = to_shanghai_iso(now)
            meta["consecutiveFailures"] = 0
            log(f"fixtures narrow ok matches={len(matches)}")
            return refreshed, "narrow"
        payload = api_get(
            "/fixtures",
            {"team": TEAM_ID, "season": season},
            secret,
            meta,
            http_get,
        )
        matches = fixtures_from_payload(payload)
        if not matches:
            raise ApiError(
                f"接口没有返回 {season}/{season + 1} 赛季的场次。"
                + ("现在接近赛季交替，新赛季编号可能还没启用。" if now.astimezone(SH).month == 7 else "")
            )
        leagues_payload = None
        leagues_error = None
        if budget_left(meta) > 0:
            try:
                leagues_payload = api_get(
                    "/leagues",
                    {"team": TEAM_ID, "season": season},
                    secret,
                    meta,
                    http_get,
                )
            except (ApiError, QuotaError) as exc:
                leagues_error = redact(str(exc), secret)
        coverage = assess_coverage(matches, leagues_payload, season, now, leagues_error)
        refreshed = empty_fixtures()
        apply_views(refreshed, matches)
        refreshed["coverage"] = coverage
        refreshed["stale"] = False
        refreshed["quotaHeld"] = False
        refreshed["fetchedAt"] = to_shanghai_iso(now)
        refreshed["attemptedAt"] = to_shanghai_iso(now)
        refreshed["message"] = "赛程已更新。" + (coverage.get("warning") or "")
        meta["lastFixturesSuccess"] = to_shanghai_iso(now)
        meta["consecutiveFailures"] = 0
        log(
            f"fixtures full ok matches={len(matches)} "
            f"competitions={len(coverage['competitions'])} complete={coverage['complete']}"
        )
        return refreshed, "full"
    except QuotaError as exc:
        meta["consecutiveFailures"] = int(meta.get("consecutiveFailures") or 0) + 1
        message = "今天的免费请求额度保护已触发。" + redact(str(exc), secret)[:160]
        log(f"fixtures quota {exc}")
        failed = fail_fixtures(existing if existing.get("matches") else None, message, now)
        failed["quotaHeld"] = True
        return failed, "quota"
    except ApiError as exc:
        meta["consecutiveFailures"] = int(meta.get("consecutiveFailures") or 0) + 1
        message = fixtures_error_message(str(exc), secret)
        log(f"fixtures failed {message}")
        return fail_fixtures(existing if existing.get("matches") else None, message, now), "failed"


def fixtures_error_message(detail: str, secret: str) -> str:
    clean = redact(detail, secret)[:240]
    if access_blocked(clean):
        return (
            "API-Football 没有提供可用的当前赛季数据（常见原因是免费套餐的赛季范围）。"
            "页面不会改用更旧的赛季冒充本赛季，也不会升级到付费计划。详情："
            + clean
        )
    return "详情：" + clean


def build_status(news: dict, fixtures: dict, podcasts: dict, meta: dict, now: datetime, mode: str) -> dict:
    coverage_warning = ((fixtures.get("coverage") or {}).get("warning")) if fixtures else None
    fixtures_stale = bool(fixtures.get("stale"))
    news_stale = bool(news.get("stale"))
    podcasts_stale = bool(podcasts.get("stale"))
    quota_held = mode == "quota"
    banner = None
    banner_level = None
    parts = []
    if news_stale or fixtures_stale or podcasts_stale:
        banner_level = "warn"
        parts.append("有更新没有成功，相关内容仍在显示上次成功缓存的数据。")
    if quota_held:
        banner_level = banner_level or "info"
        parts.append("赛程今天已达到免费额度保护，暂停继续请求。")
    if coverage_warning:
        banner_level = banner_level or "info"
        parts.append("赛程覆盖不完整，打开「赛程」可以看到说明。")
    if parts:
        banner = "".join(parts)
    schedule_note = None
    if mode == "skip":
        schedule_note = "这次按计划没有请求赛程，为了把免费额度留给每天少数几次和比赛前后的更新。"
    return {
        "generatedAt": to_shanghai_iso(now),
        "timezone": "Asia/Shanghai",
        "banner": banner,
        "bannerLevel": banner_level,
        "requestsToday": int(meta.get("requests") or 0),
        "requestCap": DAILY_REQUEST_CAP,
        "providerDailyCap": 100,
        "fixturesMode": mode,
        "news": {
            "label": "新闻",
            "stale": news_stale,
            "hasData": bool(news.get("items")),
            "fetchedAt": news.get("fetchedAt"),
            "sourceUpdatedAt": news.get("sourceUpdatedAt"),
            "sourceTimeLabel": news.get("sourceTimeLabel"),
            "message": news.get("message"),
            "sources": news.get("sources") or [],
        },
        "fixtures": {
            "label": "赛程",
            "stale": fixtures_stale,
            "hasData": bool(fixtures.get("matches")),
            "available": bool(fixtures.get("available")),
            "fetchedAt": fixtures.get("fetchedAt"),
            "sourceUpdatedAt": fixtures.get("sourceUpdatedAt"),
            "sourceTimeLabel": fixtures.get("sourceTimeLabel"),
            "message": fixtures.get("message"),
            "coverageWarning": coverage_warning,
            "coverage": fixtures.get("coverage"),
            "quotaHeld": quota_held,
            "scheduleNote": schedule_note,
            "scoreDisclaimer": SCORE_DISCLAIMER,
        },
        "podcasts": {
            "label": "播客",
            "stale": podcasts_stale,
            "hasData": bool(podcasts.get("items")),
            "fetchedAt": podcasts.get("fetchedAt"),
            "sourceUpdatedAt": podcasts.get("sourceUpdatedAt"),
            "sourceTimeLabel": podcasts.get("sourceTimeLabel"),
            "message": podcasts.get("message"),
        },
    }


def run(data_dir: Path, env: dict | None = None, now: datetime | None = None, http_get=None) -> dict:
    env = os.environ if env is None else env
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    http_get = http_get or default_http_get
    secret = (env.get("API_FOOTBALL_KEY") or "").strip()
    force = (env.get("FORCE_FIXTURES") or "").strip().lower() in {"1", "true", "yes", "on"}
    data_dir.mkdir(parents=True, exist_ok=True)
    news_old = load_json(data_dir / "news.json", empty_news())
    podcasts_old = load_json(data_dir / "podcasts.json", empty_podcasts())
    fixtures_old = load_json(data_dir / "fixtures.json", empty_fixtures())
    meta = roll_meta(load_json(data_dir / "meta.json", empty_meta(now)), now)

    news = update_news(news_old, now, http_get)
    podcasts = update_podcasts(podcasts_old, now, http_get)
    fixtures, mode = update_fixtures(fixtures_old, meta, now, secret, force, http_get)
    status = build_status(news, fixtures, podcasts, meta, now, mode)

    write_json(data_dir / "news.json", news)
    write_json(data_dir / "podcasts.json", podcasts)
    write_json(data_dir / "fixtures.json", fixtures)
    write_json(data_dir / "status.json", status)
    write_json(data_dir / "meta.json", meta)
    if secret:
        for name in ("news.json", "podcasts.json", "fixtures.json", "status.json", "meta.json"):
            text = (data_dir / name).read_text(encoding="utf-8")
            if secret in text:
                raise RuntimeError(f"API key leaked into {name}")
    log(
        "wrote data "
        f"news={len(news.get('items') or [])} "
        f"podcasts={len(podcasts.get('items') or [])} "
        f"fixtures={len(fixtures.get('matches') or [])} "
        f"mode={mode}"
    )
    return status


def main(data_dir: Path | None = None) -> int:
    directory = data_dir or Path("data")
    try:
        run(directory)
    except Exception as exc:
        secret = os.environ.get("API_FOOTBALL_KEY", "")
        log("fatal " + redact(str(exc), secret))
        return 1
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="更新阿森纳信息中心的本地 JSON 数据")
    parser.add_argument("--data-dir", default="data")
    args = parser.parse_args()
    raise SystemExit(main(Path(args.data_dir)))
