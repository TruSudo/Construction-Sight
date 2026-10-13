"""One-command, read-only localhost Command Center backed by official SMARTS rows."""

from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

from constructionsight.security_fit import rank_leads
from constructionsight.smarts_active import collect_active
from constructionsight.smarts_api import USER_AGENT

ASSETS = Path(__file__).parent / "command_center"


def projection(snapshot: dict[str, Any]) -> dict[str, Any]:
    rows = rank_leads(snapshot["rows"])
    cutoff = (datetime.now(UTC) - timedelta(days=7)).isoformat()
    return {
        "rows": rows,
        "captured_at": snapshot["captured_at"],
        "requests": snapshot["requests"],
        "totals": snapshot["totals"],
        "baseline": snapshot["baseline"],
        "demo": snapshot.get("demo", False),
        "missing_count": snapshot["missing_count"],
        "duplicate_rows": snapshot.get("duplicate_rows", 0),
        "missing_identity_rows": snapshot.get("missing_identity_rows", 0),
        "kpis": {
            "total": len(rows),
            "high": sum(r["fit_band"] == "high" for r in rows),
            "review": sum(r["fit_band"] == "review" for r in rows),
            "low": sum(r["fit_band"] == "low" for r in rows),
            "new_week": sum(bool(r.get("first_seen") and r["first_seen"] >= cutoff) for r in rows),
        },
    }


def make_server(snapshot: dict[str, Any], port: int) -> ThreadingHTTPServer:
    payload = json.dumps(projection(snapshot), allow_nan=False).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = urlsplit(self.path).path
            if path == "/api/leads":
                body, mime = payload, "application/json"
            elif path in ("/", "/style.css", "/app.js", "/logo.png"):
                asset = (
                    ASSETS
                    / {
                        "/": "index.html",
                        "/style.css": "style.css",
                        "/app.js": "app.js",
                        "/logo.png": "logo.png",
                    }[path]
                )
                body = asset.read_bytes()
                mime = {
                    ".html": "text/html",
                    ".css": "text/css",
                    ".js": "application/javascript",
                    ".png": "image/png",
                }[asset.suffix]
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args: Any) -> None:
            pass

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path.home() / ".local/share/constructionsight/command-center",
    )
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--offline", action="store_true", help="Use the last complete real capture")
    parser.add_argument("--demo", action="store_true", help="Labeled fixture preview, no network")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.demo:
            snapshot = json.loads((ASSETS / "demo.json").read_text())
        elif args.offline:
            snapshot = json.loads((args.data_dir / "active.json").read_text())
        else:
            print("Fetching official SMARTS Active facilities for both counties…", flush=True)
            with httpx.Client(timeout=60, headers={"User-Agent": USER_AGENT}) as client:
                snapshot = collect_active(client, args.data_dir)
            print(
                f"Live capture: {snapshot['totals']}; {snapshot['requests']} requests; "
                f"new records: {snapshot['new_count']}",
                flush=True,
            )
        server = make_server(snapshot, args.port)
    except (ValueError, OSError, httpx.HTTPError) as exc:
        print(f"Command Center unavailable: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"Command Center: {url}", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
