"""Actual retained CEQAnet CSV → existing SQLite → real operator read paths.

The committed source artifact was captured in July 2026; this test makes no
claim that its source observations reflect present construction activity.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode

import pytest
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from constructionsight.ceqanet_csv_live_models import CeqanetCsvLiveExecution
from constructionsight.ceqanet_csv_operator_bridge import (
    build_reviewed_ceqanet_csv_bridge,
)
from constructionsight.ceqanet_csv_operator_bridge_cli import app
from constructionsight.ceqanet_persistence_execute import execute_ceqanet_write_plan
from constructionsight.operator_dashboard import (
    build_dashboard_snapshot,
    build_geographic_footprint,
    build_workflow_snapshot,
)
from constructionsight.operator_source_candidate import build_source_candidate_preview
from constructionsight.storage.database import create_database_engine
from constructionsight.storage.operator_read_store import create_operator_read_engine

EVIDENCE = (
    Path(__file__).resolve().parents[1]
    / "evidence/source_verification/ceqanet_csv_live_execution_2026-07-12.json"
)
runner = CliRunner()


def _execution() -> CeqanetCsvLiveExecution:
    return CeqanetCsvLiveExecution.model_validate(json.loads(EVIDENCE.read_text("utf-8")))


def test_actual_retained_riverside_csv_bridges_to_existing_source_models() -> None:
    bridge = build_reviewed_ceqanet_csv_bridge(_execution())
    assert bridge.source_sha256 == (
        "5b1bc503c81d12ed0f00e52539edb437b42ae4c3a539a25e1c82a02b84273163"
    )
    assert bridge.source_inspection_digest
    assert len(bridge.source_record_keys) == 2
    assert len(set(bridge.source_record_keys)) == 2
    assert not bridge.preview.skipped_records and not bridge.write_plan.skipped_items
    assert bridge.write_plan.operation_count == bridge.preview.planned_write_count == 4
    assert len(bridge.preview.sites) == 0
    assert len(bridge.preview.entities) == 2
    statuses = {record.document_type for record in bridge.preview.ceqa_records}
    assert statuses == {"EIR", "NOP"}
    for record in bridge.preview.ceqa_records:
        assert record.state_clearinghouse_number == "2026030377"
        assert record.county == "Riverside"
        assert record.title.startswith("Cabazon Infrastructure Plan")
        assert record.received_date is not None
        assert record.site is None  # Community-wide, non-exact APN; do not fake a site.
        assert len(record.entities) == 1
        assert record.entities[0].role.value == "agency"
        assert record.provenance[0].source_url is not None
        assert record.provenance[0].verified is False
        assert record.provenance[0].confidence_score == 0
        assert bridge.source_sha256 in (record.provenance[0].notes or "")
        assert record.provenance[0].raw_reference is not None
        assert "contact_email_address" in (record.provenance[0].evidence_text or "")
        assert record.received_date.year == 2026
    assert bridge.to_dict()["persistence_mutated"] is False
    assert bridge.to_dict()["lead_created"] is False


def test_actual_retained_riverside_csv_sqlite_dossier_evidence_and_map(tmp_path: Path) -> None:
    """Exercise a real 2026 official-source capture through the exact GUI read services."""

    bridge = build_reviewed_ceqanet_csv_bridge(_execution())
    path = tmp_path / "actual-riverside-source.sqlite3"
    engine = create_database_engine(f"sqlite:///{path}")
    result = execute_ceqanet_write_plan(bridge.write_plan.to_dict(), engine=engine)
    assert result.applied_count == 4
    engine.dispose()
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    reader = create_operator_read_engine(path)
    try:
        with Session(reader, autoflush=False) as session:
            page = build_dashboard_snapshot(
                session, kind="ceqa", query="Cabazon", county="Riverside"
            )
            assert page.total == page.returned == 2
            assert {record.record_id for record in page.projects} == set(
                bridge.source_record_keys
            )
            assert {record.source_status for record in page.projects} == {"EIR", "NOP"}
            assert all(not record.entities[0].provenance[0].verified for record in page.projects)
            assert all(record.apn is None and record.point is None for record in page.projects)
            footprint = build_geographic_footprint(session, kind="ceqa", county="Riverside")
            assert footprint.matching_total == footprint.records_scanned == 2
            assert footprint.mapped_in_scan == 0 and not footprint.points
            assert not footprint.truncated
            for project in page.projects:
                dossier = build_source_candidate_preview(
                    session, kind="ceqa", record_id=project.record_id
                )
                assert dossier.source_record.record_id == project.record_id
                assert dossier.source_snapshot.provenance[0].verified is False
                assert dossier.read_only is True
                assert dossier.persisted is False
                assert dossier.commercial_lead_created is False
                assert dossier.outreach_authorized is False
                assert dossier.bid_authorized is False
            assert build_workflow_snapshot(session)["total"] == 0
    finally:
        reader.dispose()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_reviewed_csv_preview_cli_is_non_mutating_and_requires_exact_hashes(
    tmp_path: Path,
) -> None:
    plan_path = tmp_path / "reviewed-plan.json"
    preview = runner.invoke(
        app, ["preview", "--evidence", str(EVIDENCE), "--plan-output", str(plan_path)]
    )
    assert preview.exit_code == 0, preview.output
    payload = json.loads(preview.output)
    assert payload["source_record_count"] == 2
    assert payload["planned_write_count"] == 4
    assert payload["network_executed"] is False
    assert payload["persistence_mutated"] is False
    assert plan_path.is_file()
    plan = json.loads(plan_path.read_text("utf-8"))
    assert plan["metadata"]["persistence_mutated"] is False
    assert plan["metadata"]["operation_count"] == 4
    path = tmp_path / "empty-existing-db.sqlite3"
    path.write_bytes(b"")
    arguments = [
        "apply", "--evidence", str(EVIDENCE), "--database", str(path),
        "--approved-source-sha256", payload["source_sha256"],
        "--approved-plan-digest", payload["approved_plan_digest_required"],
        "--authorization-reason", "Test only: no real persistence authorized",
    ]
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    without_permission = runner.invoke(app, arguments)
    assert without_permission.exit_code != 0
    assert "execute-write" in without_permission.output
    wrong_hash = runner.invoke(
        app, [*arguments, "--approved-plan-digest", "0" * 64, "--execute-write"]
    )
    assert wrong_hash.exit_code != 0
    assert "differs from reviewed hashes" in wrong_hash.output
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_retained_csv_import_rejects_tampered_evidence_and_document_scope() -> None:
    execution = _execution()
    tampered = execution.model_copy(update={"body_sha256": "0" * 64})
    with pytest.raises(ValueError, match="digest mismatch"):
        build_reviewed_ceqanet_csv_bridge(tampered)
    # The original network observation must remain distinguishable from the
    # new, non-mutating offline replay and source-record write-plan proposal.
    assert execution.status_code == 200
    assert execution.inspection is None  # Historical Windows-1252 parse; replay recovers it.
    assert execution.retained_body_complete is True
    assert execution.error is None
