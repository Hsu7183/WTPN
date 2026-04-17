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

GENERAL_SEARCH_KEYWORDS = [
    "員警風紀",
    "警員風紀",
    "警察風紀",
    "員警 違紀",
    "警員 違紀",
    "員警 違法違紀",
    "警員 違法違紀",
    "員警 風紀案",
    "警員 風紀案",
]

BROAD_ROLE_SEARCH_TERMS = (
    "員警",
    "警員",
    "警察",
)

BROAD_MISCONDUCT_SEARCH_TERMS = (
    "收賄",
    "索賄",
    "貪污",
    "涉貪",
    "貪瀆",
    "圖利",
    "包庇",
    "包庇 詐團",
    "包庇 賭場",
    "包庇 賭博電玩",
    "洩密",
    "洩個資",
    "偷查個資",
    "查個資",
    "違法查個資",
    "非法查詢個資",
    "勾結 詐團",
    "勾結 博弈",
    "勾結 黑道",
    "通風報信",
    "洩漏 臨檢情資",
    "改單",
    "銷單",
    "吞贓",
    "酒駕",
    "吸毒",
    "販毒",
    "性騷",
    "性侵",
    "猥褻",
    "援交",
    "偷拍",
    "妨害秘密",
    "合成 性影像",
    "不當交往",
    "詐領加班費",
    "浮報 加班費",
    "偽造文書",
    "登載不實",
)

SPECIAL_SEARCH_KEYWORDS = [
    "員警 不當交往",
    "非法查詢個資 員警",
    "員警 偷查個資",
    "警察 偷查個資",
    "副所長 偷查個資",
    "員警 違法查個資",
    "警察 違法查個資",
    "員警 查個資 討債",
    "警察 查個資 討債",
    "鍾文智 偷查個資",
    "鍾文智 查個資",
    "鍾文智 警察 個資",
    "鍾文智 員警 個資",
    "鍾文智 討債 警察",
    "黃文烈 親信 偷查個資",
    "黃文烈 親信 查個資",
    "黃文烈 親信 警察 個資",
    "黃文烈 親信 個資 討債",
    "警察 博弈 洩密",
    "員警 包庇 博弈",
    "員警 包庇 電玩",
    "員警 包庇 詐團",
    "員警 包庇 賭場",
    "員警 警示帳戶",
    "員警 165 系統 收賄",
    "員警 臨檢情資",
    "員警 個資外洩",
    "員警 外流 監視器",
    "員警 違反個資法",
    "員警 白單 圖利",
    "員警 紅單 圖利",
    "員警 開假罰單",
    "員警 製單 違法",
    "員警 侵占 證物",
    "員警 贓款",
    "員警 創意私房",
    "員警 針孔 偷拍",
    "男警 偷拍 女警",
    "員警 妨害秘密",
    "員警 性招待",
    "員警 養生館",
    "員警 護膚店",
    "員警 合成 性影像",
    "男警 合成 性影像",
    "員警 詐領加班費",
    "員警 浮報 加班費",
    "員警 偽造文書",
    "員警 登載不實",
]

RANK_FOCUSED_QUERY_MAP = {
    "巡佐": ("涉貪", "包庇", "酒駕", "偷拍", "改單"),
    "偵查佐": ("涉貪", "洩密", "吞贓", "偷拍", "偽造文書", "偷查個資"),
    "副所長": ("涉貪", "收賄", "洩密", "包庇", "偷查個資"),
    "所長": ("收賄", "包庇", "洩個資", "不當交往", "偷查個資"),
    "小隊長": ("涉貪", "洩密", "包庇", "偷拍"),
    "警務員": ("涉貪", "酒駕", "吸毒", "洩密"),
    "巡官": ("詐領加班費", "浮報 加班費", "酒駕"),
    "交通警察": ("改單", "銷單", "洩密", "開假罰單"),
    "刑警": ("洩密", "包庇", "涉貪", "勾結 詐團"),
    "警政監": ("博弈 洩密", "涉貪", "收賄"),
    "男警": ("偷拍", "性騷", "性侵", "妨害秘密", "不實影像"),
    "女警": ("涉貪", "勾結 詐團"),
}


def dedupe_preserve_order(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))


def build_search_keywords() -> list[str]:
    keywords: list[str] = list(GENERAL_SEARCH_KEYWORDS)

    for role in BROAD_ROLE_SEARCH_TERMS:
        keywords.extend(
            f"{role} {misconduct}"
            for misconduct in BROAD_MISCONDUCT_SEARCH_TERMS
        )

    for role, misconducts in RANK_FOCUSED_QUERY_MAP.items():
        keywords.extend(f"{role} {misconduct}" for misconduct in misconducts)

    keywords.extend(SPECIAL_SEARCH_KEYWORDS)
    return dedupe_preserve_order(keywords)


SEARCH_KEYWORDS = build_search_keywords()

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
    "鏡週刊",
    "壹蘋新聞網",
    "CTWANT",
    "ETtoday新聞雲",
    "LINE TODAY",
    "MSN",
    "NOWnews今日新聞",
    "TVBS新聞網",
    "Yahoo新聞",
    "yesmedia.com.tw",
    "三立新聞網 Setn.com",
    "太報",
    "東森新聞",
    "風傳媒",
}

TRUSTED_SOURCE_ALIASES = {
    "三立新聞網 Setn.com": {
        "三立新聞網",
        "setn",
        "setn.com",
        "三立",
    },
    "東森新聞": {
        "東森新聞",
        "EBC東森新聞",
        "東森新聞雲",
    },
    "LINE TODAY": {
        "LINE TODAY",
        "LINE Today",
        "linetoday",
    },
}

TAG_RULES = {
    "收賄": ["收賄", "賄賂", "貪瀆", "貪污", "涉貪", "圖利", "索賄", "回扣"],
    "性紀律": ["性騷", "性侵", "猥褻", "援交", "性招待", "護膚店", "不當場所"],
    "酒駕": ["酒駕"],
    "包庇": ["包庇", "關說", "護航", "縱放"],
    "洩密": ["洩密", "洩個資", "偷查個資", "查個資", "個資", "偵查資料", "監視器", "警示帳戶"],
    "詐欺": ["詐欺", "詐團", "詐騙集團", "洗錢", "車手"],
    "博弈": ["博弈", "賭場", "賭博電玩", "地下匯兌"],
    "毒品": ["毒品", "吸毒", "販毒", "安非他命", "K他命"],
    "吞贓": ["吞贓", "贓款", "證物室", "侵占"],
    "偷拍": ["偷拍", "針孔", "妨害秘密", "不實影像", "性影像", "創意私房"],
    "文書造假": [
        "偽造文書",
        "登載不實",
        "開假罰單",
        "假罰單",
        "白單",
        "紅單",
        "製單違法",
        "詐領加班費",
        "浮報加班費",
        "浮報",
    ],
    "風紀": ["風紀", "警紀", "違紀", "懲處", "記過", "免職"],
}

RELEVANT_ROLE_TERMS = (
    "警察",
    "員警",
    "警員",
    "男警",
    "女警",
    "巡官",
    "警務員",
    "偵查佐",
    "巡佐",
    "副所長",
    "所長",
    "小隊長",
    "派出所",
    "分局",
    "國道警",
    "北市警",
    "新北警",
    "中市警",
    "高市警",
    "市警",
    "縣警",
    "警政監",
)

RELEVANT_MISCONDUCT_TERMS = (
    "風紀",
    "警紀",
    "違紀",
    "違法",
    "收賄",
    "索賄",
    "貪污",
    "涉貪",
    "貪瀆",
    "圖利",
    "包庇",
    "洩密",
    "通風報信",
    "臨檢情資",
    "個資",
    "偷查個資",
    "查個資",
    "違法查個資",
    "違反個資法",
    "警示帳戶",
    "詐團",
    "詐騙集團",
    "黑道",
    "博弈",
    "賭場",
    "賭博電玩",
    "改單",
    "銷單",
    "白單",
    "紅單",
    "吞贓",
    "贓款",
    "證物",
    "酒駕",
    "毒品",
    "吸毒",
    "販毒",
    "性騷",
    "性侵",
    "猥褻",
    "援交",
    "偷拍",
    "針孔",
    "妨害秘密",
    "不實影像",
    "性影像",
    "創意私房",
    "不當交往",
    "性招待",
    "養生館",
    "護膚店",
    "詐領加班費",
    "浮報",
    "加班費",
    "偽造文書",
    "登載不實",
    "開假罰單",
    "假罰單",
    "免職",
    "停職",
    "未繳槍",
)

RELEVANT_CASE_CONTEXT_TERMS = (
    "涉",
    "疑",
    "遭",
    "起訴",
    "被訴",
    "遭訴",
    "送辦",
    "法辦",
    "收押",
    "羈押",
    "交保",
    "聲押",
    "判刑",
    "認罪",
    "免職",
    "停職",
    "記過",
    "記大過",
    "撤職",
    "搜索",
    "約談",
    "函送",
    "偵辦",
    "查辦",
    "臨檢",
    "開鍘",
    "求刑",
    "拒測",
    "拒檢",
    "下場出爐",
)

RSS_TEMPLATE = (
    "https://news.google.com/rss/search"
    "?q={query}+when:{lookback_days}d&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
)

IRRELEVANT_ARTICLE_PATTERNS = (
    "花蓮縣府主任遭爆刁難基層員警",
    "花縣府主任違停嗆警",
    "花蓮縣府官員遭檢舉違停",
    "違停開單警控遭刁難",
    "交通糾紛警察不開單",
    "北市警未開單遭檢舉圖利",
    "檢舉達人不爽警沒開單",
    "調查官超速扣牌銷單",
    "假警察",
    "假刑警",
    "盜用警察照片",
    "圍棋師猥褻",
    "警方及時阻詐",
)

ROLE_MARKER_PATTERN = re.compile(r"[0-9一二三四五六七八九十兩]+警")


def iso_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_request(url: str) -> Request:
    return Request(url, headers={"User-Agent": USER_AGENT})


def normalize_source_name(value: str) -> str:
    return re.sub(r"[\s._-]+", "", value).lower()


def canonicalize_source(source: str) -> str:
    if source in TRUSTED_SOURCES:
        return source

    normalized_source = normalize_source_name(source)
    for canonical, aliases in TRUSTED_SOURCE_ALIASES.items():
        alias_candidates = {canonical, *aliases}
        if any(
            normalize_source_name(alias) in normalized_source
            for alias in alias_candidates
        ):
            return canonical

    return ""


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


def load_existing_payload(output_path: Path = OUTPUT_PATH) -> dict:
    if not output_path.exists():
        return {}

    return json.loads(output_path.read_text(encoding="utf-8"))


def is_relevant_article(
    title: str,
    summary: str = "",
    matched_keywords: Iterable[str] = (),
) -> bool:
    haystack = " ".join([title, summary, *matched_keywords])
    if any(pattern in haystack for pattern in IRRELEVANT_ARTICLE_PATTERNS):
        return False

    content_haystack = " ".join([title, summary])
    has_role = any(term in content_haystack for term in RELEVANT_ROLE_TERMS) or bool(
        ROLE_MARKER_PATTERN.search(content_haystack)
    )
    misconduct_hits = sum(
        1 for term in RELEVANT_MISCONDUCT_TERMS if term in content_haystack
    )
    has_misconduct = misconduct_hits > 0
    has_case_context = any(
        term in content_haystack for term in RELEVANT_CASE_CONTEXT_TERMS
    )
    return has_role and has_misconduct and (has_case_context or misconduct_hits >= 2)


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
        raw_source = (item.findtext("source") or "").strip()
        source = canonicalize_source(raw_source)
        if not source:
            continue

        raw_title = (item.findtext("title") or "").strip()
        title = clean_title(raw_title, source)
        link = (item.findtext("link") or "").strip()
        description = clean_summary(
            strip_html(item.findtext("description") or ""),
            title,
            source,
        )
        if not is_relevant_article(title, description, [query]):
            continue

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


def load_existing_articles(
    output_path: Path = OUTPUT_PATH,
    payload: dict | None = None,
) -> list[dict]:
    payload = payload or load_existing_payload(output_path)
    if not payload:
        return []

    generated_at = payload.get("generated_at")
    articles = payload.get("articles") or []
    hydrated = [
        hydrate_article(article, default_seen_at=generated_at)
        for article in articles
    ]
    return [
        article
        for article in hydrated
        if is_relevant_article(
            article["title"],
            article["summary"],
            article["matched_keywords"],
        )
    ]


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
    refresh_attempted_at: str,
    fetched_articles: int,
    new_articles: int,
    failed_queries: list[dict[str, str]],
) -> dict:
    sources = sorted({article["source"] for article in articles})
    tags = sorted({tag for article in articles for tag in article["tags"]})
    return {
        "project": PROJECT_NAME,
        "generated_at": generated_at,
        "refresh_attempted_at": refresh_attempted_at,
        "lookback_days": LOOKBACK_DAYS,
        "keywords": SEARCH_KEYWORDS,
        "trusted_sources": sorted(TRUSTED_SOURCES),
        "available_sources": sources,
        "available_tags": tags,
        "fetched_articles": fetched_articles,
        "new_articles": new_articles,
        "failed_query_count": len(failed_queries),
        "failed_queries": failed_queries,
        "total_articles": len(articles),
        "articles": articles,
    }


def refresh_news_index(output_path: Path = OUTPUT_PATH) -> dict:
    refreshed_at = iso_utc_now()
    existing_payload = load_existing_payload(output_path)
    existing_generated_at = existing_payload.get("generated_at")
    existing_articles = merge_articles(
        load_existing_articles(output_path, payload=existing_payload),
        [],
        refreshed_at,
    )
    collected: list[dict] = []
    failed_queries: list[dict[str, str]] = []

    for query in SEARCH_KEYWORDS:
        try:
            feed_bytes = fetch_feed(query)
            collected.extend(parse_feed(feed_bytes, query))
        except Exception as exc:  # pragma: no cover - operational fallback
            failed_queries.append({"query": query, "error": str(exc)})
            print(f"[warn] failed to fetch '{query}': {exc}", file=sys.stderr)

    fresh_articles = merge_articles([], collected, refreshed_at)
    existing_keys = {article_key(article) for article in existing_articles}
    new_articles = sum(
        1 for article in fresh_articles if article_key(article) not in existing_keys
    )
    articles = merge_articles(existing_articles, fresh_articles, refreshed_at)
    successful_fetch = len(failed_queries) < len(SEARCH_KEYWORDS)
    generated_at = refreshed_at if successful_fetch or not existing_generated_at else existing_generated_at
    payload = build_payload(
        articles,
        generated_at=generated_at,
        refresh_attempted_at=refreshed_at,
        fetched_articles=len(fresh_articles),
        new_articles=new_articles,
        failed_queries=failed_queries,
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
    if payload["failed_query_count"] >= len(SEARCH_KEYWORDS):
        print("All queries failed; dataset freshness was not updated.", file=sys.stderr)
        return 1
    if payload["failed_query_count"] > 0:
        print(
            f"{payload['failed_query_count']} queries failed during refresh.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
