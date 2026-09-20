"""Synthetic end-to-end evidence for explicitly authorized source review staging."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from sqlalchemy import delete, inspect, update
from sqlalchemy.orm import Session
from typer.testing import CliRunner

import constructionsight.effect_consumption as effects
import constructionsight.source_candidate_docket_service as docket
from constructionsight.authorization_decision import AuthorizationDeniedError
from constructionsight.ceqa_models import CeqaRecord
from constructionsight.permit_models import PermitRecord
from constructionsight.provenance import Provenance
from constructionsight.source_candidate_docket_cli import app
from constructionsight.source_candidate_docket_service import (
    CandidateDocketError,
    CandidateSourceChanged,
    list_staged_source_candidates,
    preview_source_for_docket,
    stage_authorized_source_candidate,
)
from constructionsight.storage.database import create_database_engine, initialize_database
from constructionsight.storage.domain_orm import CeqaDomainRecord
from constructionsight.storage.domain_store import CeqaStore, PermitStore
from constructionsight.storage.effect_consumption_store import (
    EffectConsumptionStore,
    EffectOutcomeUnavailableError,
)
from constructionsight.storage.source_candidate_docket_orm import SourceCandidateDocketRow


@pytest.fixture
def target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "source.sqlite3"
    engine = create_database_engine(f"sqlite+pysqlite:///{path}")
    initialize_database(engine)
    evidence = [Provenance(source_name="Synthetic source", evidence_text="Fixture only")]
    with Session(engine) as session, session.begin():
        CeqaStore(session).upsert(CeqaRecord(
            ceqa_key="shared", title="Synthetic project", county="San Bernardino",
            provenance=evidence,
        ))
        PermitStore(session).upsert(PermitRecord(
            permit_key="shared", permit_number="TEST", jurisdiction="Fontana",
            county="San Bernardino", provenance=evidence,
        ))
    engine.dispose()
    monkeypatch.setattr(
        effects, "_owned_store",
        lambda: EffectConsumptionStore(tmp_path / "effect-reservations.sqlite3"),
    )
    return path


def _stage(path: Path, *, kind: str = "ceqa", record_id: str = "shared",
           reason: str = "Preserve one synthetic record for further review"):
    preview = preview_source_for_docket(path, kind=kind, record_id=record_id)
    return stage_authorized_source_candidate(
        path, kind=kind, record_id=record_id,
        expected_preview_id=preview.preview_id,
        expected_source_sha256=preview.normalized_source_sha256,
        caller_confirmation=True, reason=reason, operator_id="operator:fixture",
    )


def test_exact_source_staging_is_append_only_and_not_a_commercial_lead(target: Path):
    first = _stage(target)
    assert first.entry.recorded_new
    assert first.entry.preview.source_snapshot.model_dump().get("ceqa_key") == "shared"
    assert first.entry.preview.state == "review_required"
    assert not first.entry.commercial_lead_created
    assert not first.entry.outreach_authorized and not first.entry.bid_authorized
    assert first.authorization.decision.action == "stage-source-candidate-review"
    assert first.entry.reason_text == "Preserve one synthetic record for further review"
    again = _stage(target)
    assert again.entry == first.entry
    assert len(list_staged_source_candidates(target, kind="ceqa", record_id="shared")) == 1
    other = _stage(target, kind="permit")
    assert other.entry.preview_id != first.entry.preview_id
    assert len(list_staged_source_candidates(target, kind="permit", record_id="shared")) == 1


def test_unconfirmed_and_stale_source_have_no_effect(target: Path):
    p = preview_source_for_docket(target, kind="ceqa", record_id="shared")
    with pytest.raises(AuthorizationDeniedError):
        stage_authorized_source_candidate(
            target, kind="ceqa", record_id="shared",
            expected_preview_id=p.preview_id,
            expected_source_sha256=p.normalized_source_sha256,
            caller_confirmation=False, reason="Not confirmed",
        )
    with pytest.raises(CandidateSourceChanged):
        stage_authorized_source_candidate(
            target, kind="ceqa", record_id="shared",
            expected_preview_id=p.preview_id,
            expected_source_sha256="0" * 64,
            caller_confirmation=True, reason="Stale snapshot",
        )
    assert list_staged_source_candidates(target, kind="ceqa", record_id="shared") == []


def test_source_change_during_protected_effect_rolls_back_without_stage(
    target: Path, monkeypatch: pytest.MonkeyPatch,
):
    before = preview_source_for_docket(target, kind="ceqa", record_id="shared")
    original_effect = docket._execute_owned_effect

    def change_then_execute(*args, **kwargs):
        engine = create_database_engine(f"sqlite+pysqlite:///{target}")
        with Session(engine) as session, session.begin():
            CeqaStore(session).upsert(CeqaRecord(
                ceqa_key="shared", title="Changed after preflight",
                county="San Bernardino",
                provenance=[Provenance(source_name="Synthetic source")],
            ))
        engine.dispose()
        return original_effect(*args, **kwargs)

    monkeypatch.setattr(docket, "_execute_owned_effect", change_then_execute)
    with pytest.raises(CandidateSourceChanged):
        stage_authorized_source_candidate(
            target, kind="ceqa", record_id="shared",
            expected_preview_id=before.preview_id,
            expected_source_sha256=before.normalized_source_sha256,
            caller_confirmation=True, reason="Attempt stale source",
            operator_id="operator:fixture",
        )
    assert list_staged_source_candidates(target, kind="ceqa", record_id="shared") == []


def test_cli_preview_stage_list_and_explicit_confirmation(target: Path):
    runner = CliRunner()
    args = ["--database", str(target), "--kind", "ceqa", "--record-id", "shared"]
    read = runner.invoke(app, ["preview", *args])
    assert read.exit_code == 0
    current = json.loads(read.output)
    params = [
        "stage", *args, "--expected-preview-id", current["preview_id"],
        "--expected-source-sha256", current["normalized_source_sha256"],
        "--reason", "Preserve this source for review",
        "--operator-id", "operator:fixture",
    ]
    denied = runner.invoke(app, params)
    assert denied.exit_code == 2
    accepted = runner.invoke(app, [*params, "--confirm"])
    assert accepted.exit_code == 0
    assert json.loads(accepted.stdout)["recorded_new"] is True
    changed_reason = params.copy()
    changed_reason[changed_reason.index("--reason") + 1] = (
        "A later attempt to relabel the same content snapshot"
    )
    conflict = runner.invoke(app, [*changed_reason, "--confirm"])
    assert conflict.exit_code == 2
    assert "EffectReplayConflictError" in conflict.stderr
    assert "Traceback" not in conflict.stderr
    listed = runner.invoke(app, ["list", *args])
    assert listed.exit_code == 0
    assert len(json.loads(listed.stdout)) == 1


def test_existing_schema_is_required_and_absent_schema_is_not_created(
    tmp_path: Path,
):
    path = tmp_path / "old.sqlite3"
    engine = create_database_engine(f"sqlite+pysqlite:///{path}")

    CeqaDomainRecord.__table__.create(engine)
    with Session(engine) as session, session.begin():
        CeqaStore(session).upsert(CeqaRecord(
            ceqa_key="old", title="Old fixture", county="Riverside",
            provenance=[Provenance(source_name="Synthetic source")],
        ))
    engine.dispose()
    p = preview_source_for_docket(path, kind="ceqa", record_id="old")
    with pytest.raises(CandidateDocketError, match="docket table is absent"):
        stage_authorized_source_candidate(
            path, kind="ceqa", record_id="old",
            expected_preview_id=p.preview_id,
            expected_source_sha256=p.normalized_source_sha256,
            caller_confirmation=True, reason="Schema missing",
        )
    engine = create_database_engine(f"sqlite+pysqlite:///{path}")

    assert not inspect(engine).has_table("source_candidate_review_docket")
    engine.dispose()



def test_amended_source_keeps_prior_snapshot_and_appends_review_revision(target: Path):
    original = _stage(target)
    engine = create_database_engine(f"sqlite+pysqlite:///{target}")
    with Session(engine) as session, session.begin():
        CeqaStore(session).upsert(CeqaRecord(
            ceqa_key="shared", title="Synthetic revised title",
            county="San Bernardino",
            provenance=[Provenance(source_name="Synthetic source", evidence_text="Rev 2")],
        ))
    engine.dispose()
    revised = _stage(target)
    records = list_staged_source_candidates(target, kind="ceqa", record_id="shared")
    assert len(records) == 2
    assert records[0].preview_id == revised.entry.preview_id
    assert records[1].preview_id == original.entry.preview_id
    assert records[0].candidate_key == records[1].candidate_key
    assert records[0].normalized_source_sha256 != records[1].normalized_source_sha256
    assert records[1].preview.source_snapshot.model_dump().get("title") == (
        "Synthetic project"
    )


def test_altered_staged_payload_digest_fails_integrity_verification(target: Path):
    original = _stage(target)
    engine = create_database_engine(f"sqlite+pysqlite:///{target}")

    with Session(engine) as session, session.begin():
        session.execute(
            update(SourceCandidateDocketRow)
            .where(SourceCandidateDocketRow.stage_id == original.entry.stage_id)
            .values(preview_payload_sha256="0" * 64)
        )
    engine.dispose()
    with pytest.raises(CandidateDocketError, match="identity or payload changed"):
        list_staged_source_candidates(target, kind="ceqa", record_id="shared")


def test_concurrent_exact_staging_never_inserts_twice(target: Path):
    def attempt():
        try:
            return _stage(target).entry
        except EffectOutcomeUnavailableError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = [future.result(timeout=30) for future in [
            pool.submit(attempt), pool.submit(attempt)
        ]]
    assert any(not isinstance(item, Exception) for item in outcomes)
    assert len(list_staged_source_candidates(target, kind="ceqa", record_id="shared")) == 1



def test_missing_staged_row_is_not_silently_replayed_as_durable(target: Path):
    first = _stage(target)
    engine = create_database_engine(f"sqlite+pysqlite:///{target}")

    with Session(engine) as session, session.begin():
        session.execute(
            delete(SourceCandidateDocketRow).where(
                SourceCandidateDocketRow.stage_id == first.entry.stage_id
            )
        )
    engine.dispose()
    with pytest.raises(CandidateDocketError, match="database entry is absent"):
        _stage(target)
    assert list_staged_source_candidates(target, kind="ceqa", record_id="shared") == []


def test_oversized_source_review_is_rejected_before_authorization(
    target: Path,
):
    engine = create_database_engine(f"sqlite+pysqlite:///{target}")
    with Session(engine) as session, session.begin():
        CeqaStore(session).upsert(CeqaRecord(
            ceqa_key="large", title="Synthetic large text", county="Riverside",
            description="x" * 1_000_001,
            provenance=[Provenance(source_name="Synthetic source")],
        ))
    engine.dispose()
    p = preview_source_for_docket(target, kind="ceqa", record_id="large")
    with pytest.raises(CandidateDocketError, match="retention size limit"):
        stage_authorized_source_candidate(
            target, kind="ceqa", record_id="large",
            expected_preview_id=p.preview_id,
            expected_source_sha256=p.normalized_source_sha256,
            caller_confirmation=True,
            reason="Do not start a high-volume staging effect",
            operator_id="operator:fixture",
        )
    assert list_staged_source_candidates(target, kind="ceqa", record_id="large") == []



def test_altered_operator_audit_identity_fails_docket_integrity(target: Path):
    original = _stage(target)
    engine = create_database_engine(f"sqlite+pysqlite:///{target}")

    with Session(engine) as session, session.begin():
        session.execute(
            update(SourceCandidateDocketRow)
            .where(SourceCandidateDocketRow.stage_id == original.entry.stage_id)
            .values(actor_id="operator:tampered")
        )
    engine.dispose()
    with pytest.raises(CandidateDocketError, match="identity or payload changed"):
        list_staged_source_candidates(target, kind="ceqa", record_id="shared")



def test_altered_reason_text_is_detected_on_docket_readback(target: Path):
    original = _stage(target)
    engine = create_database_engine(f"sqlite+pysqlite:///{target}")

    with Session(engine) as session, session.begin():
        session.execute(
            update(SourceCandidateDocketRow)
            .where(SourceCandidateDocketRow.stage_id == original.entry.stage_id)
            .values(reason_text="An unrecorded reason")
        )
    engine.dispose()
    with pytest.raises(CandidateDocketError, match="identity or payload changed"):
        list_staged_source_candidates(target, kind="ceqa", record_id="shared")


def test_unbounded_reason_is_denied_before_effect(target: Path):
    current = preview_source_for_docket(target, kind="ceqa", record_id="shared")
    with pytest.raises(CandidateDocketError, match="stage reason"):
        stage_authorized_source_candidate(
            target, kind="ceqa", record_id="shared",
            expected_preview_id=current.preview_id,
            expected_source_sha256=current.normalized_source_sha256,
            caller_confirmation=True, reason="x" * 1_001,
        )
    assert list_staged_source_candidates(target, kind="ceqa", record_id="shared") == []



def test_existing_source_stage_cannot_be_relabelled_by_another_actor(
    target: Path,
):
    first = _stage(target)
    current = preview_source_for_docket(target, kind="ceqa", record_id="shared")
    with pytest.raises(CandidateDocketError, match="another actor or reason"):
        stage_authorized_source_candidate(
            target, kind="ceqa", record_id="shared",
            expected_preview_id=current.preview_id,
            expected_source_sha256=current.normalized_source_sha256,
            caller_confirmation=True,
            reason="Preserve one synthetic record for further review",
            operator_id="operator:another-reviewer",
        )
    retained = list_staged_source_candidates(target, kind="ceqa", record_id="shared")
    assert len(retained) == 1
    assert retained[0].actor_id == first.entry.actor_id
    assert retained[0].reason_text == first.entry.reason_text
