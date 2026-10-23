"""Exercise original upstream inspection through the native HTTP boundary.

Historical projection equality is distinct from verified identity or permission
to queue a source. All fixtures and database mutations are local test setup.
"""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from urllib.parse import urlencode

import httpx
import pytest
from sqlalchemy import update
from sqlalchemy.orm import Session

from constructionsight.command_center_upstream import inspect_original_upstream_records
from constructionsight.live_command_center import make_server
from constructionsight.storage.database import create_database_engine
from constructionsight.storage.movement_identity_orm import ContractorIdentityRecord
from constructionsight.storage.operator_read_store import create_operator_read_engine
from constructionsight.upstream_operator_models import UpstreamOperatorRecordKind
from constructionsight.upstream_operator_service import (
    get_upstream_operator_record,
    list_upstream_operator_records,
)
from tests.test_command_center_investigation_bridge import snapshot
from tests.test_upstream_operator_cli import _seed


def test_original_upstream_native_lists_details_filters_and_payloads_are_readonly(
    tmp_path: Path,
) -> None:
    database = tmp_path / "original.sqlite3"
    _seed(f"sqlite:///{database}")
    original = hashlib.sha256(database.read_bytes()).hexdigest()
    engine = create_operator_read_engine(database)
    server = make_server(snapshot(), 0, tmp_path / "native", operator_database=database)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False,
        ) as client, Session(engine, autoflush=False) as session:
            catalog = client.get("/api/source-upstream-records").json()
            assert catalog["mode"] == "catalog"
            assert len(catalog["record_families"]) == len(UpstreamOperatorRecordKind) == 18
            assert "records" not in catalog and "returned_count" not in catalog
            observed = 0
            for kind in UpstreamOperatorRecordKind:
                listed = client.get("/api/source-upstream-records", params={
                    "kind": kind.value, "limit": "1",
                })
                assert listed.status_code == 200, listed.text
                payload = listed.json()
                expected = list_upstream_operator_records(session, kind, limit=1)
                assert payload["records"] == [row.to_dict() for row in expected]
                assert payload["returned_count"] == len(expected)
                assert payload["possibly_truncated"] == (len(expected) == 1)
                assert payload["source_claim_only"] is True
                for flag in (
                    "network_executed", "source_database_mutated", "investigation_queued",
                    "commercial_authority_granted",
                ):
                    assert payload[flag] is False
                assert payload["read_only"] is True
                assert "total" not in payload
                for row in expected:
                    observed += 1
                    detail = client.get("/api/source-upstream-records", params={
                        "kind": kind.value, "record_id": row.record_id,
                    })
                    assert detail.status_code == 200, detail.text
                    retained = get_upstream_operator_record(session, kind, row.record_id)
                    assert retained is not None
                    assert detail.json()["record"] == retained.to_dict() == row.to_dict()
                    assert "limitations" in detail.json()["record"]["payload"]
                missing = client.get("/api/source-upstream-records", params={
                    "kind": kind.value, "record_id": "missing:exact-id",
                }).json()
                assert missing["found"] is False and missing["record"] is None
            assert observed == 7
            for params, expected_count in (
                ({"kind": "parcel", "county": "San Bernardino", "apn": "0123-456-78"}, 1),
                ({"kind": "parcel", "county": "Riverside"}, 0),
                ({"kind": "contractor", "status": "candidate"}, 1),
                ({"kind": "permit_snapshot", "source_key": "source:test"}, 1),
                ({"kind": "permit_snapshot", "source_key": "source:test' OR 1=1--"}, 0),
                ({"kind": "parcel_assurance", "status": "incomplete"}, 1),
            ):
                response = client.get("/api/source-upstream-records", params=params)
                assert response.status_code == 200, response.text
                assert response.json()["returned_count"] == expected_count
            for query in (
                "kind=all", "kind=parcel&kind=decision", "kind=parcel&status=verified",
                "kind=contractor&county=Riverside", "kind=parcel&record_id=parcel:test&limit=1",
                "kind=parcel&record_id=parcel:test&apn=other", "kind=parcel&limit=0",
                "kind=parcel&limit=1001", "kind=parcel&limit=-1", "kind=parcel&limit=1.0",
                "kind=parcel&limit=01", "kind=parcel&limit=%2B1", "kind=parcel&limit=１",
                "kind=parcel&county=", "kind=parcel&source_key=%00", "county=Riverside",
                "kind=parcel&execute=true", "kind=parcel&limit=1&limit=2", "kind=parcel&broken",
            ):
                rejected = client.get("/api/source-upstream-records?" + query)
                assert rejected.status_code == 409, (query, rejected.text)
            assert client.post("/api/source-upstream-records", json={}).status_code != 200
    finally:
        engine.dispose()
        server.shutdown()
        server.server_close()
        worker.join()
    assert hashlib.sha256(database.read_bytes()).hexdigest() == original


def test_unconfigured_upstream_inspector_never_fakes_empty_evidence(tmp_path: Path) -> None:
    result = inspect_original_upstream_records(None, query="kind=parcel")
    assert result["available"] is False and result["configured"] is False
    assert "records" not in result and "returned_count" not in result
    assert list(tmp_path.iterdir()) == []
    with pytest.raises(ValueError, match="family"):
        inspect_original_upstream_records(None, query="limit=10")
    with pytest.raises(ValueError, match="regular file"):
        inspect_original_upstream_records(tmp_path / "absent.sqlite3", query="kind=parcel")
    target = tmp_path / "not-a-database"
    target.write_bytes(b"preserve incompatible original")
    link = tmp_path / "link.sqlite3"
    link.symlink_to(target)
    with pytest.raises(ValueError, match="not a link"):
        inspect_original_upstream_records(link)
    with pytest.raises(ValueError, match="incompatible"):
        inspect_original_upstream_records(target, query="kind=parcel")
    assert target.read_bytes() == b"preserve incompatible original"


def test_original_upstream_large_or_malformed_retained_payload_is_held(tmp_path: Path) -> None:
    database = tmp_path / "original.sqlite3"
    _seed(f"sqlite:///{database}")
    engine = create_database_engine(f"sqlite:///{database}")
    try:
        for retained, error in (
            (json.dumps({"limitations": ["retained " * 260_000]}), "exceeds 2 MB"),
            ("{malformed original", "malformed"),
        ):
            with Session(engine) as session, session.begin():
                session.execute(update(ContractorIdentityRecord).values(payload_json=retained))
            original = hashlib.sha256(database.read_bytes()).hexdigest()
            with pytest.raises(ValueError, match=error):
                inspect_original_upstream_records(database, query=urlencode({
                    "kind": "contractor", "record_id": "contractor:test",
                }))
            assert hashlib.sha256(database.read_bytes()).hexdigest() == original
    finally:
        engine.dispose()
