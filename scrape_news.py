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


def iso_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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


def article_key(article: dict) -> str:
    return article.get("link") or article["id"]


def build_search_text(article: dict) -> str:
    return " ".join(
        [
            article["title"],
            article["source"],
            article["summary"],
            " ".join(article["matched_keywords"]),
            " ".join(article["tags"]),
        ]
    ).lower()


def format_published_label(value: str) -> str:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt.astimezone().strftime("%Y-%m-%d %H:%M")


def hydrate_article(article: dict, default_seen_at: str | None = None) -> dict:
    item = dict(article)
    item["matched_keywords"] = sorted(set(item.get("matched_keywords") or []))
    item["tags"] = sorted(set(item.get("tags") or []))
    item["summary"] = item.get("summary") or ""
    item["source"] = item.get("source") or ""
    item["title"] = item.get("title") or ""
    item["link"] = item.get("link") or ""
    item["published_label"] = item.get("published_label") or format_published_label(
        item["published_at"]
    )
    item["first_seen_at"] = item.get("first_seen_at") or default_seen_at or item["published_at"]
    item["last_seen_at"] = item.get("last_seen_at") or item["first_seen_at"]
    item["search_text"] = build_search_text(item)
    return item


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


def load_existing_articles(output_path: Path = OUTPUT_PATH) -> list[dict]:
    if not output_path.exists():
        return []

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    generated_at = payload.get("generated_at")
    articles = payload.get("articles") or []
    return [hydrate_article(article, default_seen_at=generated_at) for article in articles]


def merge_articles(
    existing_articles: Iterable[dict],
    fresh_articles: Iterable[dict],
    refreshed_at: str,
) -> list[dict]:
    merged: dict[str, dict] = {}

    for article in existing_articles:
        item = hydrate_article(article, default_seen_at=refreshed_at)
        merged[article_key(item)] = item

    for article in fresh_articles:
        item = hydrate_article(article, default_seen_at=refreshed_at)
        item["last_seen_at"] = refreshed_at
        key = article_key(item)
        existing = merged.get(key)

        if existing is None:
            item["first_seen_at"] = item.get("first_seen_at") or refreshed_at
            item["search_text"] = build_search_text(item)
            merged[key] = item
            continue

        existing["matched_keywords"] = sorted(
            set(existing["matched_keywords"]) | set(item["matched_keywords"])
        )
        existing["tags"] = sorted(set(existing["tags"]) | set(item["tags"]))
        existing["summary"] = existing["summary"] or item["summary"]
        existing["source"] = existing["source"] or item["source"]
        existing["title"] = existing["title"] or item["title"]
        existing["link"] = existing["link"] or item["link"]
        existing["published_label"] = existing["published_label"] or item["published_label"]
        existing["first_seen_at"] = existing.get("first_seen_at") or item["first_seen_at"]
        existing["last_seen_at"] = refreshed_at
        existing["search_text"] = build_search_text(existing)

    return sorted(
        merged.values(),
        key=lambda article: article["published_at"],
        reverse=True,
    )


def build_payload(
    articles: list[dict],
    *,
    generated_at: str,
    fetched_articles: int,
    new_articles: int,
) -> dict:
    sources = sorted({article["source"] for article in articles})
    tags = sorted({tag for article in articles for tag in article["tags"]})
    return {
        "project": PROJECT_NAME,
        "generated_at": generated_at,
        "lookback_days": LOOKBACK_DAYS,
        "keywords": SEARCH_KEYWORDS,
        "trusted_sources": sorted(TRUSTED_SOURCES),
        "available_sources": sources,
        "available_tags": tags,
        "fetched_articles": fetched_articles,
        "new_articles": new_articles,
        "total_articles": len(articles),
        "articles": articles,
    }


def refresh_news_index(output_path: Path = OUTPUT_PATH) -> dict:
    refreshed_at = iso_utc_now()
    existing_articles = merge_articles(
        load_existing_articles(output_path),
        [],
        refreshed_at,
    )
    collected: list[dict] = []

    for query in SEARCH_KEYWORDS:
        try:
            feed_bytes = fetch_feed(query)
            collected.extend(parse_feed(feed_bytes, query))
        except Exception as exc:  # pragma: no cover - operational fallback
            print(f"[warn] failed to fetch '{query}': {exc}", file=sys.stderr)

    fresh_articles = merge_articles([], collected, refreshed_at)
    existing_keys = {article_key(article) for article in existing_articles}
    new_articles = sum(
        1 for article in fresh_articles if article_key(article) not in existing_keys
    )
    articles = merge_articles(existing_articles, fresh_articles, refreshed_at)
    payload = build_payload(
        articles,
        generated_at=refreshed_at,
        fetched_articles=len(fresh_articles),
        new_articles=new_articles,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload


def main() -> int:
    payload = refresh_news_index()
    print(
        "Wrote "
        f"{payload['total_articles']} stored articles "
        f"({payload['new_articles']} new, {payload['fetched_articles']} fetched)"
        f" to {OUTPUT_PATH}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
