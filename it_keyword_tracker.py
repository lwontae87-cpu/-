#!/usr/bin/env python3
"""실시간 IT 이슈 키워드 수집기.

공개 API에서 최신 IT 기사/포스트 제목을 수집하고,
간단한 빈도 분석으로 블로그 아이디어용 키워드를 제공합니다.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Iterable

STOPWORDS = {
    "the",
    "a",
    "an",
    "to",
    "of",
    "in",
    "for",
    "and",
    "on",
    "is",
    "are",
    "with",
    "from",
    "new",
    "how",
    "why",
    "what",
    "when",
    "you",
    "your",
    "about",
    "this",
    "that",
    "will",
    "can",
    "it",
    "its",
    "into",
    "using",
    "use",
    "vs",
    "api",
    "app",
    "apps",
}

TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9+#.-]{1,30}")


@dataclass
class Item:
    title: str
    source: str
    created_at: dt.datetime


def fetch_json(url: str, timeout: int = 10) -> object:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "it-keyword-tracker/1.0 (+https://example.local)",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return json.loads(resp.read().decode(charset, errors="replace"))


def fetch_hacker_news(limit: int) -> list[Item]:
    story_ids = fetch_json("https://hacker-news.firebaseio.com/v0/topstories.json")
    if not isinstance(story_ids, list):
        return []

    items: list[Item] = []
    for sid in story_ids[: limit * 2]:
        if len(items) >= limit:
            break
        try:
            data = fetch_json(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json")
        except (urllib.error.URLError, TimeoutError):
            continue
        if not isinstance(data, dict):
            continue
        title = data.get("title")
        ts = data.get("time")
        if not isinstance(title, str) or not isinstance(ts, int):
            continue
        created_at = dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc)
        items.append(Item(title=title, source="hackernews", created_at=created_at))
    return items


def fetch_reddit_technology(limit: int) -> list[Item]:
    data = fetch_json(
        f"https://www.reddit.com/r/technology/hot.json?limit={limit}",
    )
    if not isinstance(data, dict):
        return []

    children = ((data.get("data") or {}).get("children") or [])
    items: list[Item] = []
    for entry in children:
        post = (entry or {}).get("data") if isinstance(entry, dict) else None
        if not isinstance(post, dict):
            continue
        title = post.get("title")
        created_utc = post.get("created_utc")
        if not isinstance(title, str) or not isinstance(created_utc, (int, float)):
            continue
        created_at = dt.datetime.fromtimestamp(created_utc, tz=dt.timezone.utc)
        items.append(Item(title=title, source="reddit", created_at=created_at))
    return items


def fetch_devto(limit: int) -> list[Item]:
    per_page = min(limit, 100)
    data = fetch_json(f"https://dev.to/api/articles?per_page={per_page}&top=7")
    if not isinstance(data, list):
        return []

    items: list[Item] = []
    for post in data[:limit]:
        if not isinstance(post, dict):
            continue
        title = post.get("title")
        published = post.get("published_at") or post.get("created_at")
        if not isinstance(title, str) or not isinstance(published, str):
            continue
        try:
            created_at = dt.datetime.fromisoformat(published.replace("Z", "+00:00"))
        except ValueError:
            continue
        items.append(Item(title=title, source="devto", created_at=created_at))
    return items


def collect_items(limit_per_source: int) -> list[Item]:
    collectors = [
        fetch_hacker_news,
        fetch_reddit_technology,
        fetch_devto,
    ]
    all_items: list[Item] = []
    for collector in collectors:
        try:
            all_items.extend(collector(limit_per_source))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            continue
    return all_items


def filter_by_hours(items: Iterable[Item], hours: int) -> list[Item]:
    threshold = dt.datetime.now(tz=dt.timezone.utc) - dt.timedelta(hours=hours)
    return [item for item in items if item.created_at >= threshold]


def extract_keywords(titles: Iterable[str], top_n: int) -> list[tuple[str, int]]:
    counter: collections.Counter[str] = collections.Counter()
    for title in titles:
        for raw in TOKEN_RE.findall(title.lower()):
            token = raw.strip(".-+#")
            if len(token) < 3 or token in STOPWORDS or token.isdigit():
                continue
            counter[token] += 1
    return counter.most_common(top_n)


def suggest_titles(keywords: list[tuple[str, int]]) -> list[str]:
    if not keywords:
        return []

    top = [k for k, _ in keywords[:5]]
    suggestions = [f"{dt.datetime.now().year}년 지금 뜨는 {top[0]} 이슈 총정리"]
    if len(top) >= 2:
        suggestions.append(f"{top[0]} vs {top[1]}: 최근 IT 트렌드 비교")
    if len(top) >= 3:
        suggestions.append(f"{top[0]}, {top[1]}, {top[2]}로 보는 이번 주 개발 생태계 변화")
    suggestions.append("실시간 키워드 기반으로 보는 다음 블로그 주제 10선")
    return suggestions


def print_report(items: list[Item], keywords: list[tuple[str, int]]) -> None:
    print("=== Real-time IT Issue Keywords ===")
    print(f"Collected items: {len(items)}")
    source_counter = collections.Counter(item.source for item in items)
    print(f"By source: {dict(source_counter)}")
    print()

    print("Top keywords:")
    for idx, (kw, cnt) in enumerate(keywords, start=1):
        print(f"{idx:2d}. {kw:<20} {cnt}")
    print()

    print("Recent sample titles:")
    for item in sorted(items, key=lambda x: x.created_at, reverse=True)[:10]:
        ts = item.created_at.strftime("%Y-%m-%d %H:%M UTC")
        print(f"- [{item.source}] {item.title} ({ts})")
    print()

    print("Suggested blog titles:")
    for s in suggest_titles(keywords):
        print(f"- {s}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="실시간 IT 이슈 키워드 수집기")
    parser.add_argument("--hours", type=int, default=24, help="최근 N시간")
    parser.add_argument("--limit", type=int, default=30, help="소스별 최대 수집 건수")
    parser.add_argument("--top", type=int, default=15, help="상위 키워드 개수")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.hours <= 0 or args.limit <= 0 or args.top <= 0:
        print("hours/limit/top은 1 이상의 정수여야 합니다.", file=sys.stderr)
        return 2

    items = collect_items(limit_per_source=args.limit)
    recent_items = filter_by_hours(items, hours=args.hours)
    keywords = extract_keywords((item.title for item in recent_items), top_n=args.top)

    if not recent_items:
        print("최근 조건에 맞는 데이터를 찾지 못했습니다. --hours 값을 늘려 보세요.")
        return 1

    print_report(recent_items, keywords)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
