"""Native retained-source audit must equal original offline report services.

Never turns existing verification labels into a live source probe or promotion.
"""

from __future__ import annotations

import hashlib
import threading
from copy import deepcopy
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from constructionsight.adapters import default_adapter_family_specs
from constructionsight.live_command_center import make_server
from constructionsight.source_status_report import build_source_status_report
from constructionsight.source_promotion_plan_service import build_source_promotion_plan
from constructionsight.source_registry_update_plan_service import build_source_registry_update_plan
from constructionsight.source_verification_checklist_service import (
    build_source_observation_templates,
    build_source_verification_checklist_report,
)
from constructionsight.source_verification_evidence_service import (
    build_source_verification_evidence_package,
)
from constructionsight.storage.database import create_database_engine, initialize_database
from constructionsight.storage.source_registry import SourceRegistryStore
from tests.test_command_center_investigation_bridge import snapshot
from tests.test_operator_source_registry import _source


def _without_original_generated_at(payload: dict) -> dict:
    """Both original evidence rows and their package have fresh build timestamps."""
    copy = deepcopy(payload)
    assert copy.pop("generated_at")
    for row in copy["rows"]:
        assert row.pop("generated_at")
    return copy


def test_native_original_audit_exact_offline_services_without_touching_source(
    tmp_path: Path,
) -> None:
    original_db = tmp_path / "original.sqlite3"
    engine = create_database_engine(f"sqlite:///{original_db}")
    initialize_database(engine)
    source = _source("Synthetic source offline audit", county="Riverside")
    with Session(engine) as session, session.begin():
        SourceRegistryStore(session).upsert_source(source)
    engine.dispose()
    source_before = hashlib.sha256(original_db.read_bytes()).hexdigest()
    private = tmp_path / "private"
    server = make_server(snapshot(), 0, private, operator_database=original_db)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False,
        ) as client:
            response = client.get("/api/source-offline-audit")
            assert response.status_code == 200, response.text
            report = response.json()
            adapters = default_adapter_family_specs()
            assert report["available"] is True
            assert report["source_count"] == 1
            assert report["original_status_report"] == build_source_status_report(
                [source], adapters,
            ).to_dict()
            assert _without_original_generated_at(
                report["original_evidence_package"]
            ) == _without_original_generated_at(
                build_source_verification_evidence_package(
                    [source], adapters, check_http=False,
                ).to_dict()
            )
            assert _without_original_generated_at(
                report["original_manual_checklist"]
            ) == _without_original_generated_at(
                build_source_verification_checklist_report(
                    [source], adapters, check_http=False,
                ).to_dict()
            )
            assert _without_original_generated_at(
                report["original_promotion_plan"]
            ) == _without_original_generated_at(
                build_source_promotion_plan([source], adapters, check_http=False).to_dict()
            )
            assert _without_original_generated_at(
                report["original_registry_update_plan"]
            ) == _without_original_generated_at(
                build_source_registry_update_plan([source], adapters, check_http=False).to_dict()
            )
            assert report["original_registry_update_plan"]["update_count"] == 0
            assert report["original_manual_checklist"]["rows"][0][
                "detail_page"
            ] == "not_checked"
            assert report["original_observation_templates"] == [
                template.model_dump(mode="json")
                for template in build_source_observation_templates([source])
            ]
            assert report["original_observation_templates"][0][
                "query_behavior_observed"
            ] is None
            assert report["network_executed"] is False
            assert report["http_checked"] is False
            assert report["source_database_mutated"] is False
            assert report["source_promotion_authorized"] is False
            assert report["source_claim_only"] is True
            assert report["read_only"] is True
            repeated = client.get("/api/source-offline-audit").json()
            assert repeated["original_status_report"] == report["original_status_report"]
            assert _without_original_generated_at(
                repeated["original_manual_checklist"]
            ) == _without_original_generated_at(report["original_manual_checklist"])
            assert repeated["original_registry_update_plan"]["plan_digest"] == report[
                "original_registry_update_plan"
            ]["plan_digest"]
            assert repeated["original_observation_templates"] == report[
                "original_observation_templates"
            ]
            assert _without_original_generated_at(
                repeated["original_evidence_package"]
            ) == _without_original_generated_at(report["original_evidence_package"])
            for query in ("?check_http=true", "?promote=true", "?extra=1"):
                assert client.get("/api/source-offline-audit" + query).status_code == 409
            assert hashlib.sha256(original_db.read_bytes()).hexdigest() == source_before
            assert not (private / "investigations.sqlite3").exists()
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def test_native_original_audit_does_not_invent_unconfigured_registry(
    tmp_path: Path,
) -> None:
    private = tmp_path / "private"
    server = make_server(snapshot(), 0, private)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False,
        ) as client:
            response = client.get("/api/source-offline-audit")
            assert response.status_code == 200, response.text
            assert response.json()["available"] is False
            assert response.json()["network_collection_enabled"] is False
            assert "source_count" not in response.json()
            assert not (private / "investigations.sqlite3").exists()
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
