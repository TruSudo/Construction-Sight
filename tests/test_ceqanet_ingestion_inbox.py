"""Governed CEQAnet discovery-inbox reconciliation regressions."""

from __future__ import annotations

import json
from contextlib import contextmanager
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from sqlalchemy.orm import Session

from constructionsight.ceqa_models import CeqaRecord
from constructionsight.ceqanet_capture_queue import build_reviewed_ceqanet_capture_queue
from constructionsight.ceqanet_ingestion_inbox import build_ceqanet_ingestion_inbox
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
            "plan_id": "operator-inbox-test",
            "access": {"decision": "allowed"},
            "authorization": {"decision_id": "operator-inbox-test-auth"},
        },
        "snapshots": [{
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
        }],
    }


def _artifacts() -> tuple[dict[str, object], bytes, dict[str, object], bytes]:
    listing = _listing()
    listing_bytes = json.dumps(listing, sort_keys=True).encode("utf-8")
    queue = build_reviewed_ceqanet_capture_queue(listing, original_bytes=listing_bytes)
    queue_bytes = (json.dumps(queue, sort_keys=True, indent=2) + "\n").encode("utf-8")
    return listing, listing_bytes, queue, queue_bytes


def _reviewed_record(*, county: str = "Riverside") -> CeqaRecord:
    return CeqaRecord(
        ceqa_key="ceqanet_csv:2026030377:test",
        title="Cabazon Infrastructure Plan",
        county=county,
        state_clearinghouse_number="2026030377",
        provenance=[
            Provenance(
                source_name="Synthetic reviewed CEQAnet CSV fixture",
                adapter_family="ceqanet_csv_reviewed",
                evidence_text="Fixture only",
            )
        ],
    )


def test_ingestion_inbox_transitions_from_pending_to_persisted_match(tmp_path: Path) -> None:
    database = tmp_path / "operator.sqlite3"
    engine = create_database_engine(f"sqlite:///{database}")
    initialize_database(engine)
    listing, listing_bytes, queue, queue_bytes = _artifacts()

    with Session(engine) as session:
        pending = build_ceqanet_ingestion_inbox(
            session,
            listing_payload=listing,
            listing_bytes=listing_bytes,
            queue_payload=queue,
            queue_bytes=queue_bytes,
        )
    assert pending.candidate_count == 1
    assert pending.pending_capture_count == 1
    assert pending.persisted_candidate_count == 0
    assert pending.conflict_candidate_count == 0
    assert pending.next_pending_sch == "2026030377"
    assert pending.candidates[0].state == "pending_capture"

    with Session(engine) as session, session.begin():
        CeqaStore(session).upsert(_reviewed_record())
    with Session(engine) as session:
        persisted = build_ceqanet_ingestion_inbox(
            session,
            listing_payload=listing,
            listing_bytes=listing_bytes,
            queue_payload=queue,
            queue_bytes=queue_bytes,
        )
    assert persisted.pending_capture_count == 0
    assert persisted.persisted_candidate_count == 1
    assert persisted.conflict_candidate_count == 0
    assert persisted.next_pending_sch is None
    assert persisted.candidates[0].state == "persisted_source_claim_match"
    assert persisted.candidates[0].persisted_known_counties == ["Riverside"]
    engine.dispose()


def test_ingestion_inbox_rejects_queue_semantic_tampering(tmp_path: Path) -> None:
    database = tmp_path / "operator.sqlite3"
    engine = create_database_engine(f"sqlite:///{database}")
    initialize_database(engine)
    listing, listing_bytes, queue, queue_bytes = _artifacts()
    queue["candidates"][0]["source_claimed_title"] = "tampered"
    with Session(engine) as session:
        try:
            build_ceqanet_ingestion_inbox(
                session,
                listing_payload=listing,
                listing_bytes=listing_bytes,
                queue_payload=queue,
                queue_bytes=queue_bytes,
            )
        except ValueError as exc:
            assert "fresh derivation" in str(exc)
        else:
            raise AssertionError("tampered queue must fail closed")
    engine.dispose()


@contextmanager
def _server(path: Path, listing: Path | None = None, queue: Path | None = None):
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        create_handler(
            path,
            ceqanet_listing_evidence=listing,
            ceqanet_queue_evidence=queue,
        ),
    )
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
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


def test_operator_exposes_configured_read_only_ingestion_inbox(tmp_path: Path) -> None:
    database = tmp_path / "operator.sqlite3"
    engine = create_database_engine(f"sqlite:///{database}")
    initialize_database(engine)
    engine.dispose()
    listing, listing_bytes, queue, queue_bytes = _artifacts()
    listing_path = tmp_path / "listing.json"
    queue_path = tmp_path / "queue.json"
    listing_path.write_bytes(listing_bytes)
    queue_path.write_bytes(queue_bytes)

    with _server(database, listing_path, queue_path) as port:
        status, body = _get(port, "/api/ingestion-inbox")
        assert status == 200
        payload = json.loads(body)
        assert payload["configured"] is True
        assert payload["read_only"] is True
        assert payload["network_executed"] is False
        assert payload["persistence_mutated"] is False
        assert payload["pending_capture_count"] == 1
        assert payload["next_pending_sch"] == "2026030377"
        assert _get(port, "/api/ingestion-inbox?kind=ceqa")[0] == 400

    with _server(database) as port:
        status, body = _get(port, "/api/ingestion-inbox")
        assert status == 200
        payload = json.loads(body)
        assert payload["configured"] is False
        assert payload["candidate_count"] == 0
