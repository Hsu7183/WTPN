import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scrape_news


def make_article(
    *,
    link: str,
    title: str = "員警涉貪遭起訴",
    summary: str = "案件由檢方偵辦",
    published_at: str = "2026-01-01T00:00:00Z",
    first_seen_at: str = "2026-01-02T00:00:00Z",
    last_seen_at: str = "2026-01-03T00:00:00Z",
    matched_keywords=None,
    tags=None,
):
    return {
        "id": "legacy-id",
        "title": title,
        "source": "中央社",
        "link": link,
        "summary": summary,
        "published_at": published_at,
        "published_label": "legacy label",
        "matched_keywords": matched_keywords or [],
        "tags": tags or [],
        "first_seen_at": first_seen_at,
        "last_seen_at": last_seen_at,
        "search_text": "legacy search text",
    }


class UrlNormalizationTests(unittest.TestCase):
    def test_google_rss_variants_and_tracking_parameters_share_a_key(self):
        rss_link = (
            "https://NEWS.GOOGLE.COM/rss/articles/ABC123/"
            "?oc=5&hl=zh-TW&gl=TW&ceid=TW:zh-Hant&utm_source=test"
        )
        article_link = "http://news.google.com/articles/ABC123?fbclid=tracking"

        expected = "https://news.google.com/articles/ABC123"
        self.assertEqual(scrape_news.normalize_article_url(rss_link), expected)
        self.assertEqual(scrape_news.normalize_article_url(article_link), expected)

    def test_non_tracking_parameters_are_preserved_and_sorted(self):
        link = "https://example.com/story/?b=2&utm_medium=rss&a=1#section"

        self.assertEqual(
            scrape_news.normalize_article_url(link),
            "https://example.com/story?a=1&b=2",
        )


class FeedParsingTests(unittest.TestCase):
    def test_bad_item_date_is_skipped_and_raw_source_suffix_is_removed(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss><channel>
          <item>
            <title>員警涉貪遭起訴 - 聯合報</title>
            <source>聯合報</source>
            <link>https://example.com/bad</link>
            <description>員警涉貪案件由檢方偵辦</description>
            <pubDate>not a date</pubDate>
          </item>
          <item>
            <title>員警涉貪遭起訴 - 聯合報</title>
            <source>聯合報</source>
            <link>https://example.com/good</link>
            <description>員警涉貪案件由檢方偵辦</description>
            <pubDate>Wed, 01 Jan 2025 00:00:00 GMT</pubDate>
          </item>
        </channel></rss>""".encode("utf-8")

        articles = scrape_news.parse_feed(xml, "員警 涉貪")

        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["source"], "聯合新聞網")
        self.assertEqual(articles[0]["title"], "員警涉貪遭起訴")
        self.assertEqual(articles[0]["link"], "https://example.com/good")


class MergeArticlesTests(unittest.TestCase):
    def test_same_url_merges_history_and_uses_latest_available_content(self):
        old = make_article(
            link="https://news.google.com/rss/articles/SAME?oc=5",
            title="舊標題：員警涉貪",
            summary="舊摘要",
            published_at="2026-01-03T00:00:00Z",
            first_seen_at="2026-01-04T00:00:00Z",
            last_seen_at="2026-01-05T00:00:00Z",
            matched_keywords=["員警 涉貪"],
            tags=["收賄"],
        )
        latest = make_article(
            link="https://news.google.com/articles/SAME?hl=zh-TW",
            title="最新標題：員警酒駕遭起訴",
            summary="最新摘要",
            published_at="2026-01-05T00:00:00Z",
            first_seen_at="2026-01-06T00:00:00Z",
            last_seen_at="2026-01-08T00:00:00Z",
            matched_keywords=["員警 酒駕"],
            tags=["酒駕"],
        )
        middle = make_article(
            link="https://news.google.com/rss/articles/SAME?ceid=TW:zh-Hant",
            title="中間版本：員警涉貪",
            summary="中間摘要",
            published_at="2026-01-04T00:00:00Z",
            first_seen_at="2026-01-05T00:00:00Z",
            last_seen_at="2026-01-06T00:00:00Z",
            matched_keywords=["警察 涉貪"],
            tags=["風紀"],
        )

        result = scrape_news.merge_articles(
            [old, latest, middle],
            [],
            "2026-02-01T00:00:00Z",
        )

        self.assertEqual(len(result), 1)
        merged = result[0]
        self.assertEqual(merged["title"], latest["title"])
        self.assertEqual(merged["summary"], latest["summary"])
        self.assertEqual(merged["published_at"], old["published_at"])
        self.assertEqual(merged["first_seen_at"], old["first_seen_at"])
        self.assertEqual(merged["last_seen_at"], latest["last_seen_at"])
        self.assertEqual(
            merged["matched_keywords"],
            ["員警 涉貪", "員警 酒駕", "警察 涉貪"],
        )
        self.assertTrue({"收賄", "酒駕", "風紀"}.issubset(merged["tags"]))
        self.assertEqual(merged["id"], scrape_news.article_id(merged))

    def test_fresh_observation_updates_content_but_keeps_earliest_dates(self):
        existing = make_article(
            link="https://example.com/news/42?utm_source=old",
            title="員警涉貪舊標題",
            summary="舊摘要",
            published_at="2026-01-01T00:00:00Z",
            first_seen_at="2026-01-02T00:00:00Z",
            last_seen_at="2026-01-03T00:00:00Z",
        )
        fresh = {
            "title": "員警涉貪更新標題",
            "source": "中央社",
            "link": "https://example.com/news/42?utm_campaign=new",
            "summary": "更新摘要",
            "published_at": "2026-01-04T00:00:00Z",
            "matched_keywords": ["員警 涉貪"],
            "tags": ["收賄"],
        }

        result = scrape_news.merge_articles(
            [existing], [fresh], "2026-02-01T00:00:00Z"
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], fresh["title"])
        self.assertEqual(result[0]["summary"], fresh["summary"])
        self.assertEqual(result[0]["published_at"], existing["published_at"])
        self.assertEqual(result[0]["first_seen_at"], existing["first_seen_at"])
        self.assertEqual(result[0]["last_seen_at"], "2026-02-01T00:00:00Z")

    def test_same_title_on_different_urls_does_not_merge(self):
        first = make_article(link="https://example.com/news/one")
        second = make_article(link="https://example.com/news/two")

        result = scrape_news.merge_articles(
            [first, second], [], "2026-02-01T00:00:00Z"
        )

        self.assertEqual(len(result), 2)
        self.assertEqual(len({article["id"] for article in result}), 2)


class MigrationAndPersistenceTests(unittest.TestCase):
    def test_payload_migration_is_idempotent_and_rebuilds_metadata(self):
        first = make_article(
            link="https://news.google.com/rss/articles/MIGRATE?oc=5",
            matched_keywords=["員警 涉貪"],
            tags=["收賄"],
        )
        second = make_article(
            link="https://news.google.com/articles/MIGRATE?hl=zh-TW",
            title="更新標題：員警涉貪",
            last_seen_at="2026-01-04T00:00:00Z",
            matched_keywords=["警察 涉貪"],
            tags=["風紀"],
        )
        payload = {
            "generated_at": "2026-01-05T00:00:00Z",
            "refresh_attempted_at": "2026-01-05T00:00:00Z",
            "available_sources": [],
            "available_tags": [],
            "total_articles": 99,
            "articles": [first, second],
        }

        migrated = scrape_news.migrate_existing_payload(payload)
        migrated_again = scrape_news.migrate_existing_payload(migrated)

        self.assertEqual(migrated, migrated_again)
        self.assertEqual(migrated["total_articles"], 1)
        self.assertEqual(migrated["available_sources"], ["中央社"])
        self.assertTrue({"收賄", "風紀"}.issubset(migrated["available_tags"]))
        self.assertEqual(len(migrated["articles"]), 1)
        self.assertNotIn("published_label", migrated["articles"][0])
        self.assertNotIn("search_text", migrated["articles"][0])

    def test_atomic_writer_uses_compact_json_and_trailing_newline(self):
        payload = {"project": "WTPN", "message": "台灣", "articles": []}
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "news.json"

            scrape_news.write_payload_atomic(payload, output_path)

            raw = output_path.read_text(encoding="utf-8")
            self.assertTrue(raw.endswith("\n"))
            self.assertEqual(raw.count("\n"), 1)
            self.assertNotIn(": ", raw)
            self.assertEqual(json.loads(raw), payload)
            self.assertEqual(list(output_path.parent.glob("*.tmp")), [])

    def test_atomic_replace_failure_preserves_original_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "news.json"
            original = b'{"original":true}\n'
            output_path.write_bytes(original)

            with patch.object(scrape_news.os, "replace", side_effect=OSError("boom")):
                with self.assertRaises(OSError):
                    scrape_news.write_payload_atomic({"replacement": True}, output_path)

            self.assertEqual(output_path.read_bytes(), original)
            self.assertEqual(list(output_path.parent.glob("*.tmp")), [])

    def test_all_failed_queries_leave_existing_file_unchanged(self):
        payload = {
            "project": "WTPN",
            "generated_at": "2026-01-01T00:00:00Z",
            "refresh_attempted_at": "2026-01-01T00:00:00Z",
            "failed_query_count": 0,
            "failed_queries": [],
            "total_articles": 0,
            "articles": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "news.json"
            original = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            output_path.write_bytes(original)

            with patch.object(scrape_news, "SEARCH_KEYWORDS", ["query one", "query two"]):
                with patch.object(
                    scrape_news,
                    "fetch_feed",
                    side_effect=OSError("offline"),
                ):
                    result = scrape_news.refresh_news_index(output_path)

            self.assertEqual(output_path.read_bytes(), original)
            self.assertEqual(result["fetched_articles"], 0)
            self.assertEqual(result["new_articles"], 0)
            self.assertEqual(result["failed_query_count"], 2)
            self.assertEqual(len(result["failed_queries"]), 2)


if __name__ == "__main__":
    unittest.main()
