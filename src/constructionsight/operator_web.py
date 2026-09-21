"""Local, read-only HTTP application for the ConstructionSight operator GUI."""

from __future__ import annotations

import argparse
import json
from contextlib import suppress
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import cast
from urllib.parse import parse_qs, urlparse

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from constructionsight.operator_dashboard import (
    build_dashboard_snapshot,
    build_entity_neighborhood,
    build_geographic_footprint,
    build_historical_timeline,
    build_workflow_snapshot,
)
from constructionsight.operator_dashboard_models import RecordSelection
from constructionsight.operator_source_candidate import (
    SourceRecordNotFound,
    build_source_candidate_preview,
)
from constructionsight.storage.operator_read_store import create_operator_read_engine

_ASSETS = {
    "/": ("operator_ui.html", "text/html; charset=utf-8"),
    "/operator_ui.js": ("operator_ui.js", "text/javascript; charset=utf-8"),
    "/operator_ui.css": ("operator_ui.css", "text/css; charset=utf-8"),
}


@dataclass(frozen=True)
class _RequestParameters:
    """Validated HTTP query arguments; never forward arbitrary dictionaries to services."""

    kind: RecordSelection
    query: str
    county: str
    limit: int
    offset: int
    entity_key: str | None
    record_id: str | None = None


def _parameters(
    query: str, *, workflow: bool = False, footprint: bool = False,
    entity: bool = False, candidate: bool = False, timeline: bool = False
) -> _RequestParameters:
    values = parse_qs(query, keep_blank_values=True, max_num_fields=5)
    allowed = (
        {"limit", "offset"}
        if workflow
        else {"kind", "record_id"}
        if candidate
        else {"kind", "q", "county", "entity_key"}
        if timeline
        else {"kind", "county", "entity_key"}
        if entity
        else {"kind", "q", "county"}
        if footprint
        else {"kind", "q", "county", "limit", "offset"}
    )
    if set(values) - allowed or any(len(value) != 1 for value in values.values()):
        raise ValueError("unsupported or repeated query parameter")
    limit = int(values.get("limit", ["100"])[0])
    offset = int(values.get("offset", ["0"])[0])
    if not 1 <= limit <= 500 or not 0 <= offset <= 1_000_000:
        raise ValueError("invalid page bounds")
    if workflow:
        return _RequestParameters(
            kind="all", query="", county="", limit=limit, offset=offset, entity_key=None
        )
    raw_kind = values.get("kind", ["all"])[0]
    query_text = values.get("q", [""])[0]
    county = values.get("county", [""])[0]
    if raw_kind not in {"all", "ceqa", "permit"} or len(query_text) > 200:
        raise ValueError("invalid record kind or search length")
    if county not in {"", "San Bernardino", "Riverside"}:
        raise ValueError("unsupported county filter")
    record_id = values["record_id"][0] if "record_id" in values else None
    if candidate and (
        raw_kind not in {"ceqa", "permit"}
        or record_id is None or not record_id or len(record_id) > 255
        or record_id != record_id.strip()
        or any(ord(c) < 32 or ord(c) == 127 for c in record_id)
    ):
        raise ValueError("invalid exact source record selection")
    entity_key = values["entity_key"][0] if "entity_key" in values else None
    if entity and (
        entity_key is None
        or not entity_key
        or entity_key != entity_key.strip()
        or len(entity_key) > 255
    ):
        raise ValueError("invalid or missing entity key")
    if timeline and entity_key is not None and (
        not entity_key or entity_key != entity_key.strip() or len(entity_key) > 255
        or any(ord(char) < 32 or ord(char) == 127 for char in entity_key)
    ):
        raise ValueError("invalid timeline entity key")
    return _RequestParameters(
        kind=cast(RecordSelection, raw_kind),
        query=query_text,
        county=county,
        limit=limit,
        offset=offset,
        entity_key=entity_key,
        record_id=record_id,
    )


def create_handler(database_path: Path) -> type[BaseHTTPRequestHandler]:
    """Bind to an existing database in SQLite read-only mode without schema changes."""

    engine = create_operator_read_engine(database_path)

    class OperatorHandler(BaseHTTPRequestHandler):
        """Serve only same-origin, loopback reads and bundled presentation assets."""

        def do_GET(self) -> None:
            address = self.server.server_address
            if not isinstance(address, tuple):
                raise ValueError("TCP server address required")
            port = address[1]
            allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
            hosts = self.headers.get_all("Host", [])
            origins = self.headers.get_all("Origin", [])
            if (
                len(hosts) != 1
                or hosts[0] not in allowed_hosts
                or (origins and origins != [f"http://{hosts[0]}"])
                or self.headers.get("Sec-Fetch-Site") == "cross-site"
            ):
                self._send_json(
                    {"error": "Local same-origin access required."}, status=HTTPStatus.FORBIDDEN
                )
                return
            try:
                parsed = urlparse(self.path)
                if parsed.scheme or parsed.netloc or parsed.fragment:
                    raise ValueError("local request path required")
                path = parsed.path
                if path in _ASSETS:
                    name, content_type = _ASSETS[path]
                    self._send(
                        HTTPStatus.OK, content_type, Path(__file__).with_name(name).read_bytes()
                    )
                    return
                if path not in {
                    "/api/health",
                    "/api/snapshot",
                    "/api/footprint",
                    "/api/timeline",
                    "/api/entity-neighborhood",
                    "/api/candidate-preview",
                    "/api/workflows",
                }:
                    self._send_json({"error": "Not found."}, status=HTTPStatus.NOT_FOUND)
                    return
                parameters = _parameters(
                    parsed.query,
                    workflow=path == "/api/workflows",
                    footprint=path == "/api/footprint",
                    timeline=path == "/api/timeline",
                    entity=path == "/api/entity-neighborhood",
                    candidate=path == "/api/candidate-preview",
                )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            try:
                with Session(engine, autoflush=False) as session:
                    if path == "/api/health":
                        session.scalar(select(1))
                        payload: object = {
                            "status": "database_readable",
                            "read_only": True,
                            "live_collection_enabled": False,
                        }
                    elif path == "/api/workflows":
                        payload = build_workflow_snapshot(
                            session, limit=parameters.limit, offset=parameters.offset
                        )
                    elif path == "/api/candidate-preview":
                        if parameters.record_id is None or parameters.kind == "all":
                            raise ValueError("missing exact source record selection")
                        payload = build_source_candidate_preview(
                            session, kind=parameters.kind,
                            record_id=parameters.record_id,
                        ).model_dump(mode="json")
                    elif path == "/api/entity-neighborhood":
                        if parameters.entity_key is None:
                            raise ValueError("missing entity key")
                        payload = build_entity_neighborhood(
                            session,
                            entity_key=parameters.entity_key,
                            kind=parameters.kind,
                            county=parameters.county,
                        ).model_dump(mode="json")
                    elif path == "/api/timeline":
                        payload = build_historical_timeline(
                            session,
                            kind=parameters.kind,
                            query=parameters.query,
                            county=parameters.county,
                            entity_key=parameters.entity_key,
                        ).model_dump(mode="json")
                    elif path == "/api/footprint":
                        payload = build_geographic_footprint(
                            session,
                            kind=parameters.kind,
                            query=parameters.query,
                            county=parameters.county,
                        ).model_dump(mode="json")
                    else:
                        payload = build_dashboard_snapshot(
                            session,
                            kind=parameters.kind,
                            query=parameters.query,
                            county=parameters.county,
                            limit=parameters.limit,
                            offset=parameters.offset,
                        ).model_dump(mode="json")
                self._send_json(payload)
            except SourceRecordNotFound:
                self._send_json(
                    {"error": "Source record not found."}, status=HTTPStatus.NOT_FOUND
                )
            except (SQLAlchemyError, ValueError, TypeError, KeyError):
                self._send_json(
                    {
                        "error": "Stored data could not be read. "
                        "Check the database schema and records; "
                        "the operator does not create or repair the database."
                    },
                    status=HTTPStatus.SERVICE_UNAVAILABLE,
                )

        def _send_json(self, payload: object, *, status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload, sort_keys=True, allow_nan=False).encode("utf-8")
            self._send(status, "application/json; charset=utf-8", body)

        def _send(self, status: HTTPStatus, content_type: str, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", _content_security_policy())
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    return OperatorHandler


def _content_security_policy() -> str:
    return "; ".join(
        [
            "default-src 'none'",
            "script-src 'self'",
            "style-src 'self'",
            "img-src 'self' data:",
            "connect-src 'self'",
            "frame-ancestors 'none'",
            "base-uri 'none'",
            "form-action 'none'",
        ]
    )


def main() -> None:
    """Run the local-only operator application against an existing database."""

    parser = argparse.ArgumentParser(description="ConstructionSight operator GUI (read only)")
    parser.add_argument("--database", type=Path, default=Path("data/constructionsight.sqlite3"))
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    try:
        handler = create_handler(args.database)
    except (OSError, ValueError) as exc:
        parser.error(f"--database must name an existing SQLite file: {exc}")
    with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
        print(f"ConstructionSight operator GUI: http://127.0.0.1:{args.port}", flush=True)
        with suppress(KeyboardInterrupt):
            server.serve_forever()


if __name__ == "__main__":
    main()
