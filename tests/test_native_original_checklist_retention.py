"""Original manual source review is retained only after exact separate consent."""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path

import httpx
import pytest
from sqlalchemy.orm import Session

from constructionsight.command_center_original_checklist import (
    preview_original_manual_checklist,
)
from constructionsight.command_center_source_checklist_retention import (
    preview_original_manual_checklist_retention,
    retain_reviewed_original_manual_checklist,
)
from constructionsight.live_command_center import make_server
from constructionsight.storage.database import create_database_engine, initialize_database
from constructionsight.storage.runtime_artifacts import read_runtime_artifact
from constructionsight.storage.source_registry import SourceRegistryStore
from tests.test_command_center_investigation_bridge import snapshot
from tests.test_operator_source_registry import _source


def _fixture(tmp_path: Path) -> tuple[Path, Path, dict[str, object]]:
    database = tmp_path / "original.sqlite3"
    engine = create_database_engine(f"sqlite:///{database}")
    initialize_database(engine)
    source = _source("Retained original source proof", county="Riverside")
    with Session(engine) as session, session.begin():
        SourceRegistryStore(session).upsert_source(source)
    engine.dispose()
    preview = preview_original_manual_checklist(
        database, source_name=source.source_name, public_url=str(source.public_url),
    )
    observation = {
        "source_key": preview["source_key"],
        "source_name": source.source_name,
        "public_entry_observed": True,
        "query_behavior_observed": None,
        "result_list_observed": None,
        "detail_page_observed": None,
        "access_barrier_observed": None,
        "terms_review_observed": None,
        "notes": "Human review of the original source, no independent verification.",
        "evidence_refs": ["reviewed:source:local-evidence"],
    }
    request: dict[str, object] = {
        "source_name": source.source_name,
        "public_url": str(source.public_url),
        "expected_source_sha256": preview["expected_source_sha256"],
        "review_reason": "The operator observed the exact source manually.",
        "caller_confirmation": True,
        "observation": observation,
    }
    return database, tmp_path / "private", request


def test_original_source_checklist_retention_is_create_only_and_offline(
    tmp_path: Path,
) -> None:
    db, private, request = _fixture(tmp_path)
    db_before = hashlib.sha256(db.read_bytes()).hexdigest()
    first = preview_original_manual_checklist_retention(db, private, request)
    second = preview_original_manual_checklist_retention(db, private, request)
    assert first["available"] is True
    assert first["may_request_approval"] is True
    assert first["expected_review_digest"] == second["expected_review_digest"]
    assert first["original_manual_checklist_status"] == "public_entry_reachable"
    assert not (private / "source-verification-evidence").exists()
    assert first["network_executed"] is False
    assert first["source_registry_mutated"] is False

    approval = {
        **request,
        "expected_review_digest": first["expected_review_digest"],
        "retention_reason": "Retain an independently distinguished manual source observation.",
        "retention_confirmation": True,
    }
    with pytest.raises(ValueError, match="stale"):
        retain_reviewed_original_manual_checklist(
            db, private, {**approval, "expected_review_digest": "0" * 64},
        )
    with pytest.raises(ValueError, match="consent"):
        retain_reviewed_original_manual_checklist(
            db, private, {**approval, "retention_confirmation": False},
        )
    receipt = retain_reviewed_original_manual_checklist(db, private, approval)
    assert receipt["retained_evidence_written"] is True
    assert receipt["network_executed"] is False
    assert receipt["source_registry_mutated"] is False
    assert receipt["source_promoted"] is False
    assert receipt["independent_verification_established"] is False
    assert receipt["commercial_authority_granted"] is False
    filename = private / receipt["retained_artifact_ref"]
    bytes_written = read_runtime_artifact(filename, max_bytes=4 * 1024 * 1024)
    assert hashlib.sha256(bytes_written).hexdigest() == receipt[
        "retained_artifact_sha256"
    ]
    stored = json.loads(bytes_written)
    assert stored["review_digest"] == first["expected_review_digest"]
    assert stored["original_review"]["original_manual_checklist"]["source_count"] == 1
    assert stored["original_review"]["original_operator_observation"] == request[
        "observation"
    ]
    assert hashlib.sha256(db.read_bytes()).hexdigest() == db_before
    assert preview_original_manual_checklist_retention(
        db, private, request,
    )["may_request_approval"] is False
    with pytest.raises(ValueError):
        retain_reviewed_original_manual_checklist(db, private, approval)
    assert read_runtime_artifact(filename, max_bytes=4 * 1024 * 1024) == bytes_written


def test_original_checklist_retention_denies_symlink_destination(
    tmp_path: Path,
) -> None:
    db, private, request = _fixture(tmp_path)
    planned = preview_original_manual_checklist_retention(db, private, request)
    target = private / planned["relative_retained_file"]
    target.parent.mkdir(parents=True)
    outsider = tmp_path / "outsider.json"
    outsider.write_text("{}")
    target.symlink_to(outsider)
    with pytest.raises(ValueError, match="already retained or stale"):
        retain_reviewed_original_manual_checklist(
            db, private, {
                **request,
                "expected_review_digest": planned["expected_review_digest"],
                "retention_reason": "Reviewed bounded source verification proof",
                "retention_confirmation": True,
            },
        )
    assert outsider.read_text() == "{}"


def test_original_checklist_retention_exact_native_http_gate(
    tmp_path: Path,
) -> None:
    db, private, request = _fixture(tmp_path)
    server = make_server(snapshot(), 0, private, operator_database=db)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host = f"http://127.0.0.1:{server.server_port}"
        with httpx.Client(base_url=host, trust_env=False) as client:
            cross = client.post(
                "/api/source-checklist-retention-preview",
                json=request, headers={"Origin": "https://evil.invalid"},
            )
            assert cross.status_code == 403
            preview_response = client.post(
                "/api/source-checklist-retention-preview", json=request,
                headers={"Origin": host},
            )
            assert preview_response.status_code == 200, preview_response.text
            review = preview_response.json()
            assert review["may_request_approval"] is True
            denied = client.post(
                "/api/source-checklist-retention",
                json={
                    **request,
                    "expected_review_digest": review["expected_review_digest"],
                    "retention_reason": "Retain this single exact source verification proof",
                    "retention_confirmation": False,
                },
                headers={"Origin": host},
            )
            assert denied.status_code == 400
            retained = client.post(
                "/api/source-checklist-retention",
                json={
                    **request,
                    "expected_review_digest": review["expected_review_digest"],
                    "retention_reason": "Retain this single exact source verification proof",
                    "retention_confirmation": True,
                },
                headers={"Origin": host},
            )
            assert retained.status_code == 200, retained.text
            response = retained.json()
            assert response["retained_evidence_written"] is True
            assert response["commercial_authority_granted"] is False
            assert (private / response["retained_artifact_ref"]).is_file()
            assert client.post(
                "/api/source-checklist-retention", json={
                    **request,
                    "expected_review_digest": review["expected_review_digest"],
                    "retention_reason": "Retain this single exact source verification proof",
                    "retention_confirmation": True,
                }, headers={"Origin": host},
            ).status_code == 400
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
