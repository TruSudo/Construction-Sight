"""Native original SMARTS combined offline review parity and rejection evidence."""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path

import httpx
import pytest

from constructionsight.command_center_smarts_source_review import (
    native_original_smarts_source_review,
)
from constructionsight.live_command_center import make_server
from constructionsight.smarts_source_review_cli import prepare_source_review
from constructionsight.storage.database import create_database_engine, initialize_database
from tests.test_command_center_investigation_bridge import snapshot
from tests.test_smarts_source_review_cli import _csv


def _retained(tmp_path: Path) -> tuple[Path, Path, Path]:
    folder = tmp_path / "private"
    folder.mkdir(mode=0o700)
    before = _csv(
        folder / "before.csv",
        ("APP_ID", "WDID", "SITE_COUNTY", "STATUS", "PERSONAL_EMAIL"),
        [("101", "8 33C101", "Riverside", "Active", "secret@example.test")],
    )
    after = _csv(
        folder / "after.csv",
        ("APP_ID", "WDID", "SITE_COUNTY", "STATUS", "PERSONAL_EMAIL"),
        [("101", "8 33C101", "Riverside", "Terminated", "secret@example.test")],
    )
    inspection = _csv(
        folder / "inspections.csv",
        ("APP_ID", "WDID", "INSPECTION_ID", "INSPECTION_DATE",
         "PLACE_COUNTY", "PERMIT_TYPE", "INSPECTOR_NOTES"),
        [("101", "8 33C101", "500", "2026-09-01",
          "Riverside", "Construction", "Private inspection note")],
    )
    violations = _csv(
        folder / "violations.csv",
        ("APP_ID", "WDID", "VIOLATION_ID", "OCCURRENCE_DATE",
         "PLACE_COUNTY", "PERMIT_TYPE", "NOTES"),
        [("101", "8 33C101", "600", "2026-09-02",
          "Riverside", "Construction", "Private violation note")],
    )
    enforcement = _csv(
        folder / "enforcement.csv",
        ("APP_ID", "WDID", "ENFORCEMENT_ID", "ISSUANCE_DATE",
         "PLACE_COUNTY", "PERMIT_TYPE", "NOTES"),
        [("101", "8 33C101", "700", "2026-09-03",
          "Riverside", "Construction", "Private enforcement note")],
    )
    manifest = folder / "source-review.json"
    manifest.write_text(json.dumps({
        "schema_version": "constructionsight.smarts-source-review-inputs/v1",
        "previous": before.name, "current": after.name,
        "inspections": inspection.name, "violations": violations.name,
        "enforcement": enforcement.name,
    }), encoding="utf-8")
    return folder, manifest, before


def test_native_smarts_combined_original_sources_same_review_and_no_private_leak(
    tmp_path: Path,
) -> None:
    folder, manifest, _ = _retained(tmp_path)
    report = native_original_smarts_source_review(manifest=manifest, county="Riverside")
    assert report["available"] is True
    assert report["network_executed"] is False
    assert report["persistence_mutated"] is False
    assert report["physical_construction_verified"] is False
    assert report["commercial_authority_granted"] is False
    assert len(report["retained_source_sha256"]) == 5
    expected_inputs = {
        "previous": "before.csv",
        "current": "after.csv",
        "inspections": "inspections.csv",
        "violations": "violations.csv",
        "enforcement": "enforcement.csv",
    }
    for name, filename in expected_inputs.items():
        assert report["retained_source_sha256"][name] == hashlib.sha256(
            (folder / filename).read_bytes()
        ).hexdigest()
    original = prepare_source_review(
        county="Riverside", previous=folder / "before.csv",
        current=folder / "after.csv", inspections=folder / "inspections.csv",
        violations=folder / "violations.csv", enforcement=folder / "enforcement.csv",
    )
    assert report["original_source_review"] == original
    assert original["facility_change_review"]["counts"]["changed"] == 1
    assert original["inspection_review"]["linked_inspection_rows"] == 1
    assert original["compliance_reviews"]["violations"]["linked_records"] == 1
    assert original["compliance_reviews"]["enforcement"]["linked_records"] == 1
    serialized = json.dumps(report)
    assert "secret@example.test" not in serialized
    assert "Private inspection note" not in serialized
    assert "Private violation note" not in serialized
    assert "Private enforcement note" not in serialized
    assert report["original_source_review"]["lead_readiness"] == (
        "blocked_pending_independent_verification"
    )


def test_native_smarts_review_http_only_reads_explicit_manifest(
    tmp_path: Path,
) -> None:
    folder, manifest, _ = _retained(tmp_path)
    database = folder / "operator.sqlite3"
    engine = create_database_engine(f"sqlite:///{database}")
    initialize_database(engine)
    engine.dispose()
    server = make_server(
        snapshot(), 0, folder,
        operator_database=database, operator_smarts_review_manifest=manifest,
    )
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{server.server_port}",
                          trust_env=False) as client:
            for query in ("", "?county=Riverside&x=1",
                          "?county=Riverside&county=San+Bernardino",
                          "?county=Imperial"):
                result = client.get("/api/source-smarts-original-source-review" + query)
                assert result.status_code == 409, result.text
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            response = client.get(
                "/api/source-smarts-original-source-review?county=Riverside"
            )
            assert response.status_code == 200, response.text
            report = response.json()
            assert report["available"] is True
            assert report["original_source_review"]["ok"] is True
            assert report["original_source_review"]["bid_actions"] is False
            assert hashlib.sha256(database.read_bytes()).hexdigest() == before
            assert client.get(
                "/api/source-smarts-original-source-review?county=San+Bernardino"
            ).status_code == 200
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def test_original_smarts_manifest_refuses_changed_invalid_and_duplicate_inputs(
    tmp_path: Path,
) -> None:
    folder, manifest, _ = _retained(tmp_path)
    base = json.loads(manifest.read_text("utf-8"))
    for changed in (
        {**base, "previous": "../outside.csv"},
        {**base, "inspections": "/tmp/outside.csv"},
        {**base, "current": "before.csv"},
        {**base, "other": "unreviewed.csv"},
        {**base, "schema_version": "unknown"},
        {**base, "violations": None},
    ):
        manifest.write_text(json.dumps(changed), encoding="utf-8")
        with pytest.raises(ValueError):
            native_original_smarts_source_review(manifest=manifest, county="Riverside")
    manifest.write_text(json.dumps(base), encoding="utf-8")
    (folder / "inspections.csv").write_text("invalid,columns\n", encoding="utf-8")
    with pytest.raises(ValueError):
        native_original_smarts_source_review(manifest=manifest, county="Riverside")
    unavailable = native_original_smarts_source_review(manifest=None, county="Riverside")
    assert unavailable["available"] is False
    assert unavailable["network_executed"] is False
    with pytest.raises(ValueError):
        native_original_smarts_source_review(manifest=None, county="Imperial")
