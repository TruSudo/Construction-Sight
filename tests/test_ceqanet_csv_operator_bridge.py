"""Actual retained CEQAnet CSV → existing SQLite → real operator read paths.

The committed source artifact was captured in July 2026; this test makes no
claim that its source observations reflect present construction activity.
"""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import quote

import pytest
import typer
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from constructionsight.ceqanet_csv_live_models import CeqanetCsvLiveExecution
from constructionsight.ceqanet_csv_models import canonical_digest
from constructionsight.ceqanet_csv_operator_bridge import (
    build_reviewed_ceqanet_csv_bridge,
)
from constructionsight.ceqanet_csv_operator_bridge_cli import app, apply as apply_reviewed
from constructionsight.ceqanet_persistence_execute import execute_ceqanet_write_plan
from constructionsight.operator_dashboard import (
    build_dashboard_snapshot,
    build_geographic_footprint,
    build_workflow_snapshot,
)
from constructionsight.operator_source_candidate import build_source_candidate_preview
from constructionsight.operator_web import create_handler
from constructionsight.storage.database import create_database_engine, initialize_database
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
    assert without_permission.exit_code == 2
    with pytest.raises(typer.BadParameter, match="execute-write"):
        apply_reviewed(
            EVIDENCE, path, payload["source_sha256"],
            payload["approved_plan_digest_required"], "Test only", execute_write=False,
        )
    wrong_hash = runner.invoke(
        app, [*arguments, "--approved-plan-digest", "0" * 64, "--execute-write"]
    )
    assert wrong_hash.exit_code == 2
    with pytest.raises(typer.BadParameter, match="differs from reviewed hashes"):
        apply_reviewed(
            EVIDENCE, path, payload["source_sha256"], "0" * 64,
            "Test only", execute_write=True,
        )
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


@contextmanager
def _real_source_operator_server(path: Path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(path))
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def _http_get(port: int, path: str) -> tuple[int, bytes]:
    connection = HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


def test_actual_riverside_csv_import_reaches_command_center_http(tmp_path: Path) -> None:
    """Same genuine retained source → SQLite → official desktop GUI HTTP read routes."""

    bridge = build_reviewed_ceqanet_csv_bridge(_execution())
    path = tmp_path / "actual-ceqanet-command-center.sqlite3"
    engine = create_database_engine(f"sqlite:///{path}")
    assert execute_ceqanet_write_plan(
        bridge.write_plan.to_dict(), engine=engine
    ).applied_count == bridge.write_plan.operation_count
    engine.dispose()
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    with _real_source_operator_server(path) as port:
        status, html = _http_get(port, "/")
        assert status == 200 and b"Construction intelligence, one workspace." in html
        status, script = _http_get(port, "/operator_command_center.js")
        assert status == 200 and b"/api/candidate-preview?" in script
        status, raw = _http_get(
            port, "/api/snapshot?kind=ceqa&q=Cabazon&county=Riverside&limit=25&offset=0"
        )
        assert status == 200
        payload = json.loads(raw)
        assert payload["total"] == payload["returned"] == 2
        assert {row["record_id"] for row in payload["projects"]} == set(
            bridge.source_record_keys
        )
        for record in payload["projects"]:
            assert record["source_status"] in {"EIR", "NOP"}
            assert record["point"] is None
            assert record["coverage"] == "target_county"
            selection = quote(record["record_id"], safe="")
            status, raw = _http_get(
                port, f"/api/candidate-preview?kind=ceqa&record_id={selection}"
            )
            assert status == 200
            preview = json.loads(raw)
            assert preview["source_record"] == record
            assert preview["source_snapshot"]["provenance"][0]["verified"] is False
            assert preview["commercial_lead_created"] is False
            assert preview["outreach_authorized"] is False
            assert preview["bid_authorized"] is False
            assert bridge.source_sha256 in (
                preview["source_snapshot"]["provenance"][0]["notes"]
            )
        status, raw = _http_get(port, "/api/footprint?kind=ceqa&county=Riverside")
        assert status == 200
        footprint = json.loads(raw)
        assert footprint["matching_total"] == 2 and footprint["points"] == []
        status, raw = _http_get(port, "/api/workflows?limit=25&offset=0")
        assert status == 200 and json.loads(raw)["total"] == 0
        status, raw = _http_get(port, "/api/source-revision")
        assert status == 200
        revision = json.loads(raw)
        assert revision["source_families"]["ceqa"]["record_count"] == 2
        assert revision["source_families"]["permit"]["record_count"] == 0
        assert revision["read_only"] and not revision["live_collection_enabled"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_real_riverside_csv_cli_authorized_apply_to_operator_sqlite(tmp_path: Path) -> None:
    """Run the actual two-digest reviewed CLI path through governed persistence."""

    bridge = build_reviewed_ceqanet_csv_bridge(_execution())
    path = tmp_path / "authorized-historical-riverside.sqlite3"
    engine = create_database_engine(f"sqlite:///{path}")
    initialize_database(engine)
    engine.dispose()
    source_before = hashlib.sha256(EVIDENCE.read_bytes()).hexdigest()
    arguments = [
        "apply", "--evidence", str(EVIDENCE), "--database", str(path),
        "--approved-source-sha256", bridge.source_sha256,
        "--approved-plan-digest", canonical_digest(bridge.write_plan.to_dict()),
        "--authorization-reason", "Apply exact retained Riverside fixture to isolated test DB",
        "--operator-id", "operator:reviewed-import-integration-test",
        "--execute-write",
    ]
    result = runner.invoke(app, arguments)
    assert result.exit_code == 0, result.output
    # The existing governance layer writes the authorization audit to stderr;
    # CliRunner.output merges the two streams, but a real CLI keeps JSON stdout clean.
    audit = json.loads(result.stderr.strip().splitlines()[0])
    assert audit["action"] == "execute-ceqanet-write-plan"
    payload = json.loads(result.stdout)
    assert payload["applied_operations"] == bridge.write_plan.operation_count == 4
    assert payload["operator_readback_verified"] is True
    assert payload["commercial_leads_created"] is False
    assert payload["source_review_state"] == "unassessed"
    reader = create_operator_read_engine(path)
    try:
        with Session(reader, autoflush=False) as session:
            page = build_dashboard_snapshot(session, kind="ceqa", county="Riverside")
            assert page.total == 2
            assert {record.record_id for record in page.projects} == set(
                bridge.source_record_keys
            )
            assert build_workflow_snapshot(session)["total"] == 0
    finally:
        reader.dispose()
    assert hashlib.sha256(EVIDENCE.read_bytes()).hexdigest() == source_before
