from datetime import date

import pytest

from constructionsight.permit_transition_models import PermitSnapshot, PermitTransitionKind
from constructionsight.permit_transition_service import detect_permit_transitions


def _snapshot(**kwargs: object) -> PermitSnapshot:
    payload = {
        "source_key": "test:source",
        "source_record_id": "permit:1",
        "permit_number": "B-1",
        "status": "applied",
        "job_value": 1000.0,
    }
    payload.update(kwargs)
    return PermitSnapshot.model_validate(payload)


def test_detect_permit_transitions_emits_new_record_for_first_snapshot() -> None:
    transitions = detect_permit_transitions(None, _snapshot())

    assert len(transitions) == 1
    assert transitions[0].transition_kind == PermitTransitionKind.NEW_RECORD
    assert transitions[0].current_value == "permit:1"


def test_detect_permit_transitions_returns_empty_for_no_change() -> None:
    current = _snapshot()
    previous = _snapshot()

    assert detect_permit_transitions(previous, current) == []


def test_detect_permit_transitions_finds_status_and_value_changes() -> None:
    previous = _snapshot(status="applied", job_value=1000.0)
    current = _snapshot(status="issued", job_value=2500.0)

    transitions = detect_permit_transitions(previous, current)
    kinds = {transition.transition_kind for transition in transitions}
    fields = {transition.field_name for transition in transitions}

    assert PermitTransitionKind.STATUS_CHANGED in kinds
    assert PermitTransitionKind.VALUE_CHANGED in kinds
    assert fields == {"status", "job_value"}


def test_detect_permit_transitions_finds_date_and_site_changes() -> None:
    previous = _snapshot(issue_date=None, site_key="site:old")
    current = _snapshot(issue_date=date(2026, 1, 1), site_key="site:new")

    transitions = detect_permit_transitions(previous, current)
    fields = {transition.field_name for transition in transitions}

    assert "issue_date" in fields
    assert "site_key" in fields


def test_detect_permit_transitions_finds_contractor_change() -> None:
    previous = _snapshot(contractor_key="contractor:old")
    current = _snapshot(contractor_key="contractor:new")

    transitions = detect_permit_transitions(previous, current)

    assert transitions[0].transition_kind == PermitTransitionKind.CONTRACTOR_CHANGED
    assert transitions[0].field_name == "contractor_key"


def test_detect_permit_transitions_rejects_mismatched_source_record() -> None:
    previous = _snapshot(source_record_id="permit:1")
    current = _snapshot(source_record_id="permit:2")

    with pytest.raises(ValueError, match="same source_record_id"):
        detect_permit_transitions(previous, current)


def test_repeated_same_value_transition_has_distinct_occurrence_identity() -> None:
    first = _snapshot(status="applied")
    second = _snapshot(status="issued")
    third = _snapshot(status="applied")
    fourth = _snapshot(status="issued")

    first_transition = detect_permit_transitions(first, second)[0]
    repeated_transition = detect_permit_transitions(third, fourth)[0]

    assert first_transition.previous_value == repeated_transition.previous_value
    assert first_transition.current_value == repeated_transition.current_value
    assert first_transition.transition_id != repeated_transition.transition_id
