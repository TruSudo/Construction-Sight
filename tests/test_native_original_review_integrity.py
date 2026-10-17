"""Phase 8 historical review integrity at both read-only native lineage endpoints."""

from __future__ import annotations

import hashlib
import threading
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from constructionsight.command_center_legacy_review import verified_original_review_package
from constructionsight.lead_review_models import LeadReviewPackage
from constructionsight.lead_workflow_service import create_lead_workflow
from constructionsight.live_command_center import make_server
from constructionsight.operator_source_candidate import build_source_candidate_preview
from constructionsight.storage.database import create_database_engine, initialize_database
from constructionsight.storage.domain_store import CeqaStore
from constructionsight.storage.lead_workflow_orm import LeadReviewPackageRecord
from constructionsight.storage.lead_workflow_store import (
    store_lead_review_package,
    store_lead_workflow_record,
)
from tests.test_bid_proposal_service import _package
from tests.test_command_center_investigation_bridge import snapshot
from tests.test_operator_dashboard import _record


@pytest.mark.parametrize(
    ("corruption", "error"),
    [
        ("status", "index and payload disagree"),
        ("score", "index and payload disagree"),
        ("created", "index and payload disagree"),
        ("candidate", "index and payload disagree"),
        ("payload", "payload is invalid"),
        ("missing", "is missing"),
    ],
)
def test_native_historical_lineage_fails_closed_on_corrupt_original_review(
    tmp_path: Path, corruption: str, error: str,
) -> None:
    original_db = tmp_path / "original.sqlite3"
    engine = create_database_engine(f"sqlite:///{original_db}")
    initialize_database(engine)
    record_id = "phase8:review-integrity"
    with Session(engine) as session, session.begin():
        CeqaStore(session).upsert(_record(record_id, title="Synthetic review integrity"))
    with Session(engine) as session:
        key = build_source_candidate_preview(
            session, kind="ceqa", record_id=record_id
        ).candidate_key
    package: LeadReviewPackage = _package().model_copy(update={
        "package_id": "lead-review:phase8:review-integrity",
        "base_candidate_id": key,
    })
    workflow = create_lead_workflow(package=package)
    with Session(engine) as session, session.begin():
        store_lead_review_package(session, package)
        store_lead_workflow_record(session, workflow)
    with Session(engine) as session:
        assert verified_original_review_package(
            session, package_id=package.package_id, candidate_key=key
        ).status == package.status
        with pytest.raises(ValueError, match="source identity disagrees"):
            verified_original_review_package(
                session, package_id=package.package_id, candidate_key="another:source"
            )

    with Session(engine) as session, session.begin():
        row = session.scalar(
            select(LeadReviewPackageRecord).where(
                LeadReviewPackageRecord.package_id == package.package_id
            )
        )
        assert row is not None
        if corruption == "missing":
            session.delete(row)
        else:
            values = {
                "status": {"status": "hold"},
                "score": {"lead_score": -1},
                "created": {"observed_created_at": "2000-01-01T00:00:00+00:00"},
                "candidate": {"base_candidate_id": "another:source"},
                "payload": {"payload_json": "not-json"},
            }[corruption]
            session.execute(
                update(LeadReviewPackageRecord)
                .where(LeadReviewPackageRecord.id == row.id)
                .values(**values)
            )
    with Session(engine), pytest.raises(ValueError, match=error):
        with Session(engine) as session:
            verified_original_review_package(
                session, package_id=package.package_id, candidate_key=key
            )
    engine.dispose()
    digest_before = hashlib.sha256(original_db.read_bytes()).hexdigest()
    server = make_server(
        snapshot(), 0, tmp_path / "native", operator_database=original_db
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False
        ) as client:
            common = {"kind": "ceqa", "record_id": record_id}
            lineage = client.get("/api/source-commercial-lineage", params=common)
            attribution = client.get("/api/original-workflow-attribution", params={
                **common, "workflow": workflow.workflow_id,
            })
            assert lineage.status_code == 409, lineage.text
            assert attribution.status_code == 409, attribution.text
            assert "matching_workflows" not in lineage.text
            assert "historical_result" not in attribution.text
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    assert hashlib.sha256(original_db.read_bytes()).hexdigest() == digest_before
