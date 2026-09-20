"""Local, read-only HTTP application for the ConstructionSight operator GUI."""

from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from constructionsight.operator_dashboard import build_dashboard_snapshot
from constructionsight.storage.database import (
    create_database_engine,
    database_url_from_path,
    initialize_database,
    managed_session,
    session_factory,
)

_UI_PATH = Path(__file__).with_name("operator_ui.html")


def create_handler(database_path: Path) -> type[BaseHTTPRequestHandler]:
    """Build a request handler bound to one local SQLite database."""

    engine = create_database_engine(database_url_from_path(database_path))
    initialize_database(engine)
    factory = session_factory(engine)

    class OperatorHandler(BaseHTTPRequestHandler):
        """Serve the dashboard shell and its read-only JSON snapshot."""

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/":
                self._send(HTTPStatus.OK, "text/html; charset=utf-8", _UI_PATH.read_bytes())
                return
            if path == "/api/health":
                self._send_json({"status": "ok", "read_only": True})
                return
            if path == "/api/snapshot":
                with managed_session(factory) as session:
                    snapshot = build_dashboard_snapshot(session)
                self._send_json(snapshot.model_dump(mode="json"))
                return
            self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)

        def _send_json(
            self,
            payload: object,
            *,
            status: HTTPStatus = HTTPStatus.OK,
        ) -> None:
            body = json.dumps(payload, sort_keys=True).encode("utf-8")
            self._send(status, "application/json; charset=utf-8", body)

        def _send(
            self,
            status: HTTPStatus,
            content_type: str,
            body: bytes,
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", _content_security_policy())
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    return OperatorHandler


def _content_security_policy() -> str:
    return "; ".join(
        [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline'",
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data:",
            "connect-src 'self'",
            "frame-ancestors 'none'",
            "base-uri 'none'",
            "form-action 'none'",
        ]
    )


def main() -> None:
    """Run the local-only operator application."""

    parser = argparse.ArgumentParser(description="ConstructionSight operator GUI")
    parser.add_argument("--database", type=Path, default=Path("data/constructionsight.sqlite3"))
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    server = ThreadingHTTPServer(
        ("127.0.0.1", args.port),
        create_handler(args.database),
    )
    print(f"ConstructionSight operator GUI: http://127.0.0.1:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
