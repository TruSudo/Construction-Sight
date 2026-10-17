"""Evidence-bound source replay from original operator records to one native worker.

Preview compares deterministic source identities across existing databases.
The source store remains read-only. Confirmed replay queues a retained snapshot
through the existing native investigation job engine, never an identity merge,
commercial lead, outreach or bid.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from constructionsight.ceqa_models import CeqaRecord
from constructionsight.intelligence.investigation_service import InvestigationService, _identity
from constructionsight.intelligence.investigation_sources import from_domain
from constructionsight.intelligence.relationship_query_service import canonical_investigation_id
from constructionsight.intelligence.schemas import RuntimeEvent, RuntimeEventType
from constructionsight.investigation_jobs import InvestigationJobQueue, JobDefinition
from constructionsight.investigation_runtime import (
    InvestigationRuntime,
    OriginalReplayApproval,
    retain_input,
)
from constructionsight.operator_source_candidate import (
    SourceRecordNotFound,
    build_source_candidate_preview,
)
from constructionsight.permit_models import PermitRecord
from constructionsight.storage.database import managed_session, prepare_private_database
from constructionsight.storage.domain_store import CeqaStore, PermitStore
from constructionsight.storage.intelligence_store import IntelligenceStore
from constructionsight.storage.operator_read_store import create_operator_read_engine


class LegacyReplayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    kind: Literal["ceqa", "permit"]
    record_id: str = Field(min_length=1, max_length=255)
    expected_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_native_evidence_id: str | None = Field(default=None, max_length=255)
    caller_confirmation: Literal[True]
    review_reason: str = Field(min_length=10, max_length=2000)


def _source(
    operator_database: Path | None, *, kind: Literal["ceqa", "permit"], record_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if operator_database is None:
        raise ValueError("original operator source database is not configured")
    if operator_database.is_symlink() or not operator_database.is_file():
        raise ValueError("original operator database must be an existing regular file")
    engine = create_operator_read_engine(operator_database)
    try:
        with Session(engine, autoflush=False) as session:
            try:
                original = build_source_candidate_preview(
                    session, kind=kind, record_id=record_id
                )
            except SourceRecordNotFound as exc:
                raise ValueError("original exact source record was not found") from exc
            record = (
                CeqaStore(session).get(record_id) if kind == "ceqa"
                else PermitStore(session).get(record_id)
            )
            if record is None:
                raise ValueError("original exact source record disappeared")
            raw = record.model_dump(mode="json", round_trip=True)
            return {
                "kind": kind, "record_id": record_id,
                "source_sha256": original.normalized_source_sha256,
                "preview_id": original.preview_id,
            }, raw
    finally:
        engine.dispose()


def _native(
    directory: Path, *, kind: Literal["ceqa", "permit"], raw: dict[str, Any],
) -> dict[str, Any]:
    observation = from_domain(
        CeqaRecord.model_validate(raw) if kind == "ceqa"
        else PermitRecord.model_validate(raw)
    )
    db = directory / "investigations.sqlite3"
    base: dict[str, Any] = {
        "source_entity_id": observation.source_entity_id,
        "unreviewed_investigation_id": observation.investigation_id,
        "expected_evidence_id": observation.evidence.evidence_id,
        "native_evidence_id": None,
        "canonical_investigation_id": None,
        "worker_event_cursor": None,
        "native_state": "not_in_native_store",
        "independent_project_identity_verified": False,
        "commercial_authority_granted": False,
    }
    if not db.exists() and not db.is_symlink():
        return base
    prepare_private_database(db, create=False)
    engine = create_operator_read_engine(db)
    try:
        with Session(engine, autoflush=False) as session:
            store = IntelligenceStore(session)
            base["worker_event_cursor"] = store.runtime_event_cursor()
            entity = store.get_entity(observation.source_entity_id)
            if entity is None:
                return base
            current = InvestigationService(store).current_observation(
                observation.source_entity_id
            )
            base["native_evidence_id"] = current.evidence.evidence_id
            base["canonical_investigation_id"] = canonical_investigation_id(
                store, observation.investigation_id
            )
            base["native_state"] = (
                "exact_observation_already_retained"
                if current.evidence.evidence_id == observation.evidence.evidence_id
                else "current_observation_disagrees_requires_review"
            )
            return base
    finally:
        engine.dispose()


def preview_legacy_reconciliation(
    directory: Path, operator_database: Path | None, *,
    kind: Literal["ceqa", "permit"], record_id: str,
) -> dict[str, Any]:
    """Inspect exact original source evidence and its deterministic native identity."""

    metadata, raw = _source(operator_database, kind=kind, record_id=record_id)
    state = _native(directory, kind=kind, raw=raw)
    return {
        "schema_version": "constructionsight.original-native-reconciliation/v1",
        "available": True, "read_only": True,
        "original_source": metadata, **state,
        "replay_eligible": state["native_state"] == "not_in_native_store",
        "replay_means": "queued_unverified_source_observation_only",
        "no_network_collection": True,
        "no_commercial_authorization": True,
    }


def enqueue_legacy_reconciliation(
    directory: Path, operator_database: Path | None, payload: dict[str, Any],
) -> dict[str, Any]:
    """Queue only an exactly reviewed missing source, never overwrite existing knowledge."""

    request = LegacyReplayRequest.model_validate(payload)
    previous = preview_legacy_reconciliation(
        directory, operator_database, kind=request.kind, record_id=request.record_id
    )
    if previous["original_source"]["source_sha256"] != request.expected_source_sha256:
        raise ValueError("original source changed; inspect the current evidence again")
    if previous["native_evidence_id"] != request.expected_native_evidence_id:
        raise ValueError("canonical source evidence changed; inspect again")
    if not previous["replay_eligible"]:
        raise ValueError("source already present or contradictory; review native evidence first")
    metadata, raw = _source(
        operator_database, kind=request.kind, record_id=request.record_id
    )
    canonical = json.dumps(raw, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False, allow_nan=False).encode("utf-8")
    if hashlib.sha256(canonical).hexdigest() != request.expected_source_sha256:
        raise ValueError("source changed during replay selection")
    runtime = InvestigationRuntime(directory)
    try:
        # A bounded, confirmed approval is included in the immutable job
        # definition, and a dedicated audit event commits in the SAME SQLite
        # transaction as the queued job. Neither a failed insert nor a stale
        # source can leave a misleading accepted approval receipt.
        observation = from_domain(
            CeqaRecord.model_validate(raw) if request.kind == "ceqa"
            else PermitRecord.model_validate(raw)
        )
        approval = OriginalReplayApproval(
            kind=request.kind,
            record_id=request.record_id,
            source_sha256=request.expected_source_sha256,
            source_entity_id=observation.source_entity_id,
            expected_evidence_id=observation.evidence.evidence_id,
            review_reason=request.review_reason,
            local_user_confirmation=True,
        )
        reference = retain_input(runtime.directory, canonical)
        definition = JobDefinition(
            kind="retained_json_replay",
            inputs={
                "input": reference.model_dump(),
                "source_kind": request.kind,
                "offset": 0,
                "row_count": 1,
                "original_replay_approval": approval.model_dump(mode="json"),
            },
        )
        with managed_session(runtime.queue.factory) as session:
            runtime.queue.begin_write(session)
            store = IntelligenceStore(session)
            if store.get_entity(approval.source_entity_id) is not None:
                raise ValueError("source changed in native investigation; re-review required")
            queued = runtime.queue.enqueue_in_transaction(store, definition)
            audit_id = _identity("event:original-source-replay-approval", queued.job_id)
            store.add_runtime_event(
                RuntimeEvent(
                    event_id=audit_id,
                    event_type=RuntimeEventType.BACKGROUND_JOB_QUEUED,
                    source_service="original_source_replay_approval",
                    correlation_id=queued.job_id,
                    created_at=datetime.fromtimestamp(queued.created_at, UTC),
                    source_record_refs=[approval.source_entity_id],
                    payload=approval.model_dump(mode="json"),
                    message="Original exact source replay reviewed and queued; no identity approval.",
                )
            )
    finally:
        runtime.close()
    return {
        "schema_version": "constructionsight.original-native-replay-queued/v1",
        "source_entity_id": previous["source_entity_id"],
        "approval_audit_event_id": audit_id,
        "approval_audit_retained": True,
        "original_source": metadata,
        "job_id": queued.job_id,
        "job_status": queued.status,
        "worker_required": True,
        "source_identity_verified": False,
        "project_identity_verified": False,
        "outreach_authorized": False,
        "bid_authorized": False,
    }


def original_source_replay_audit(directory: Path, *, job_id: str) -> dict[str, Any]:
    """Read one exact immutable approval and the CURRENT durable worker state."""

    if (
        not job_id.startswith("job:investigation:")
        or len(job_id) > 255
        or any(ord(char) < 32 or ord(char) == 127 for char in job_id)
    ):
        raise ValueError("invalid original replay job identity")
    database = prepare_private_database(directory / "investigations.sqlite3", create=False)
    engine = create_operator_read_engine(database)
    try:
        with Session(engine, autoflush=False) as session:
            store = IntelligenceStore(session)
            audit_id = _identity("event:original-source-replay-approval", job_id)
            audit = store.get_runtime_event(audit_id)
            if (
                audit is None
                or audit.source_service != "original_source_replay_approval"
                or audit.correlation_id != job_id
            ):
                raise ValueError("original replay approval receipt not found")
            approval = OriginalReplayApproval.model_validate(audit.payload)
            job = InvestigationJobQueue(engine).current(store, job_id)
            if (
                job is None or job.definition.kind != "retained_json_replay"
                or job.definition.inputs.get("original_replay_approval")
                != approval.model_dump(mode="json")
            ):
                raise ValueError("original replay approval lost its exact job lineage")
            return {
                "schema_version": "constructionsight.original-replay-audit/v1",
                "audit_event_id": audit_id,
                "approval_retained_at": audit.created_at.isoformat(),
                "approval": approval.model_dump(mode="json"),
                "job_id": job_id,
                "job_status": job.status,
                "job_error_code": job.error_code,
                "job_result": job.result,
                "read_only": True,
                "project_identity_verified": False,
                "commercial_authority_granted": False,
            }
    finally:
        engine.dispose()
