import json

import pytest
from sqlalchemy import inspect, select

from constructionsight.contractor_identity_models import ContractorIdentityStatus
from constructionsight.contractor_identity_service import build_contractor_identity
from constructionsight.decision_record_models import DecisionKind, DecisionSourceKind
from constructionsight.decision_record_service import build_decision_record
from constructionsight.permit_transition_models import (
    PermitSnapshot,
    PermitTransition,
    PermitTransitionKind,
)
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.movement_identity_orm import (
    ContractorIdentityRecord,
    DecisionRecordRow,
    PermitSnapshotRecord,
    PermitTransitionRecord,
)
from constructionsight.storage.movement_identity_store import (
    store_contractor_identity,
    store_decision_record,
    store_permit_snapshot,
    store_permit_transition,
)


def _session_factory():
    engine = create_database_engine("sqlite:///:memory:")
    initialize_database(engine)
    return engine, session_factory(engine)


def test_movement_identity_tables_are_created() -> None:
    engine, _factory = _session_factory()

    table_names = set(inspect(engine).get_table_names())

    assert "permit_snapshots" in table_names
    assert "permit_transitions" in table_names
    assert "contractor_identities" in table_names
    assert "decision_records" in table_names


def test_store_permit_snapshot_roundtrip() -> None:
    _engine, factory = _session_factory()
    snapshot = PermitSnapshot(
        source_key="source:test",
        source_record_id="permit:1",
        permit_number="B-1",
        status="issued",
        site_key="site:test",
    )

    with managed_session(factory) as session:
        store_permit_snapshot(session, snapshot)
        session.flush()
        row = session.execute(select(PermitSnapshotRecord)).scalar_one()

        assert row.snapshot_id == snapshot.snapshot_id
        payload = json.loads(row.payload_json)
        assert payload["status"] == "issued"
        assert payload["site_key"] == "site:test"


def test_store_permit_transition_roundtrip() -> None:
    _engine, factory = _session_factory()
    previous = PermitSnapshot(
        source_key="source:test",
        source_record_id="permit:1",
        status="applied",
    )
    current = PermitSnapshot(
        source_key="source:test",
        source_record_id="permit:1",
        status="issued",
    )
    transition = PermitTransition(
        transition_kind=PermitTransitionKind.STATUS_CHANGED,
        source_key="source:test",
        source_record_id="permit:1",
        previous_snapshot_id=previous.snapshot_id,
        current_snapshot_id=current.snapshot_id,
        field_name="status",
        previous_value="applied",
        current_value="issued",
        reason="status changed",
        detected_at=current.observed_at,
    )

    with managed_session(factory) as session:
        store_permit_transition(session, transition)
        session.flush()
        row = session.execute(select(PermitTransitionRecord)).scalar_one()

        assert row.transition_kind == "status_changed"
        payload = json.loads(row.payload_json)
        assert payload["current_value"] == "issued"


def test_store_contractor_identity_roundtrip() -> None:
    _engine, factory = _session_factory()
    identity = build_contractor_identity(
        display_name="Acme Builders",
        license_number="123456",
        license_status=ContractorIdentityStatus.ACTIVE,
    )

    with managed_session(factory) as session:
        store_contractor_identity(session, identity)
        session.flush()
        row = session.execute(select(ContractorIdentityRecord)).scalar_one()

        assert row.contractor_key == identity.contractor_key
        assert row.status == "active"
        payload = json.loads(row.payload_json)
        assert payload["normalized_name"] == "ACME BUILDERS"


def test_store_decision_record_roundtrip() -> None:
    _engine, factory = _session_factory()
    decision = build_decision_record(
        source_key="decision:test",
        title="Project approval",
        source_kind=DecisionSourceKind.AGENDA,
        decision_kind=DecisionKind.APPROVAL,
        site_key="site:test",
        apn="123-456-78",
        source_url="https://example.invalid/item",
    )

    with managed_session(factory) as session:
        store_decision_record(session, decision)
        session.flush()
        row = session.execute(select(DecisionRecordRow)).scalar_one()

        assert row.decision_key == decision.decision_key
        assert row.site_key == "site:test"
        payload = json.loads(row.payload_json)
        assert payload["apn"] == "12345678"


def test_store_helpers_reject_changed_snapshot_replay() -> None:
    _engine, factory = _session_factory()
    first = PermitSnapshot(
        source_key="source:test",
        source_record_id="permit:1",
        status="applied",
    )
    with managed_session(factory) as session:
        store_permit_snapshot(session, first)
        store_permit_snapshot(session, first)
        session.flush()
        rows = session.execute(select(PermitSnapshotRecord)).scalars().all()

        assert len(rows) == 1
        assert rows[0].status == "applied"

        forged = first.model_copy(update={"status": "issued"})
        with pytest.raises(ValueError, match="immutable"):
            store_permit_snapshot(session, forged)
