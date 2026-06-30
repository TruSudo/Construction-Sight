"""Permit transition detection service."""

from __future__ import annotations

import hashlib
from datetime import date, datetime

from constructionsight.permit_transition_models import (
    PermitSnapshot,
    PermitTransition,
    PermitTransitionKind,
)


def detect_permit_transitions(
    previous: PermitSnapshot | None,
    current: PermitSnapshot,
) -> list[PermitTransition]:
    """Detect relevant transitions between permit snapshots."""

    if previous is None:
        return [_new_record_transition(current)]
    if previous.source_key != current.source_key:
        raise ValueError("permit snapshots must have the same source_key")
    if previous.source_record_id != current.source_record_id:
        raise ValueError("permit snapshots must have the same source_record_id")

    transitions: list[PermitTransition] = []
    transitions.extend(_field_transition(previous, current, "status", PermitTransitionKind.STATUS_CHANGED))
    transitions.extend(_field_transition(previous, current, "job_value", PermitTransitionKind.VALUE_CHANGED))
    transitions.extend(
        _field_transition(previous, current, "contractor_key", PermitTransitionKind.CONTRACTOR_CHANGED)
    )
    transitions.extend(
        _field_transition(
            previous,
            current,
            "contractor_group_key",
            PermitTransitionKind.CONTRACTOR_CHANGED,
        )
    )
    for field_name in ("file_date", "issue_date", "final_date", "expiration_date"):
        transitions.extend(
            _field_transition(previous, current, field_name, PermitTransitionKind.DATE_CHANGED)
        )
    transitions.extend(_field_transition(previous, current, "site_key", PermitTransitionKind.SITE_CHANGED))
    transitions.extend(
        _field_transition(
            previous,
            current,
            "work_description",
            PermitTransitionKind.DESCRIPTION_CHANGED,
        )
    )
    return transitions


def _new_record_transition(snapshot: PermitSnapshot) -> PermitTransition:
    """Return transition for a newly observed permit snapshot."""

    return PermitTransition(
        transition_id=_transition_id(
            snapshot=snapshot,
            transition_kind=PermitTransitionKind.NEW_RECORD,
            field_name="source_record_id",
            previous_value=None,
            current_value=snapshot.source_record_id,
        ),
        transition_kind=PermitTransitionKind.NEW_RECORD,
        source_key=snapshot.source_key,
        source_record_id=snapshot.source_record_id,
        field_name="source_record_id",
        previous_value=None,
        current_value=snapshot.source_record_id,
        reason="permit record was first observed by ConstructionSight",
    )


def _field_transition(
    previous: PermitSnapshot,
    current: PermitSnapshot,
    field_name: str,
    transition_kind: PermitTransitionKind,
) -> list[PermitTransition]:
    """Return a transition if one field changed."""

    previous_value = _string_value(getattr(previous, field_name))
    current_value = _string_value(getattr(current, field_name))
    if previous_value == current_value:
        return []
    return [
        PermitTransition(
            transition_id=_transition_id(
                snapshot=current,
                transition_kind=transition_kind,
                field_name=field_name,
                previous_value=previous_value,
                current_value=current_value,
            ),
            transition_kind=transition_kind,
            source_key=current.source_key,
            source_record_id=current.source_record_id,
            field_name=field_name,
            previous_value=previous_value,
            current_value=current_value,
            reason=_reason_for_transition(field_name, previous_value, current_value),
        )
    ]


def _string_value(value: object) -> str | None:
    """Return stable string representation for transition comparison."""

    if value is None:
        return None
    if isinstance(value, date | datetime):
        return value.isoformat()
    return str(value)


def _reason_for_transition(
    field_name: str,
    previous_value: str | None,
    current_value: str | None,
) -> str:
    """Return a deterministic transition reason."""

    if previous_value is None and current_value is not None:
        return f"{field_name} was added"
    if previous_value is not None and current_value is None:
        return f"{field_name} was removed"
    return f"{field_name} changed"


def _transition_id(
    *,
    snapshot: PermitSnapshot,
    transition_kind: PermitTransitionKind,
    field_name: str | None,
    previous_value: str | None,
    current_value: str | None,
) -> str:
    """Build a deterministic transition id."""

    basis = "|".join(
        [
            snapshot.source_key,
            snapshot.source_record_id,
            transition_kind.value,
            field_name or "",
            previous_value or "",
            current_value or "",
        ]
    )
    return f"permit-transition:{hashlib.sha256(basis.encode('utf-8')).hexdigest()[:16]}"
