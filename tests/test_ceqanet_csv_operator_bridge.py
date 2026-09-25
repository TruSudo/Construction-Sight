"""Actual retained CEQAnet CSV → existing SQLite → real operator read paths.

The committed source artifact was captured in July 2026; this test makes no
claim that its source observations reflect present construction activity.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
import hashlib
import json
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from types import SimpleNamespace
from urllib.parse import quote

import pytest
import typer
from sqlalchemy.orm import Session
from typer.testing import CliRunner

import constructionsight.ceqanet_csv_operator_bridge_cli as capture_module
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
        status, raw = _http_get(port, "/api/entity-index?kind=ceqa&county=Riverside")
        assert status == 200
        index = json.loads(raw)
        assert index["read_only"] and not index["live_collection_enabled"]
        assert index["matching_source_records"] == index["scanned_source_records"] == 2
        assert index["distinct_keys_in_scan"] >= 1
        assert index["entries"] and all(
            entry["riverside_records"] == entry["matching_records_in_scan"]
            and entry["san_bernardino_records"] == 0
            and entry["appears_in_both_target_counties"] is False
            for entry in index["entries"]
        )
        status, raw = _http_get(
            port, "/api/entity-index?kind=ceqa&county=Riverside&role=agency"
        )
        assert status == 200
        agency_index = json.loads(raw)
        assert agency_index["role_filter"] == "agency"
        assert {entry["entity_key"] for entry in agency_index["entries"]} == {
            entry["entity_key"] for entry in index["entries"]
        }
        status, raw = _http_get(
            port, "/api/entity-index?kind=ceqa&county=Riverside&role=contractor"
        )
        assert status == 200
        assert json.loads(raw)["entries"] == []
        retained_keys = {
            entity["entity_key"]
            for record in payload["projects"]
            for entity in record["entities"]
        }
        assert {entry["entity_key"] for entry in index["entries"]} == retained_keys
        for entry in index["entries"]:
            status, raw = _http_get(
                port, "/api/entity-neighborhood?kind=ceqa&county=Riverside&entity_key="
                + quote(entry["entity_key"], safe="")
            )
            assert status == 200
            neighborhood = json.loads(raw)
            assert neighborhood["read_only"]
            assert neighborhood["entity_key"] == entry["entity_key"]
            assert neighborhood["matching_records_in_scan"] == entry[
                "matching_records_in_scan"
            ]
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


def test_capture_preview_delegates_one_exact_authorized_get_and_replays_saved_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One explicit capture bridges a retained public-source response without importing."""

    calls: list[dict[str, object]] = []
    delivered: list[CeqanetCsvLiveExecution] = []

    def authorized_capture(**kwargs: object) -> SimpleNamespace:
        calls.append(kwargs)
        # A mocked NEW invocation must carry the current effect timestamp;
        # the retained body remains the actual historical July source fixture.
        source = _execution().model_copy(update={"executed_at": datetime.now(UTC)})
        delivered.append(source)
        return SimpleNamespace(
            execution=source, verification=SimpleNamespace(passed=True),
        )

    monkeypatch.setattr(
        capture_module, "execute_authorized_ceqanet_csv", authorized_capture,
    )
    evidence = tmp_path / "new-exact-capture.json"
    plan = tmp_path / "unapproved-plan.json"
    result = runner.invoke(
        app, [
            "capture-preview", "--sch-number", "2026030377",
            "--output", str(evidence), "--plan-output", str(plan),
            "--authorization-reason", "One reviewed public project scope",
            "--execute-live",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert len(calls) == 1
    assert calls[0]["request"].sch_number == "2026030377"
    assert calls[0]["request"].document_id is None
    assert calls[0]["access_profile"].public_url == calls[0]["request"].source_url
    assert calls[0]["caller_confirmation"] is True
    assert calls[0]["max_retained_rows"] == 100
    assert payload["source_record_count"] == 2
    assert payload["planned_write_count"] == 4
    assert payload["network_executed"] is True
    assert payload["persistence_mutated"] is False
    assert payload["qualified_leads_created"] is False
    assert payload["source_claims_verified"] is False
    assert payload["source_evidence_path"] == str(evidence)
    assert payload["plan_output_path"] == str(plan)
    assert payload["source_verification_passed"] is True
    assert payload["execution_timestamp_within_invocation"] is True
    assert payload["approved_plan_digest_required"] == canonical_digest(
        json.loads(plan.read_text("utf-8"))
    )
    saved = CeqanetCsvLiveExecution.model_validate(json.loads(evidence.read_text("utf-8")))
    assert saved == delivered[0]
    assert saved.body_sha256 == _execution().body_sha256
    assert saved.executed_at.year == 2026
    assert not (tmp_path / "operator.sqlite3").exists()


def test_capture_preview_rejects_missing_authority_and_existing_outputs_before_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The command never acquires a source without explicit approval and fresh paths."""

    calls: list[dict[str, object]] = []

    def no_request(**kwargs: object) -> SimpleNamespace:
        calls.append(kwargs)
        raise AssertionError("no acquisition is authorized by this input")

    monkeypatch.setattr(capture_module, "execute_authorized_ceqanet_csv", no_request)
    evidence = tmp_path / "capture.json"
    plan = tmp_path / "plan.json"
    base = [
        "capture-preview", "--sch-number", "2026030377",
        "--output", str(evidence), "--authorization-reason", "Reviewed exact scope",
    ]
    for arguments in (
        base,
        [
            "capture-preview", "--sch-number", "2026030377",
            "--output", str(evidence), "--authorization-reason", "  ",
            "--execute-live",
        ],
        [*base, "--execute-live", "--plan-output", str(evidence)],
        [
            "capture-preview", "--sch-number", "not-an-sch",
            "--output", str(evidence), "--authorization-reason", "Reviewed exact scope",
            "--execute-live",
        ],
    ):
        result = runner.invoke(app, arguments)
        assert result.exit_code != 0
    evidence.write_text("existing source is never overwritten", encoding="utf-8")
    plan.write_text("existing plan is never overwritten", encoding="utf-8")
    result = runner.invoke(app, [*base, "--execute-live", "--plan-output", str(plan)])
    assert result.exit_code != 0
    assert evidence.read_text("utf-8") == "existing source is never overwritten"
    assert plan.read_text("utf-8") == "existing plan is never overwritten"
    assert not calls


def test_capture_preview_preserves_failed_verification_and_rejects_claimed_captcha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence = tmp_path / "failed-verification.json"
    plan = tmp_path / "never-written-plan.json"
    governed_capture = capture_module.execute_authorized_ceqanet_csv
    monkeypatch.setattr(
        capture_module, "execute_authorized_ceqanet_csv",
        lambda **_: SimpleNamespace(
            execution=_execution(), verification=SimpleNamespace(passed=False),
        ),
    )
    arguments = [
        "capture-preview", "--sch-number", "2026030377",
        "--output", str(evidence), "--plan-output", str(plan),
        "--authorization-reason", "Inspect one public record",
        "--execute-live",
    ]
    result = runner.invoke(app, arguments)
    assert result.exit_code == 1
    assert evidence.is_file() and not plan.exists()
    assert "Retained source verification failed" in result.output

    # Restore the actual lawful-access facade, never a mock, for denial verification.
    monkeypatch.setattr(capture_module, "execute_authorized_ceqanet_csv", governed_capture)
    # The real governed facade must refuse disclosed CAPTCHA access before HTTP.
    blocked = runner.invoke(
        app, [
            "capture-preview", "--sch-number", "2026030377",
            "--output", str(tmp_path / "blocked.json"),
            "--authorization-reason", "Known CAPTCHA must block",
            "--execute-live", "--has-captcha",
        ],
    )
    assert blocked.exit_code == 1
    assert "blocked" in blocked.output.lower()
    assert not (tmp_path / "blocked.json").exists()


def test_capture_preview_refuses_old_effect_replay_as_new_public_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Durable exact-request replay remains auditable but cannot claim new ingestion."""

    monkeypatch.setattr(
        capture_module, "execute_authorized_ceqanet_csv",
        lambda **_: SimpleNamespace(
            execution=_execution(), verification=SimpleNamespace(passed=True),
        ),
    )
    path = tmp_path / "previously-captured-response.json"
    plan = tmp_path / "must-not-suggest-import.json"
    result = runner.invoke(
        app, [
            "capture-preview", "--sch-number", "2026030377",
            "--output", str(path), "--plan-output", str(plan),
            "--authorization-reason", "Require genuinely new response",
            "--execute-live",
        ],
    )
    assert result.exit_code == 1
    assert "not a new public-source acquisition" in result.output
    assert path.is_file()
    assert not plan.exists()
    assert CeqanetCsvLiveExecution.model_validate(
        json.loads(path.read_text("utf-8"))
    ) == _execution()


def test_capture_preview_to_separate_authorized_apply_and_live_operator_http(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mock only the network boundary; replay, approve, persist and GET real SQLite."""

    def captured_once(**_: object) -> SimpleNamespace:
        # The source BODY is the genuine committed JULY capture, not a new live GET.
        # Its invocation timestamp is adjusted solely to simulate the CLI's
        # fresh-effect contract without making a real network request in CI.
        execution = _execution().model_copy(update={"executed_at": datetime.now(UTC)})
        return SimpleNamespace(
            execution=execution, verification=SimpleNamespace(passed=True),
        )

    monkeypatch.setattr(capture_module, "execute_authorized_ceqanet_csv", captured_once)
    evidence = tmp_path / "mock-boundary-actual-retained-body.json"
    plan = tmp_path / "mock-boundary-unapproved-plan.json"
    capture = runner.invoke(
        app, [
            "capture-preview", "--sch-number", "2026030377",
            "--output", str(evidence), "--plan-output", str(plan),
            "--authorization-reason", "CI simulation of one exact public GET",
            "--execute-live",
        ],
    )
    assert capture.exit_code == 0, capture.output
    preview = json.loads(capture.stdout)
    assert preview["persistence_mutated"] is False
    assert preview["source_sha256"] == _execution().body_sha256
    assert preview["planned_write_count"] == 4
    path = tmp_path / "operator-for-explicit-reviewed-apply.sqlite3"
    engine = create_database_engine(f"sqlite:///{path}")
    initialize_database(engine)
    engine.dispose()

    # A separate import must still present both reviewed digests and its OWN
    # write authorization; the capture's --execute-live is never sufficient.
    args = [
        "apply", "--evidence", str(evidence), "--database", str(path),
        "--approved-source-sha256", preview["source_sha256"],
        "--approved-plan-digest", preview["approved_plan_digest_required"],
        "--authorization-reason", "Independent exact-plan approval in CI",
    ]
    before_approval = hashlib.sha256(path.read_bytes()).hexdigest()
    denied = runner.invoke(app, args)
    assert denied.exit_code == 2
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before_approval
    applied = runner.invoke(app, [*args, "--execute-write"])
    assert applied.exit_code == 0, applied.output
    assert json.loads(applied.stdout)["operator_readback_verified"] is True

    before = hashlib.sha256(path.read_bytes()).hexdigest()
    with _real_source_operator_server(path) as port:
        status, raw = _http_get(
            port, "/api/snapshot?kind=ceqa&county=Riverside&q=Cabazon&limit=50&offset=0"
        )
        assert status == 200
        page = json.loads(raw)
        assert page["total"] == page["returned"] == 2
        assert {row["record_id"] for row in page["projects"]} == set(
            preview["source_records"]
        )
        assert all(row["point"] is None and row["apn"] is None for row in page["projects"])
        status, raw = _http_get(port, "/api/entity-index?kind=ceqa&county=Riverside")
        assert status == 200
        assert json.loads(raw)["matching_source_records"] == 2
        status, raw = _http_get(port, "/api/workflows?limit=25&offset=0")
        assert status == 200 and json.loads(raw)["total"] == 0
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_capture_preview_rejects_result_from_another_sch_without_ever_importing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The saved source cannot be represented as the operator's approved SCH."""

    monkeypatch.setattr(
        capture_module, "execute_authorized_ceqanet_csv",
        lambda **_: SimpleNamespace(
            execution=_execution().model_copy(update={"executed_at": datetime.now(UTC)}),
            verification=SimpleNamespace(passed=True),
        ),
    )
    path = tmp_path / "mismatched-source.json"
    plan = tmp_path / "no-mismatched-plan.json"
    result = runner.invoke(
        app, [
            "capture-preview", "--sch-number", "2026030378",
            "--output", str(path), "--plan-output", str(plan),
            "--authorization-reason", "Reject misrouted exact project identity",
            "--execute-live",
        ],
    )
    assert result.exit_code == 1
    assert "does not match the exact approved SCH request" in result.output
    assert path.is_file() and not plan.exists()
    assert CeqanetCsvLiveExecution.model_validate(
        json.loads(path.read_text("utf-8"))
    ).request.sch_number == "2026030377"

def test_listing_queue_bound_capture_apply_and_operator_http_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prove listing discovery -> bound exact capture -> approved SQLite -> operator HTTP."""

    html = (
        '<div class="search-result">'
        '<a href="/Project/2026030377">Cabazon Infrastructure Plan</a>'
        '<span>SCH Number</span><span>2026030377</span>'
        '<span>County</span><span>Riverside</span>'
        '</div>'
    )
    listing = {
        "metadata": {
            "schema_version": "ceqanet_listing_execution.v2",
            "allowed": True,
            "planned_request_count": 1,
            "executed_request_count": 1,
            "successful_response_count": 1,
            "failed_response_count": 0,
            "plan_id": "end-to-end-bound-listing",
            "access": {"decision": "allowed"},
            "authorization": {"decision_id": "end-to-end-test-authorization"},
        },
        "snapshots": [{
            "page_number": 1,
            "method": "GET",
            "request_url": "https://ceqanet.lci.ca.gov/Search?County=Riverside",
            "final_url": "https://ceqanet.lci.ca.gov/Search?County=Riverside",
            "status_code": 200,
            "content_type": "text/html; charset=utf-8",
            "body_text": html,
            "body_length": len(html),
            "body_truncated": False,
            "executed": True,
            "reachable": True,
            "error": None,
            "failure_kind": "none",
        }],
    }
    listing_path = tmp_path / "listing.json"
    queue_path = tmp_path / "queue.json"
    evidence = tmp_path / "bound-capture.json"
    plan = tmp_path / "bound-plan.json"
    listing_path.write_text(json.dumps(listing, sort_keys=True), encoding="utf-8")

    discovered = runner.invoke(
        app, [
            "discover-preview", "--listing-evidence", str(listing_path),
            "--output", str(queue_path),
        ],
    )
    assert discovered.exit_code == 0, discovered.output
    assert json.loads(discovered.stdout)["candidate_count"] == 1

    monkeypatch.setattr(
        capture_module, "execute_authorized_ceqanet_csv",
        lambda **_: SimpleNamespace(
            execution=_execution().model_copy(update={"executed_at": datetime.now(UTC)}),
            verification=SimpleNamespace(passed=True),
        ),
    )
    captured = runner.invoke(
        app, [
            "capture-preview", "--sch-number", "2026030377",
            "--listing-evidence", str(listing_path),
            "--queue-evidence", str(queue_path),
            "--output", str(evidence), "--plan-output", str(plan),
            "--authorization-reason", "Capture exact independently rebound queued project",
            "--execute-live",
        ],
    )
    assert captured.exit_code == 0, captured.output
    preview = json.loads(captured.stdout)
    binding = preview["discovery_binding"]
    assert binding["sch_number"] == "2026030377"
    assert binding["source_claimed_county"] == "Riverside"
    assert binding["listing_artifact_sha256"] == hashlib.sha256(
        listing_path.read_bytes()
    ).hexdigest()
    assert binding["queue_artifact_sha256"] == hashlib.sha256(
        queue_path.read_bytes()
    ).hexdigest()
    retained = json.loads(evidence.read_text("utf-8"))
    assert retained["schema_version"] == "ceqanet_bound_project_capture.v1"
    assert retained["discovery_binding"] == binding
    assert retained["live_execution"]["request"]["sch_number"] == "2026030377"

    database = tmp_path / "operator-bound.sqlite3"
    engine = create_database_engine(f"sqlite:///{database}")
    initialize_database(engine)
    engine.dispose()
    applied = runner.invoke(
        app, [
            "apply", "--evidence", str(evidence), "--database", str(database),
            "--approved-source-sha256", preview["source_sha256"],
            "--approved-plan-digest", preview["approved_plan_digest_required"],
            "--authorization-reason", "Independent approval of exact bound source and plan",
            "--execute-write",
        ],
    )
    assert applied.exit_code == 0, applied.output
    assert json.loads(applied.stdout)["operator_readback_verified"] is True

    with _real_source_operator_server(database) as port:
        status, raw = _http_get(
            port, "/api/snapshot?kind=ceqa&county=Riverside&q=Cabazon&limit=50&offset=0"
        )
        assert status == 200
        page = json.loads(raw)
        assert page["total"] == page["returned"] == 2
        assert {row["record_id"] for row in page["projects"]} == set(
            preview["source_records"]
        )
        assert all(row["county"] == "Riverside" for row in page["projects"])

