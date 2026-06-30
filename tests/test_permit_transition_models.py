from datetime import date

import pytest
from pydantic import ValidationError

from constructionsight.permit_transition_models import (
    PermitSnapshot,
    PermitTransition,
    PermitTransitionKind,
)


def test_permit_snapshot_requires_some_signal() -> None:
    with pytest.raises(ValidationError):
        PermitSnapshot(
            snapshot_id="snapshot:test",
            source_key="test:source",
            source_record_id="permit:1",
        )


def test_permit_snapshot_accepts_status_signal() -> None:
    snapshot = PermitSnapshot(
        snapshot_id="snapshot:test",
        source_key="test:source",
        source_record_id="permit:1",
        status="issued",
    )

    assert snapshot.status == "issued"


def test_permit_snapshot_rejects_duplicate_limitations() -> None:
    with pytest.raises(ValidationError):
        PermitSnapshot(
            snapshot_id="snapshot:test",
            source_key="test:source",
            source_record_id="permit:1",
            status="issued",
            limitations=["x", "x"],
        )


def test_non_new_transition_requires_field_name() -> None:
    with pytest.raises(ValidationError):
        PermitTransition(
            transition_id="permit-transition:test",
            transition_kind=PermitTransitionKind.STATUS_CHANGED,
            source_key="test:source",
            source_record_id="permit:1",
            reason="status changed",
        )


def test_new_transition_can_serialize_to_dict() -> None:
    transition = PermitTransition(
        transition_id="permit-transition:test",
        transition_kind=PermitTransitionKind.NEW_RECORD,
        source_key="test:source",
        source_record_id="permit:1",
        reason="new record",
        current_value="permit:1",
    )

    payload = transition.to_dict()

    assert payload["transition_kind"] == "new_record"


def test_permit_snapshot_serializes_dates() -> None:
    snapshot = PermitSnapshot(
        snapshot_id="snapshot:test",
        source_key="test:source",
        source_record_id="permit:1",
        permit_number="B-1",
        issue_date=date(2026, 1, 1),
    )

    assert snapshot.to_dict()["issue_date"] == "2026-01-01"
