from __future__ import annotations

import http.client
import json
import threading
import unittest
from unittest.mock import patch

import local_server


class LocalServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = local_server.WTPNServer((local_server.HOST, 0))
        cls.port = cls.server.server_address[1]
        cls.host = f"127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, bytes]:
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()

    def refresh_headers(self, **extra: str) -> dict[str, str]:
        return {
            "Host": self.host,
            "Origin": f"http://{self.host}",
            "Content-Type": "application/json",
            **extra,
        }

    def test_serves_docs_but_not_repository_files(self) -> None:
        self.assertEqual(self.request("GET", "/", headers={"Host": self.host})[0], 200)
        self.assertEqual(
            self.request(
                "GET",
                "/",
                headers={"Host": f"localhost:{self.port}"},
            )[0],
            200,
        )
        for path in (
            "/local_server.py",
            "/scrape_news.py",
            "/.git/config",
            "/.github/workflows/update-news.yml",
        ):
            with self.subTest(path=path):
                self.assertEqual(
                    self.request("GET", path, headers={"Host": self.host})[0],
                    404,
                )

    def test_rejects_untrusted_host_and_origin(self) -> None:
        self.assertEqual(
            self.request("GET", "/", headers={"Host": "attacker.example"})[0],
            403,
        )
        body = json.dumps({"password": local_server.LOGIN_PASSWORD}).encode()
        self.assertEqual(
            self.request(
                "POST",
                "/api/refresh-news",
                body=body,
                headers=self.refresh_headers(Origin="http://attacker.example"),
            )[0],
            403,
        )

    def test_rejects_oversized_or_non_object_json(self) -> None:
        self.assertEqual(
            self.request(
                "POST",
                "/api/refresh-news",
                body=b"{}",
                headers={
                    **self.refresh_headers(),
                    "Content-Type": "text/plain",
                },
            )[0],
            415,
        )
        oversized = b"{" + b" " * local_server.MAX_REQUEST_BODY
        self.assertEqual(
            self.request(
                "POST",
                "/api/refresh-news",
                body=oversized,
                headers=self.refresh_headers(),
            )[0],
            413,
        )
        for body in (b"[]", b"null", b"1", b"\xff", b"{"):
            with self.subTest(body=body):
                self.assertEqual(
                    self.request(
                        "POST",
                        "/api/refresh-news",
                        body=body,
                        headers=self.refresh_headers(),
                    )[0],
                    400,
                )

    def test_only_one_refresh_runs_at_a_time(self) -> None:
        started = threading.Event()
        release = threading.Event()
        first_result: list[int] = []

        def fake_refresh(_path):
            started.set()
            release.wait(timeout=3)
            return {"ok": True, "articles": []}

        body = json.dumps({"password": local_server.LOGIN_PASSWORD}).encode()

        def first_request() -> None:
            first_result.append(
                self.request(
                    "POST",
                    "/api/refresh-news",
                    body=body,
                    headers=self.refresh_headers(),
                )[0]
            )

        with patch.object(local_server, "refresh_news_index", side_effect=fake_refresh) as mocked:
            request_thread = threading.Thread(target=first_request)
            request_thread.start()
            self.assertTrue(started.wait(timeout=2))
            try:
                second_status, _ = self.request(
                    "POST",
                    "/api/refresh-news",
                    body=body,
                    headers=self.refresh_headers(),
                )
                self.assertEqual(second_status, 409)
            finally:
                release.set()
                request_thread.join(timeout=2)

        self.assertEqual(first_result, [200])
        self.assertEqual(mocked.call_count, 1)


if __name__ == "__main__":
    unittest.main()
