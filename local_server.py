from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from scrape_news import refresh_news_index


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_PATH = PROJECT_ROOT / "docs" / "data" / "news.json"
HOST = os.getenv("LOCAL_SERVER_HOST", "127.0.0.1")
PORT = int(os.getenv("LOCAL_SERVER_PORT", "8000"))
LOGIN_PASSWORD = os.getenv("WTPN_LOGIN_PASSWORD", "23319448")


class WTPNRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PROJECT_ROOT), **kwargs)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/refresh-news":
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
            return

        payload = self.read_json_body()
        if payload is None:
            return

        if payload.get("password") != LOGIN_PASSWORD:
            self.respond_json(
                {"ok": False, "error": "invalid password"},
                status=HTTPStatus.FORBIDDEN,
            )
            return

        try:
            news_payload = refresh_news_index(DATA_PATH)
        except Exception as exc:  # pragma: no cover - operational fallback
            self.respond_json(
                {"ok": False, "error": str(exc)},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return

        self.respond_json(news_payload)

    def read_json_body(self) -> dict | None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            content_length = 0

        raw_body = self.rfile.read(content_length)
        if not raw_body:
            return {}

        try:
            return json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            self.respond_json(
                {"ok": False, "error": "invalid json body"},
                status=HTTPStatus.BAD_REQUEST,
            )
            return None

    def respond_json(self, payload: dict, *, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        print(f"[server] {self.address_string()} - {format % args}")


def main() -> int:
    server = ThreadingHTTPServer((HOST, PORT), WTPNRequestHandler)
    print(f"Serving WTPN at http://{HOST}:{PORT}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
