"""An original persisted parcel reaches the common worker only via exact approval."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from constructionsight.investigation_runtime import InvestigationRuntime
from constructionsight.parcel_core_models import ParcelCoreRecord
from constructionsight.site_resolution_service import normalize_apn
from constructionsight.storage.database import create_database_engine, initialize_database
from constructionsight.storage.parcel_site_store import store_parcel_core_record
from tests.test_native_source_inspection import _native


def _parcel_database(tmp_path: Path) -> tuple[Path, ParcelCoreRecord]:
    database = tmp_path / "original.sqlite3"
    engine = create_database_engine(f"sqlite:///{database}")
    initialize_database(engine)
    parcel = ParcelCoreRecord(
        parcel_record_id="original:parcel:one",
        source_key="san-bernardino:county-gis-parcels",
        source_record_id="FEATURE-245",
        apn="123-456-789",
        normalized_apn=normalize_apn("123-456-789"),
        county="San Bernardino",
        state="CA",
        address="123 Synthetic Street",
        normalized_address="123 synthetic street",
        zoning="Industrial",
        created_at=datetime(2026, 7, 14, 18, tzinfo=UTC),
    )
    with Session(engine) as session, session.begin():
        store_parcel_core_record(session, parcel)
    engine.dispose()
    return database, parcel


def test_exact_original_parcel_replay_keeps_original_and_native_identities_separate(
    tmp_path: Path,
) -> None:
    database, parcel = _parcel_database(tmp_path)
    before = database.read_bytes()
    directory = tmp_path / "private"
    server, thread = _native(directory, operator_database=database)
    base = f"http://127.0.0.1:{server.server_port}"
    selection = {"parcel_record_id": parcel.parcel_record_id}
    try:
        with httpx.Client(base_url=base, trust_env=False) as client:
            inspected = client.get("/api/source-parcel-reconciliation", params=selection)
            assert inspected.status_code == 200, inspected.text
            state = inspected.json()
            assert state["replay_eligible"] is True
            assert state["native_state"] == "not_in_native_store"
            assert state["parcel_to_project_identity_verified"] is False
            assert state["original_source"]["record_id"] == parcel.source_record_id
            assert state["original_source"]["parcel_record_id"] == parcel.parcel_record_id
            assert database.read_bytes() == before
            assert client.get("/api/source-parcel-reconciliation?parcel_record_id=missing"
                              ).status_code == 409
            assert client.get("/api/source-parcel-reconciliation?parcel_record_id="
                              "original%3Aparcel%3Aone&x=1").status_code == 409
            payload = {
                **selection,
                "expected_source_sha256": state["original_source"]["source_sha256"],
                "expected_native_evidence_id": None,
                "action": "retain_missing",
                "review_reason": "Preserve exact reviewed source parcel evidence in common engine.",
                "caller_confirmation": True,
            }
            assert client.post("/api/source-parcel-reconciliation-queue",
                               json=payload).status_code == 403
            incorrect = client.post(
                "/api/source-parcel-reconciliation-queue",
                json={**payload, "expected_source_sha256": "0" * 64},
                headers={"Origin": base},
            )
            assert incorrect.status_code == 400
            accepted = client.post(
                "/api/source-parcel-reconciliation-queue",
                json=payload, headers={"Origin": base},
            )
            assert accepted.status_code == 200, accepted.text
            receipt = accepted.json()
            assert receipt["approval_audit_retained"] is True
            assert receipt["unverified_parcel_claim_only"] is True
            assert receipt["project_identity_verified"] is False
            assert receipt["source_entity_id"] == state["source_entity_id"]
            assert database.read_bytes() == before
            runtime = InvestigationRuntime(directory)
            try:
                report = runtime.process(max_jobs=100)
                assert report["failed_jobs"] == 0
            finally:
                runtime.close()
            after = client.get("/api/source-parcel-reconciliation", params=selection)
            assert after.status_code == 200
            assert after.json()["native_state"] == "exact_observation_already_retained"
            assert after.json()["replay_eligible"] is False
            assert after.json()["canonical_investigation_id"] is not None
            assert client.post(
                "/api/source-parcel-reconciliation-queue", json=payload,
                headers={"Origin": base},
            ).status_code == 400
            audit = client.get(
                "/api/source-reconciliation-audit", params={"job": receipt["job_id"]},
            )
            assert audit.status_code == 200, audit.text
            assert database.read_bytes() == before
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_tampered_original_parcel_index_is_rejected_without_replay(
    tmp_path: Path,
) -> None:
    from sqlalchemy import text

    database, parcel = _parcel_database(tmp_path)
    engine = create_database_engine(f"sqlite:///{database}")
    with Session(engine) as session, session.begin():
        session.execute(text(
            "UPDATE parcel_core_records SET apn='changed' "
            "WHERE parcel_record_id=:parcel_id"
        ), {"parcel_id": parcel.parcel_record_id})
    engine.dispose()
    before = database.read_bytes()
    directory = tmp_path / "private"
    server, thread = _native(directory, operator_database=database)
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False
        ) as client:
            denied = client.get("/api/source-parcel-reconciliation",
                                params={"parcel_record_id": parcel.parcel_record_id})
            assert denied.status_code == 409
            assert "index and payload disagree" in denied.text
            assert database.read_bytes() == before
            assert not (directory / "investigations.sqlite3").exists()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
