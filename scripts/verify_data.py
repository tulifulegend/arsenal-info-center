#!/usr/bin/env python3
"""Check generated JSON stays inside the v1 content rules."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from update_data import EXCERPT_LIMIT

MAX_SUMMARY = EXCERPT_LIMIT + 20
PODCAST_KINDS = {"episode", "extra", "women"}
ALLOWED_HOST_SUFFIXES = ("acast.com", "arseblog.com")


def load(directory: Path, name: str):
    path = directory / name
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return exc


def problems(directory: Path) -> list[str]:
    errors = []
    news = load(directory, "news.json")
    podcasts = load(directory, "podcasts.json")
    fixtures = load(directory, "fixtures.json")
    status = load(directory, "status.json")
    for label, value in (
        ("news.json", news),
        ("podcasts.json", podcasts),
        ("fixtures.json", fixtures),
        ("status.json", status),
    ):
        if isinstance(value, Exception):
            errors.append(f"{label} 无法读取：{value}")
    if errors:
        return errors
    if not isinstance(news, dict) or not isinstance(news.get("items"), list):
        errors.append("news.json 结构不对")
        return errors
    for item in news["items"]:
        summary = item.get("summary") or ""
        if len(summary) > MAX_SUMMARY:
            errors.append(f"新闻摘要过长：{item.get('title', '')[:40]}")
        if re.search(r"<\s*/?\s*[A-Za-z]", summary) or re.search(
            r"<\s*/?\s*[A-Za-z]", item.get("title") or ""
        ):
            errors.append(f"新闻标题或摘要仍含 HTML：{item.get('id')}")
        for banned in ("encoded", "content", "body", "description"):
            if banned in item:
                errors.append(f"新闻条目含禁止字段 {banned}")
        url = item.get("url") or ""
        if not url.startswith("https://") and not url.startswith("http://"):
            errors.append(f"新闻链接不合法：{url[:80]}")
        published = item.get("publishedAt") or ""
        if published and not published.endswith("+08:00"):
            errors.append(f"新闻时间不是北京时间：{published}")
    items = podcasts.get("items") if isinstance(podcasts, dict) else None
    if not isinstance(items, list):
        errors.append("podcasts.json 结构不对")
    else:
        if len(items) > 24:
            errors.append(f"播客条目过多：{len(items)}")
        for item in items:
            if item.get("kind") not in PODCAST_KINDS:
                errors.append(f"播客分类不对：{item.get('kind')}")
            blob = f"{item.get('title', '')} {item.get('url', '')}".lower()
            if "patreon" in blob or "patron" in blob:
                errors.append(f"播客含付费内容：{item.get('title', '')[:80]}")
            host = ""
            url = item.get("url") or ""
            if "://" in url:
                host = url.split("/")[2].lower()
            if not any(host.endswith(suffix) for suffix in ALLOWED_HOST_SUFFIXES):
                errors.append(f"播客链接不是官方页面：{url[:80]}")
            if len(item.get("summary") or "") > MAX_SUMMARY:
                errors.append("播客简介过长")
            if "enclosure" in item or "audio" in item:
                errors.append("播客 JSON 不应包含音频文件地址")
    if not isinstance(fixtures, dict):
        errors.append("fixtures.json 结构不对")
    else:
        if fixtures.get("scoreDisclaimer") != "比分来自最近一次成功更新，不是实时比分。":
            errors.append("赛程缺少非实时比分说明")
        blob = json.dumps(fixtures, ensure_ascii=False)
        for banned in ("实时直播", "LIVE", "live score", "x-apisports-key"):
            if banned in blob:
                errors.append(f"赛程数据出现不该有的字样：{banned}")
    if isinstance(status, dict):
        generated = status.get("generatedAt") or ""
        if generated and not generated.endswith("+08:00"):
            errors.append("状态里的生成时间不是北京时间")
    return errors


def main() -> int:
    directory = Path(sys.argv[1] if len(sys.argv) > 1 else "data")
    found = problems(directory)
    if found:
        for item in found:
            print(item)
        return 1
    print(f"verified {directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
