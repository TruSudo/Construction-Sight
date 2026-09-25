"""Read-only CEQAnet ingestion status exposed through the local operator."""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from sqlalchemy.orm import Session

from constructionsight.ceqa_models import CeqaRecord
from constructionsight.ceqanet_capture_queue import build_reviewed_ceqanet_capture_queue
from constructionsight.operator_web import create_handler
from constructionsight.provenance import Provenance
from constructionsight.storage.database import create_database_engine, initialize_database
from constructionsight.storage.domain_store import CeqaStore


def _listing() -> dict[str, object]:
    html = (
        '<div class="search-result">'
        '<a href="/Project/2026030377">Cabazon Infrastructure Plan</a>'
        '<span>SCH Number</span><span>2026030377</span>'
        '<span>County</span><span>Riverside</span>'
        '</div>'
    )
    return {
        "metadata": {
            "schema_version": "ceqanet_listing_execution.v2",
            "allowed": True,
            "planned_request_count": 1,
            "executed_request_count": 1,
            "successful_response_count": 1,
            "failed_response_count": 0,
            "plan_id": "operator-ingestion-status-test",
            "access": {"decision": "allowed"},
            "authorization": {"decision_id": "operator-ingestion-status-auth"},
        },
        "snapshots": [
            {
                "page_number": 1,
                "method": "GET",
                "request_url": "https://ceqanet.lci.ca.gov/Search?County=Riverside",
                "final_url": "https://ceqanet.lci.ca.gov/Search?County=Riverside",
                "status_code": 200,
                "content_type": "text/html; charset=utf-8",
                "body_text": html,
                "body_length": len(html),
                "body_truncated": False,
                "executed": True,
                "reachable": True,
                "error": None,
                "failure_kind": "none",
            }
        ],
    }


def _write_artifacts(tmp_path: Path) -> tuple[Path, Path]:
    listing = _listing()
    listing_raw = json.dumps(listing, sort_keys=True).encode("utf-8")
    queue = build_reviewed_ceqanet_capture_queue(listing, original_bytes=listing_raw)
    listing_path = tmp_path / "listing.json"
    queue_path = tmp_path / "queue.json"
    listing_path.write_bytes(listing_raw)
    queue_path.write_text(
        json.dumps(queue, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return listing_path, queue_path


@contextmanager
def _server(
    database: Path,
    *,
    listing: Path | None = None,
    queue: Path | None = None,
):
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        create_handler(
            database,
            ceqanet_listing_evidence=listing,
            ceqanet_queue_evidence=queue,
        ),
    )
    thread = Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": 0.01},
        daemon=True,
    )
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _get(port: int, path: str) -> tuple[int, bytes]:
    connection = HTTPConnection("127.0.0.1", port, timeout=3)
    connection.request("GET", path, headers={"Host": f"127.0.0.1:{port}"})
    response = connection.getresponse()
    body = response.read()
    status = response.status
    connection.close()
    return status, body


def _reviewed_record() -> CeqaRecord:
    return CeqaRecord(
        ceqa_key="ceqanet_csv:2026030377:operator-status-test",
        title="Cabazon Infrastructure Plan",
        county="Riverside",
        state_clearinghouse_number="2026030377",
        provenance=[
            Provenance(
                source_name="Synthetic reviewed CEQAnet CSV fixture",
                adapter_family="ceqanet_csv_reviewed",
                evidence_text="Fixture only",
            )
        ],
    )


def test_operator_ingestion_status_tracks_exact_queue_without_writes(tmp_path: Path) -> None:
    database = tmp_path / "operator.sqlite3"
    engine = create_database_engine(f"sqlite:///{database}")
    initialize_database(engine)
    listing, queue = _write_artifacts(tmp_path)
    before = hashlib.sha256(database.read_bytes()).hexdigest()

    with _server(database, listing=listing, queue=queue) as port:
        status, raw = _get(port, "/api/ingestion-inbox")
        assert status == 200
        pending = json.loads(raw)
        assert pending["configured"] is True
        assert pending["read_only"] is True
        assert pending["network_executed"] is False
        assert pending["persistence_mutated"] is False
        assert pending["commercial_leads_created"] is False
        assert pending["candidate_count"] == 1
        assert pending["pending_capture_count"] == 1
        assert pending["persisted_candidate_count"] == 0
        assert pending["conflict_candidate_count"] == 0
        assert pending["county_unavailable_candidate_count"] == 0
        assert pending["next_pending_sch"] == "2026030377"
        assert pending["candidates"][0]["state"] == "pending_capture"
        assert _get(port, "/api/ingestion-inbox?kind=ceqa")[0] == 400
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before

    with Session(engine) as session, session.begin():
        CeqaStore(session).upsert(_reviewed_record())
    engine.dispose()
    after_write = hashlib.sha256(database.read_bytes()).hexdigest()

    with _server(database, listing=listing, queue=queue) as port:
        status, raw = _get(port, "/api/ingestion-inbox")
        assert status == 200
        persisted = json.loads(raw)
        assert persisted["pending_capture_count"] == 0
        assert persisted["persisted_candidate_count"] == 1
        assert persisted["next_pending_sch"] is None
        assert persisted["candidates"][0]["state"] == "persisted_source_claim_match"
        assert persisted["candidates"][0]["persisted_record_count"] == 1
        assert persisted["candidates"][0]["persisted_known_counties"] == ["Riverside"]
    assert hashlib.sha256(database.read_bytes()).hexdigest() == after_write


def test_operator_ingestion_status_is_safe_when_not_configured(tmp_path: Path) -> None:
    database = tmp_path / "operator.sqlite3"
    engine = create_database_engine(f"sqlite:///{database}")
    initialize_database(engine)
    engine.dispose()
    before = hashlib.sha256(database.read_bytes()).hexdigest()

    with _server(database) as port:
        status, raw = _get(port, "/api/ingestion-inbox")
        assert status == 200
        payload = json.loads(raw)
        assert payload["configured"] is False
        assert payload["candidate_count"] == 0
        assert payload["pending_capture_count"] == 0
        assert payload["read_only"] is True
        assert payload["network_executed"] is False
        assert payload["persistence_mutated"] is False
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before


def test_operator_rejects_half_configured_ingestion_evidence(tmp_path: Path) -> None:
    database = tmp_path / "operator.sqlite3"
    engine = create_database_engine(f"sqlite:///{database}")
    initialize_database(engine)
    engine.dispose()
    listing, _ = _write_artifacts(tmp_path)

    try:
        create_handler(database, ceqanet_listing_evidence=listing)
    except ValueError as exc:
        assert "configured together" in str(exc)
    else:
        raise AssertionError("half-configured ingestion evidence must fail closed")
