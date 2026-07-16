"""Store helpers for movement and identity records."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from constructionsight.contractor_identity_models import ContractorIdentity
from constructionsight.decision_record_models import DecisionRecord
from constructionsight.permit_transition_models import PermitSnapshot, PermitTransition
from constructionsight.storage.movement_identity_orm import (
    ContractorIdentityRecord,
    DecisionRecordRow,
    PermitSnapshotRecord,
    PermitTransitionRecord,
)


def store_permit_snapshot(session: Session, snapshot: PermitSnapshot) -> PermitSnapshotRecord:
    """Insert or update a permit snapshot record."""

    session.flush()
    payload_json = _payload_json(snapshot.to_dict())
    existing = session.execute(
        select(PermitSnapshotRecord).where(
            PermitSnapshotRecord.snapshot_id == snapshot.snapshot_id
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = PermitSnapshotRecord(
            snapshot_id=snapshot.snapshot_id,
            source_key=snapshot.source_key,
            source_record_id=snapshot.source_record_id,
            permit_number=snapshot.permit_number,
            status=snapshot.status,
            site_key=snapshot.site_key,
            observed_at=snapshot.observed_at.isoformat(),
            payload_json=payload_json,
        )
        session.add(existing)
        return existing
    existing.source_key = snapshot.source_key
    existing.source_record_id = snapshot.source_record_id
    existing.permit_number = snapshot.permit_number
    existing.status = snapshot.status
    existing.site_key = snapshot.site_key
    existing.observed_at = snapshot.observed_at.isoformat()
    existing.payload_json = payload_json
    return existing


def store_permit_transition(
    session: Session,
    transition: PermitTransition,
) -> PermitTransitionRecord:
    """Insert or update a permit transition record."""

    session.flush()
    payload_json = _payload_json(transition.to_dict())
    existing = session.execute(
        select(PermitTransitionRecord).where(
            PermitTransitionRecord.transition_id == transition.transition_id
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = PermitTransitionRecord(
            transition_id=transition.transition_id,
            transition_kind=transition.transition_kind.value,
            source_key=transition.source_key,
            source_record_id=transition.source_record_id,
            field_name=transition.field_name,
            opportunity_relevant=transition.opportunity_relevant,
            detected_at=transition.detected_at.isoformat(),
            payload_json=payload_json,
        )
        session.add(existing)
        return existing
    existing.transition_kind = transition.transition_kind.value
    existing.source_key = transition.source_key
    existing.source_record_id = transition.source_record_id
    existing.field_name = transition.field_name
    existing.opportunity_relevant = transition.opportunity_relevant
    existing.detected_at = transition.detected_at.isoformat()
    existing.payload_json = payload_json
    return existing


def store_contractor_identity(
    session: Session,
    identity: ContractorIdentity,
) -> ContractorIdentityRecord:
    """Insert or update a contractor identity record."""

    session.flush()
    payload_json = _payload_json(identity.to_dict())
    existing = session.execute(
        select(ContractorIdentityRecord).where(
            ContractorIdentityRecord.contractor_key == identity.contractor_key
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = ContractorIdentityRecord(
            contractor_key=identity.contractor_key,
            display_name=identity.display_name,
            normalized_name=identity.normalized_name,
            source_kind=identity.source_kind.value,
            status=identity.status.value,
            confidence_score=identity.confidence_score,
            payload_json=payload_json,
        )
        session.add(existing)
        return existing
    existing.display_name = identity.display_name
    existing.normalized_name = identity.normalized_name
    existing.source_kind = identity.source_kind.value
    existing.status = identity.status.value
    existing.confidence_score = identity.confidence_score
    existing.payload_json = payload_json
    return existing


def store_decision_record(session: Session, decision: DecisionRecord) -> DecisionRecordRow:
    """Insert or update a public decision record."""

    session.flush()
    payload_json = _payload_json(decision.to_dict())
    existing = session.execute(
        select(DecisionRecordRow).where(
            DecisionRecordRow.decision_key == decision.decision_key
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = DecisionRecordRow(
            decision_key=decision.decision_key,
            source_key=decision.source_key,
            source_record_id=decision.source_record_id,
            source_kind=decision.source_kind.value,
            decision_kind=decision.decision_kind.value,
            site_key=decision.site_key,
            apn=decision.apn,
            confidence_score=decision.confidence_score,
            payload_json=payload_json,
        )
        session.add(existing)
        return existing
    existing.source_key = decision.source_key
    existing.source_record_id = decision.source_record_id
    existing.source_kind = decision.source_kind.value
    existing.decision_kind = decision.decision_kind.value
    existing.site_key = decision.site_key
    existing.apn = decision.apn
    existing.confidence_score = decision.confidence_score
    existing.payload_json = payload_json
    return existing


def _payload_json(payload: dict[str, object]) -> str:
    """Return deterministic JSON payload."""

    return json.dumps(payload, sort_keys=True)
