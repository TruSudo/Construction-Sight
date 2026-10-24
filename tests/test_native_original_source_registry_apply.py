"""Exact original registry status apply requires review and locked persistence.

Offline synthetic evidence only; no network access or commercial effect.
"""

from __future__ import annotations

import hashlib
import threading
from pathlib import Path

import httpx
import pytest
from sqlalchemy.orm import Session

from constructionsight.live_command_center import make_server
from constructionsight.models import PublicSource
from constructionsight.operator_services.source_registry_persistence_service import (
    persist_authorized_source_registry_records,
)
from constructionsight.storage.database import create_database_engine, initialize_database
from constructionsight.storage.source_registry import SourceRegistryStore
from tests.test_command_center_investigation_bridge import snapshot
from tests.test_operator_source_registry import _source


def _registry_fixture(tmp_path: Path, name: str) -> tuple[Path, PublicSource]:
    database = tmp_path / "original.sqlite3"
    engine = create_database_engine(f"sqlite:///{database}")
    initialize_database(engine)
    source = _source(name, county="Riverside", verification_status="unverified")
    other = _source(
        "Unrelated original registry source", verification_status="failed",
        public_url="https://example.invalid/unrelated/",
    )
    with Session(engine) as session, session.begin():
        registry = SourceRegistryStore(session)
        registry.upsert_source(source)
        registry.upsert_source(other)
    engine.dispose()
    database.chmod(0o600)
    return database, source


def _review_input(source: PublicSource, preview: dict) -> dict:
    return {
        "source_name": source.source_name,
        "public_url": str(source.public_url),
        "expected_source_sha256": preview["expected_source_sha256"],
        "review_reason": "I inspected the synthetic original source evidence.",
        "caller_confirmation": True,
        "observation": {
            "source_key": preview["source_key"],
            "source_name": source.source_name,
            "public_entry_observed": None,
            "query_behavior_observed": None,
            "result_list_observed": None,
            "detail_page_observed": True,
            "access_barrier_observed": None,
            "terms_review_observed": None,
            "notes": "Only a synthetic detail-page observation.",
            "evidence_refs": ["manual:test:registry-status-apply"],
        },
    }


def test_exact_native_original_registry_apply_is_governed_and_source_only(
    tmp_path: Path,
) -> None:
    original, source = _registry_fixture(tmp_path, "Synthetic governed original status")
    private = tmp_path / "private"
    server = make_server(snapshot(), 0, private, operator_database=original)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host = f"http://127.0.0.1:{server.server_port}"
        headers = {"Origin": host}
        params = {"source_name": source.source_name, "public_url": str(source.public_url)}
        with httpx.Client(base_url=host, trust_env=False) as client:
            preview_response = client.get("/api/source-checklist-preview", params=params)
            assert preview_response.status_code == 200, preview_response.text
            reviewed_payload = _review_input(source, preview_response.json())
            before = hashlib.sha256(original.read_bytes()).hexdigest()
            review_response = client.post(
                "/api/source-checklist-review", json=reviewed_payload, headers=headers,
            )
            assert review_response.status_code == 200, review_response.text
            reviewed = review_response.json()
            assert hashlib.sha256(original.read_bytes()).hexdigest() == before
            plan = reviewed["original_registry_update_plan"]
            assert plan["update_count"] == 1
            assert plan["rows"][0]["proposed_verification_status"] == "partial"
            approved_payload = {
                **reviewed_payload,
                "expected_plan_digest": plan["plan_digest"],
                "apply_reason": "Approve one exact synthetic source status change.",
                "apply_confirmation": True,
            }
            for bad in (
                {**approved_payload, "apply_confirmation": False},
                {**approved_payload, "expected_plan_digest": "f" * 64},
                {**approved_payload, "extra_field": "unreviewed"},
                {**approved_payload, "observation": {
                    **reviewed_payload["observation"], "source_key": "substituted",
                }},
                {**approved_payload, "observation": {
                    **reviewed_payload["observation"], "evidence_refs": [],
                }},
            ):
                rejected = client.post(
                    "/api/source-registry-reviewed-apply", json=bad, headers=headers,
                )
                assert rejected.status_code == 400, rejected.text
            assert client.post(
                "/api/source-registry-reviewed-apply", json=approved_payload,
            ).status_code == 403
            assert client.post(
                "/api/source-registry-reviewed-apply", json=approved_payload,
                headers={"Origin": "https://foreign.invalid"},
            ).status_code == 403
            assert client.post(
                "/api/source-registry-reviewed-apply?extra=1",
                json=approved_payload, headers=headers,
            ).status_code == 400
            assert hashlib.sha256(original.read_bytes()).hexdigest() == before

            response = client.post(
                "/api/source-registry-reviewed-apply",
                json=approved_payload, headers=headers,
            )
            assert response.status_code == 200, response.text
            applied = response.json()
            assert applied["resulting_verification_status"] == "partial"
            assert applied["original_registry_mutated"] is True
            assert applied["network_executed"] is False
            assert applied["live_collection_authorized"] is False
            assert applied["commercial_authority_granted"] is False
            assert applied["independent_source_verification_established"] is False
            assert applied["original_registry_apply_report"]["applied_count"] == 1
            assert applied["original_registry_persistence_report"]["processed_count"] == 1
            assert applied["apply_authorization"]["action"] == (
                "apply-source-registry-update-plan"
            )
            assert applied["persistence_authorization"]["action"] == (
                "persist-source-registry-records"
            )
            engine = create_database_engine(f"sqlite:///{original}")
            try:
                with Session(engine) as session:
                    stored = SourceRegistryStore(session)
                    updated = stored.get_by_identity(source.source_name, str(source.public_url))
                    assert updated is not None
                    assert updated.verification_status.value == "partial"
                    assert updated.model_dump(mode="json") == {
                        **source.model_dump(mode="json"),
                        "verification_status": "partial",
                    }
                    other = stored.get_by_identity(
                        "Unrelated original registry source",
                        "https://example.invalid/unrelated/",
                    )
                    assert other is not None
                    assert other.verification_status.value == "failed"
            finally:
                engine.dispose()
            repeated = client.post(
                "/api/source-registry-reviewed-apply",
                json=approved_payload, headers=headers,
            )
            assert repeated.status_code == 400, repeated.text
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_original_registry_apply_rejects_stale_source_and_locked_substitution(
    tmp_path: Path,
) -> None:
    original, source = _registry_fixture(tmp_path, "Synthetic stale registry source")
    server = make_server(snapshot(), 0, tmp_path / "private", operator_database=original)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host = f"http://127.0.0.1:{server.server_port}"
        headers = {"Origin": host}
        with httpx.Client(base_url=host, trust_env=False) as client:
            response = client.get("/api/source-checklist-preview", params={
                "source_name": source.source_name,
                "public_url": str(source.public_url),
            })
            assert response.status_code == 200
            payload = _review_input(source, response.json())
            reviewed = client.post(
                "/api/source-checklist-review", json=payload, headers=headers,
            ).json()
            proposed = {
                **payload,
                "expected_plan_digest": reviewed[
                    "original_registry_update_plan"
                ]["plan_digest"],
                "apply_reason": "Approve this exact old source snapshot for one update.",
                "apply_confirmation": True,
            }
            engine = create_database_engine(f"sqlite:///{original}")
            try:
                with Session(engine) as session, session.begin():
                    changed = PublicSource.model_validate({
                        **source.model_dump(mode="json"),
                        "verification_status": "failed",
                    })
                    SourceRegistryStore(session).upsert_source(changed)
                with Session(engine, autoflush=False) as session, pytest.raises(
                    ValueError, match="changed before locked registry persistence"
                ):
                    persist_authorized_source_registry_records(
                        session, [source],
                        caller_confirmation=True,
                        authorization_reason="Reject the mismatched source snapshot.",
                        expected_current_source=source,
                    )
            finally:
                engine.dispose()
            response = client.post(
                "/api/source-registry-reviewed-apply",
                json=proposed, headers=headers,
            )
            assert response.status_code == 400, response.text
            assert "review" in response.text.lower()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
