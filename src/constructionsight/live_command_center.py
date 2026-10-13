"""One-command, read-only localhost Command Center backed by official SMARTS rows."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import webbrowser
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qs, unquote, urlsplit
from zoneinfo import ZoneInfo

import httpx

from constructionsight.fontana_permits import fetch_candidates, retain_candidates
from constructionsight.lead_watchlist import update_watch, watchlist
from constructionsight.lead_workflow import (
    REASONS,
    STATUSES,
    begin_run,
    capture_lock,
    csv_export,
    developer_accounts,
    finish_run,
    get_feedback,
    outcome_report,
    run_history,
    save_feedback,
)
from constructionsight.security_fit import WEIGHTS_PATH, load_weights, rank_leads
from constructionsight.smarts_active import collect_active
from constructionsight.smarts_api import USER_AGENT

ASSETS = Path(__file__).parent / "command_center"


def projection(snapshot: dict[str, Any], directory: Path | None = None) -> dict[str, Any]:
    weights_path = directory / "weights.json" if directory else None
    rows = rank_leads(snapshot["rows"], weights=load_weights(weights_path))
    feedback = get_feedback(directory) if directory else {}
    permits_file = directory / "fontana-permits.json" if directory else None
    permits = json.loads(permits_file.read_text()) if permits_file and permits_file.exists() else {}
    for row in rows:
        row["feedback"] = feedback.get(row.get("source_key", ""), {"status": "New"})
        candidate = permits.get(row.get("source_key", ""))
        row["permit_candidates"] = (
            {k: v for k, v in candidate.items() if k != "raw_response"} if candidate else None
        )
    cutoff = (datetime.now(UTC) - timedelta(days=7)).isoformat()
    local_today = datetime.now(ZoneInfo("America/Los_Angeles")).date()
    for row in rows:
        first_seen = row.get("first_seen")
        row["new_today"] = bool(
            first_seen
            and datetime.fromisoformat(first_seen)
            .astimezone(ZoneInfo("America/Los_Angeles"))
            .date()
            == local_today
        )
    map_file = directory / "map.json" if directory else None
    map_settings = (
        json.loads(map_file.read_text())
        if map_file and map_file.exists()
        else {"offline_first": True, "url_template": None, "attribution": None}
    )
    template = map_settings.get("url_template")
    if template is not None and (
        not isinstance(template, str)
        or not template.startswith("https://")
        or any("{" + key + "}" not in template for key in ("z", "x", "y"))
    ):
        raise ValueError("Tile template must use HTTPS and contain {z}, {x}, {y}")
    runs = run_history(directory) if directory else []
    latest = runs[0] if runs else None
    return {
        "rows": rows,
        "warning": ("Capture failed; showing last good data. " + str(latest["error"]))
        if latest and latest["outcome"] == "error"
        else None,
        "map_settings": map_settings,
        "statuses": STATUSES,
        "reasons": REASONS,
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


def make_server(
    snapshot: dict[str, Any], port: int, directory: Path | None = None
) -> ThreadingHTTPServer:
    if directory:
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not (directory / "map.json").exists():
            (directory / "map.json").write_text(
                json.dumps(
                    {"offline_first": True, "url_template": None, "attribution": None}, indent=2
                )
            )
        if not (directory / "weights.json").exists():
            shutil.copyfile(WEIGHTS_PATH, directory / "weights.json")

    def current() -> dict[str, Any]:
        active = directory / "active.json" if directory else None
        current_snapshot = (
            json.loads(active.read_text()) if active and active.exists() else snapshot
        )
        return projection(current_snapshot, directory)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            port = cast(ThreadingHTTPServer, self.server).server_port
            if self.headers.get("Host") not in (f"127.0.0.1:{port}", f"localhost:{port}"):
                self.send_error(403)
                return
            path = urlsplit(self.path).path
            if path == "/api/leads":
                body, mime = json.dumps(current(), allow_nan=False).encode(), "application/json"
            elif path == "/api/terms":
                conditions = [
                    {
                        "source": "California SMARTS",
                        "summary": (
                            "The publisher labels this dataset public with No Restrictions on "
                            "Public Use. The State's general conditions describe information as "
                            "generally public domain, except third-party copyrighted material. No "
                            "accuracy, completeness or suitability warranty is supplied. "
                            "Regulatory Active status is not proof of physical construction."
                        ),
                        "url": "https://publish.data.ca.gov/dataset/stormwater-regulatory-including-enforcement-actions-information-and-water-quality-results",
                        "conditions_url": "https://handbook.data.ca.gov/conditions-of-use/",
                    },
                    {
                        "source": "Fontana historical property records",
                        "summary": (
                            "The city links an address-search service for researching whether a "
                            "property has permits. Its website copyright notice reserves content "
                            "rights. The observed pages do not establish a bulk commercial "
                            "API-use license. This pilot retains bounded exact-address historical "
                            "candidates only; it does not verify current project scope or fill "
                            "missing dossier facts. Current Accela access returned HTTP 403; no "
                            "bypass is attempted."
                        ),
                        "url": "https://fontanaca.gov/3123/Historical-Property-Permit-Information",
                        "conditions_url": "https://fontanaca.gov/site/copyright",
                    },
                    {
                        "source": "Map setting",
                        "summary": (
                            "Offline-first is the default; no public tile host is embedded. To "
                            "use a provider you are authorized to use, set url_template and "
                            "attribution in the local map.json. A template must use HTTPS and "
                            "{z}, {x}, {y}. Provider licensing is separate from SMARTS and "
                            "city-record access."
                        ),
                        "url": None,
                        "conditions_url": None,
                    },
                ]
                body, mime = json.dumps(conditions).encode(), "application/json"
            elif path == "/api/runs":
                body, mime = (
                    json.dumps(run_history(directory) if directory else []).encode(),
                    "application/json",
                )
            elif path == "/api/watchlist":
                body, mime = (
                    json.dumps(
                        watchlist(directory, current()["rows"]) if directory else []
                    ).encode(),
                    "application/json",
                )
            elif path == "/api/developers":
                body, mime = (
                    json.dumps(developer_accounts(current()["rows"])).encode(),
                    "application/json",
                )
            elif path == "/api/outcomes":
                rows = current()["rows"]
                if directory:
                    present = {r["source_key"] for r in rows}
                    rows += [
                        {
                            "source_key": k,
                            "security_fit": v["score_at_update"],
                            "project_type": v["project_type_at_update"],
                            "feedback": v,
                        }
                        for k, v in get_feedback(directory).items()
                        if k not in present
                    ]
                body, mime = json.dumps(outcome_report(rows)).encode(), "application/json"
            elif path == "/api/export.csv":
                query = parse_qs(urlsplit(self.path).query)
                rows = current()["rows"]
                if query.get("new_today") == ["1"]:
                    rows = [r for r in rows if r["new_today"]]
                if query.get("new_since") == ["1"]:
                    rows = [r for r in rows if r["is_new"]]
                for parameter, field in (
                    ("county", "SITE_COUNTY"),
                    ("type", "project_type"),
                    ("band", "fit_band"),
                ):
                    if query.get(parameter):
                        rows = [r for r in rows if r.get(field) == query[parameter][0]]
                if query.get("search"):
                    term = query["search"][0].casefold()
                    rows = [
                        r
                        for r in rows
                        if term
                        in " ".join(
                            str(r.get(k) or "")
                            for k in ("SITE_NAME", "DEVELOPER_NAME", "SITE_CITY", "WDID", "APP_ID")
                        ).casefold()
                    ]
                if query.get("status"):
                    rows = [r for r in rows if r["feedback"]["status"] == query["status"][0]]
                body, mime = csv_export(rows), "text/csv; charset=utf-8"
            elif path in (
                "/",
                "/style.css",
                "/app.js",
                "/logo.png",
                "/design_tokens.json",
                "/icons.js",
            ):
                asset = (
                    ASSETS
                    / {
                        "/": "index.html",
                        "/style.css": "style.css",
                        "/app.js": "app.js",
                        "/logo.png": "logo.png",
                        "/design_tokens.json": "design_tokens.json",
                        "/icons.js": "icons.js",
                    }[path]
                )
                body = asset.read_bytes()
                mime = {
                    ".html": "text/html",
                    ".css": "text/css",
                    ".js": "application/javascript",
                    ".png": "image/png",
                    ".json": "application/json",
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

        def do_POST(self) -> None:
            path = urlsplit(self.path).path
            is_watch = path.startswith("/api/watchlist/")
            if not directory or not (is_watch or path.startswith("/api/feedback/")):
                self.send_error(501)
                return
            host = self.headers.get("Host", "")
            port = cast(ThreadingHTTPServer, self.server).server_port
            if (
                host not in (f"127.0.0.1:{port}", f"localhost:{port}")
                or self.headers.get("Origin") != f"http://{host}"
            ):
                self.send_error(403)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 65536:
                    raise ValueError("Invalid feedback size")
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError("Feedback must be an object")
                prefix = "/api/watchlist/" if is_watch else "/api/feedback/"
                key = unquote(path[len(prefix) :])
                lead = next((r for r in current()["rows"] if r["source_key"] == key), None)
                if lead is None and not is_watch:
                    raise ValueError("Unknown lead")
                if is_watch:
                    result = update_watch(directory, key, payload, lead)
                else:
                    assert lead is not None
                    result = save_feedback(directory, key, payload, lead)
                body = json.dumps(result).encode()
            except (ValueError, KeyError) as exc:
                self.send_error(400, str(exc))
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
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
    parser.add_argument(
        "--capture-only", action="store_true", help="Scheduled capture without a server"
    )
    parser.add_argument(
        "--fontana-source-key",
        help="Explicit bounded historical address research for one current SMARTS lead",
    )
    args = parser.parse_args(argv)
    try:
        if args.demo:
            snapshot = json.loads((ASSETS / "demo.json").read_text())
        elif args.offline:
            snapshot = json.loads((args.data_dir / "active.json").read_text())
        else:
            print("Fetching official SMARTS Active facilities for both counties…", flush=True)
            with capture_lock(args.data_dir):
                run_id = begin_run(args.data_dir)
                try:
                    with httpx.Client(timeout=60, headers={"User-Agent": USER_AGENT}) as client:
                        snapshot = collect_active(client, args.data_dir)
                    finish_run(args.data_dir, run_id, snapshot)
                    print(
                        f"Live capture: {snapshot['totals']}; {snapshot['requests']} requests; "
                        f"new records: {snapshot['new_count']}",
                        flush=True,
                    )
                except (ValueError, OSError, httpx.HTTPError) as exc:
                    finish_run(args.data_dir, run_id, None, f"{type(exc).__name__}: {exc}")
                    if args.capture_only or not (args.data_dir / "active.json").exists():
                        raise
                    snapshot = json.loads((args.data_dir / "active.json").read_text())
                    print(
                        "Capture failed; opening the last good capture with a warning.", flush=True
                    )
        if args.fontana_source_key:
            lead = next(
                (r for r in snapshot["rows"] if r["source_key"] == args.fontana_source_key), None
            )
            if lead is None:
                raise ValueError("Unknown SMARTS source key")
            with httpx.Client(timeout=30, headers={"User-Agent": USER_AGENT}) as client:
                candidates = fetch_candidates(client, lead)
            retain_candidates(args.data_dir, candidates)
            print(
                f"Fontana: {candidates['returned_records']} returned, "
                f"{len(candidates['candidates'])} exact historical address candidates; "
                "current project match unverified; no dossier facts filled."
            )
        if args.capture_only:
            return 0
        server = make_server(snapshot, args.port, None if args.demo else args.data_dir)
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
