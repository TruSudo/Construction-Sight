"""Original commercial no-send/no-submit service parity in native Command Center."""

from __future__ import annotations

import hashlib
import threading
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from constructionsight.lead_workflow_service import create_lead_workflow
from constructionsight.live_command_center import make_server
from constructionsight.storage.database import create_database_engine, initialize_database
from constructionsight.storage.lead_workflow_store import (
    store_lead_review_package,
    store_lead_workflow_record,
)
from tests.test_bid_proposal_service import _package
from tests.test_command_center_investigation_bridge import snapshot


def test_original_governed_preview_chain_stays_read_only_and_manual(
    tmp_path: Path,
) -> None:
    database = tmp_path / "original.sqlite3"
    engine = create_database_engine(f"sqlite:///{database}")
    initialize_database(engine)
    package = _package()
    workflow = create_lead_workflow(package=package)
    with Session(engine) as session, session.begin():
        store_lead_review_package(session, package)
        store_lead_workflow_record(session, workflow)
    engine.dispose()
    digest = hashlib.sha256(database.read_bytes()).hexdigest()
    server = make_server(
        snapshot(), 0, tmp_path / "native", operator_database=database
    )
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        origin = {"Origin": base}
        with httpx.Client(base_url=base, trust_env=False) as client:
            outreach = {
                "workflow_id": workflow.workflow_id,
                "expected_current_status": "ready",
                "channel": "email",
                "destination": "estimating@example-contractor.test",
                "business_role": "estimating department",
                "source_name": "official business contact",
                "source_reference": "https://example-contractor.test/contact",
                "contact_review_basis": "Reviewed exact business page.",
                "subject": "Construction site security",
                "body": "Manual draft for human review only.",
            }
            def run(operation: str, data: dict[str, object]) -> httpx.Response:
                return client.post(
                    "/api/source-commercial-preview",
                    json={"operation": operation, "data": data},
                    headers=origin,
                )

            assert run("outreach", outreach).status_code == 200
            result = run("outreach", outreach).json()
            assert result["outreach_sent"] is False
            assert result["bid_submitted"] is False
            assert result["preview"]["external_send_authorized"] is False
            assert result["preview"]["requires_human_approval"] is True
            request_data: dict[str, object] = {
                "workflow_id": workflow.workflow_id,
                "expected_current_status": "ready",
                "request_channel": "email",
                "requester_business_name": "Synthetic Contractor LLC",
                "requester_business_role": "estimating department",
                "request_source_name": "retained business email",
                "request_source_reference": "message:synthetic:request",
                "request_review_basis": "Reviewed explicit security pricing request.",
                "request_observed_at": "2026-10-08T10:00:00+00:00",
                "request_text": "Please provide pricing for night guard coverage.",
                "scope_summary": "Night guard at identified construction site.",
            }
            requested = run("bid_request", request_data)
            assert requested.status_code == 200, requested.text
            evidence = requested.json()["preview"]
            assert evidence["pricing_authorized"] is False
            assert evidence["bid_submission_authorized"] is False
            priced = run("pricing", {
                "request_evidence": evidence,
                "currency_code": "USD",
                "line_items": [{
                    "line_key": "night-guard",
                    "description": "Night guard coverage",
                    "pricing_basis": "Manually reviewed amount",
                    "amount": "125.50",
                }],
                "assumptions": ["Synthetic review only."],
                "exclusions": ["No tax treatment implied."],
                "validity_note": "Human commercial approval required.",
            })
            assert priced.status_code == 200, priced.text
            preview = priced.json()["preview"]
            assert preview["subtotal_minor"] == 12550
            assert preview["bid_submission_authorized"] is False
            proposal = run("proposal", {
                "request_evidence": evidence,
                "pricing_preview": preview,
                "proposal_title": "Internal construction security draft",
                "cover_note": "Internal review; not released.",
                "additional_terms": ["Subject to signed approval."],
            })
            assert proposal.status_code == 200, proposal.text
            proposal_data = proposal.json()["preview"]
            assert proposal_data["bid_submission_authorized"] is False
            assert proposal_data["commercial_terms_authorized"] is False
            assert proposal.json()["native_commercial_authority_created"] is False
            assert client.post(
                "/api/source-commercial-preview",
                json={"operation": "outreach", "data": outreach},
            ).status_code == 403
            assert client.post(
                "/api/source-commercial-preview",
                json={"operation": "outreach", "data": outreach},
                headers={"Origin": "https://malicious.example"},
            ).status_code == 403
            assert run("outreach", {**outreach, "extra": "send"}).status_code == 400
            assert run("outreach", {**outreach, "expected_current_status": "active"}
                      ).status_code == 400
            assert run("outreach", {**outreach, "workflow_id": "absent"}
                      ).status_code == 400
            assert run("pricing", {
                "request_evidence": evidence,
                "currency_code": "USD",
                "line_items": [{
                    "line_key": "night-guard", "description": "Coverage",
                    "pricing_basis": "Manual", "amount": "125.501",
                }],
                "assumptions": [], "exclusions": [],
                "validity_note": "Internal",
            }).status_code == 400
            assert client.post(
                "/api/source-commercial-preview?unexpected=yes",
                json={"operation": "outreach", "data": outreach},
                headers=origin,
            ).status_code == 400
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
    assert hashlib.sha256(database.read_bytes()).hexdigest() == digest
