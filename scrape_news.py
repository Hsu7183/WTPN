from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Iterable
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


PROJECT_NAME = "WTPN"
OUTPUT_PATH = Path("docs/data/news.json")
MAX_ITEMS_PER_QUERY = int(os.getenv("MAX_ITEMS_PER_QUERY", "30"))
LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "365"))
TIMEOUT_SECONDS = 30
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)

SEARCH_KEYWORDS = [
    "台灣警察風紀",
    "警察 收賄",
    "警察 警紀",
    "員警 貪污",
    "警察 包庇",
    "警察 洩密",
    "員警 酒駕",
]

TRUSTED_SOURCES = {
    "中央社",
    "中時新聞網",
    "公視新聞網",
    "台視新聞網",
    "台灣好新聞",
    "台灣華報",
    "品觀點",
    "民眾新聞網",
    "民視新聞網",
    "自由時報",
    "聯合新聞網",
    "華視新聞網",
    "翻爆",
    "鏡新聞",
    "壹蘋新聞網",
    "CTWANT",
    "ETtoday新聞雲",
    "MSN",
    "NOWnews今日新聞",
    "TVBS新聞網",
    "Yahoo新聞",
    "yesmedia.com.tw",
    "三立新聞網 Setn.com",
    "風傳媒",
}

TAG_RULES = {
    "收賄": ["收賄", "賄選", "賄賂", "貪瀆", "貪污"],
    "性紀律": ["性騷", "性侵", "猥褻", "護膚店", "不當場所"],
    "酒駕": ["酒駕"],
    "包庇": ["包庇", "關說"],
    "洩密": ["洩密", "個資", "偵查資料"],
    "詐欺": ["詐欺", "洗錢", "車手"],
    "風紀": ["風紀", "警紀", "懲處", "記過"],
}

RSS_TEMPLATE = (
    "https://news.google.com/rss/search"
    "?q={query}+when:{lookback_days}d&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
)


def build_request(url: str) -> Request:
    return Request(url, headers={"User-Agent": USER_AGENT})


def fetch_feed(query: str) -> bytes:
    url = RSS_TEMPLATE.format(
        query=quote_plus(query),
        lookback_days=LOOKBACK_DAYS,
    )
    with urlopen(build_request(url), timeout=TIMEOUT_SECONDS) as response:
        return response.read()


def parse_datetime(value: str) -> tuple[str, str]:
    dt = parsedate_to_datetime(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    iso_value = dt.isoformat().replace("+00:00", "Z")
    label = dt.astimezone().strftime("%Y-%m-%d %H:%M")
    return iso_value, label


def strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_title(title: str, source: str) -> str:
    suffix = f" - {source}"
    if title.endswith(suffix):
        return title[: -len(suffix)].strip()
    return title.strip()


def clean_summary(summary: str, title: str, source: str) -> str:
    compact = re.sub(r"\s+", " ", summary).strip()
    trivial_summaries = {
        title,
        f"{title} {source}",
        f"{title} - {source}",
        f"{title}{source}",
    }
    if compact in trivial_summaries:
        return ""
    return compact


def classify_tags(chunks: Iterable[str]) -> list[str]:
    haystack = " ".join(chunks)
    tags: list[str] = []
    for tag, needles in TAG_RULES.items():
        if any(needle in haystack for needle in needles):
            tags.append(tag)
    return tags


def article_id(source: str, title: str, published_at: str) -> str:
    seed = f"{source}|{title}|{published_at}"
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


def parse_feed(xml_bytes: bytes, query: str) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    entries: list[dict] = []

    for item in root.findall("./channel/item")[:MAX_ITEMS_PER_QUERY]:
        source = (item.findtext("source") or "").strip()
        if not source or source not in TRUSTED_SOURCES:
            continue

        raw_title = (item.findtext("title") or "").strip()
        title = clean_title(raw_title, source)
        link = (item.findtext("link") or "").strip()
        description = clean_summary(
            strip_html(item.findtext("description") or ""),
            title,
            source,
        )
        published_at, published_label = parse_datetime(item.findtext("pubDate") or "")
        tags = classify_tags([title, description, query])

        entries.append(
            {
                "id": article_id(source, title, published_at),
                "title": title,
                "source": source,
                "link": link,
                "summary": description,
                "published_at": published_at,
                "published_label": published_label,
                "matched_keywords": [query],
                "tags": tags,
            }
        )

    return entries


def merge_articles(articles: Iterable[dict]) -> list[dict]:
    merged: dict[str, dict] = {}

    for item in articles:
        key = item["link"] or item["id"]
        existing = merged.get(key)
        if existing is None:
            item["search_text"] = " ".join(
                [
                    item["title"],
                    item["source"],
                    item["summary"],
                    " ".join(item["matched_keywords"]),
                    " ".join(item["tags"]),
                ]
            ).lower()
            merged[key] = item
            continue

        existing["matched_keywords"] = sorted(
            set(existing["matched_keywords"]) | set(item["matched_keywords"])
        )
        existing["tags"] = sorted(set(existing["tags"]) | set(item["tags"]))
        existing["search_text"] = " ".join(
            [
                existing["title"],
                existing["source"],
                existing["summary"],
                " ".join(existing["matched_keywords"]),
                " ".join(existing["tags"]),
            ]
        ).lower()

    return sorted(
        merged.values(),
        key=lambda article: article["published_at"],
        reverse=True,
    )


def build_payload(articles: list[dict]) -> dict:
    sources = sorted({article["source"] for article in articles})
    tags = sorted({tag for article in articles for tag in article["tags"]})
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "project": PROJECT_NAME,
        "generated_at": generated_at,
        "lookback_days": LOOKBACK_DAYS,
        "keywords": SEARCH_KEYWORDS,
        "trusted_sources": sorted(TRUSTED_SOURCES),
        "available_sources": sources,
        "available_tags": tags,
        "total_articles": len(articles),
        "articles": articles,
    }


def main() -> int:
    collected: list[dict] = []

    for query in SEARCH_KEYWORDS:
        try:
            feed_bytes = fetch_feed(query)
            collected.extend(parse_feed(feed_bytes, query))
        except Exception as exc:  # pragma: no cover - operational fallback
            print(f"[warn] failed to fetch '{query}': {exc}", file=sys.stderr)

    articles = merge_articles(collected)
    payload = build_payload(articles)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Wrote {payload['total_articles']} articles to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
