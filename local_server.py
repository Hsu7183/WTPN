from __future__ import annotations

import json
import os
import threading
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from scrape_news import refresh_news_index


PROJECT_ROOT = Path(__file__).resolve().parent
DOCS_ROOT = PROJECT_ROOT / "docs"
DATA_PATH = DOCS_ROOT / "data" / "news.json"
HOST = "127.0.0.1"
PORT = int(os.getenv("LOCAL_SERVER_PORT", "8000"))
LOGIN_PASSWORD = os.getenv("WTPN_LOGIN_PASSWORD", "23319448")
MAX_REQUEST_BODY = 4 * 1024
REQUEST_TIMEOUT_SECONDS = 5


class WTPNServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address: tuple[str, int]):
        super().__init__(server_address, WTPNRequestHandler)
        self.refresh_lock = threading.Lock()


class WTPNRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DOCS_ROOT), **kwargs)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def allowed_host(self) -> str | None:
        host = self.headers.get("Host", "").lower()
        port = self.server.server_address[1]
        if host in {f"127.0.0.1:{port}", f"localhost:{port}"}:
            return host
        return None

    def reject_invalid_host(self) -> bool:
        if self.allowed_host() is not None:
            return False
        self.respond_json(
            {"ok": False, "error": "invalid host"},
            status=HTTPStatus.FORBIDDEN,
        )
        return True

    def do_GET(self) -> None:
        if self.reject_invalid_host():
            return
        if urlparse(self.path).path.startswith("/api/"):
            self.respond_json(
                {"ok": False, "error": "not found"},
                status=HTTPStatus.NOT_FOUND,
            )
            return
        super().do_GET()

    def do_HEAD(self) -> None:
        if self.reject_invalid_host():
            return
        if urlparse(self.path).path.startswith("/api/"):
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
            return
        super().do_HEAD()

    def list_directory(self, path: str):
        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
        return None

    def do_POST(self) -> None:
        allowed_host = self.allowed_host()
        if allowed_host is None:
            self.respond_json(
                {"ok": False, "error": "invalid host"},
                status=HTTPStatus.FORBIDDEN,
            )
            return

        parsed = urlparse(self.path)
        if parsed.path != "/api/refresh-news":
            self.respond_json(
                {"ok": False, "error": "not found"},
                status=HTTPStatus.NOT_FOUND,
            )
            return

        if self.headers.get("Origin") != f"http://{allowed_host}":
            self.respond_json(
                {"ok": False, "error": "invalid origin"},
                status=HTTPStatus.FORBIDDEN,
            )
            return

        if self.headers.get_content_type() != "application/json":
            self.respond_json(
                {"ok": False, "error": "application/json required"},
                status=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
            )
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

        if not self.server.refresh_lock.acquire(blocking=False):
            self.respond_json(
                {"ok": False, "error": "refresh already in progress"},
                status=HTTPStatus.CONFLICT,
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
        finally:
            self.server.refresh_lock.release()

        self.respond_json(news_payload)

    def read_json_body(self) -> dict | None:
        content_length = self.headers.get("Content-Length")
        try:
            size = int(content_length) if content_length is not None else 0
        except ValueError:
            size = -1

        if size <= 0 or size > MAX_REQUEST_BODY:
            self.respond_json(
                {"ok": False, "error": "request body must be between 1 and 4096 bytes"},
                status=(
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE
                    if size > MAX_REQUEST_BODY
                    else HTTPStatus.BAD_REQUEST
                ),
            )
            return None

        self.connection.settimeout(REQUEST_TIMEOUT_SECONDS)
        try:
            raw_body = self.rfile.read(size)
            if len(raw_body) != size:
                raise ValueError("incomplete request body")
            payload = json.loads(raw_body.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("request body must be a JSON object")
            return payload
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TimeoutError):
            self.respond_json(
                {"ok": False, "error": "invalid JSON request body"},
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
    try:
        server = WTPNServer((HOST, PORT))
    except OSError as exc:
        print(f"Cannot start local server on {HOST}:{PORT}: {exc}")
        return 1

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
