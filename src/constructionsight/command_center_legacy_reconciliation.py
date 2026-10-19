"""Evidence-bound source replay from original operator records to one native worker.

Preview compares deterministic source identities across existing databases.
The source store remains read-only. Confirmed replay queues a retained snapshot
through the existing native investigation job engine, never an identity merge,
commercial lead, outreach or bid.
"""

from __future__ import annotations

import hashlib
import json
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from constructionsight.ceqa_models import CeqaRecord
from constructionsight.intelligence.investigation_service import InvestigationService, _identity
from constructionsight.intelligence.investigation_sources import (
    from_domain,
    normalize_retained_record,
)
from constructionsight.intelligence.relationship_query_service import canonical_investigation_id
from constructionsight.intelligence.schemas import RuntimeEvent, RuntimeEventType
from constructionsight.investigation_jobs import InvestigationJobQueue, JobDefinition
from constructionsight.investigation_runtime import (
    MAX_INPUT_BYTES,
    InvestigationRuntime,
    OriginalReplayApproval,
    retain_input,
)
from constructionsight.operator_source_candidate import (
    SourceRecordNotFound,
    build_source_candidate_preview,
)
from constructionsight.permit_models import PermitRecord
from constructionsight.storage.database import (
    ensure_database_transaction,
    managed_session,
    prepare_private_database,
)
from constructionsight.storage.domain_store import CeqaStore, PermitStore
from constructionsight.storage.intelligence_store import IntelligenceStore
from constructionsight.storage.operator_read_store import (
    create_operator_read_engine,
    read_project_page,
)


class LegacyReplayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    kind: Literal["ceqa", "permit"]
    record_id: str = Field(min_length=1, max_length=255)
    expected_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_native_evidence_id: str | None = Field(default=None, max_length=255)
    action: Literal["retain_missing", "retain_revision"] = "retain_missing"
    caller_confirmation: Literal[True]
    review_reason: str = Field(min_length=10, max_length=2000)

    @field_validator("caller_confirmation", mode="before")
    @classmethod
    def exact_confirmation(cls, value: Any) -> Literal[True]:
        if value is not True:
            raise ValueError("explicit boolean confirmation is required")
        return True


class LegacyReplayScope(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    kind: Literal["all", "ceqa", "permit"] = "all"
    county: Literal["", "San Bernardino", "Riverside"] = ""
    query: str = Field(default="", max_length=200)
    offset: int = Field(default=0, ge=0, le=1_000_000)
    limit: int = Field(default=25, ge=1, le=25)


class LegacyReplayBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    scope: LegacyReplayScope
    expected_plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    caller_confirmation: Literal[True]
    review_reason: str = Field(min_length=10, max_length=2000)

    @field_validator("caller_confirmation", mode="before")
    @classmethod
    def exact_confirmation(cls, value: Any) -> Literal[True]:
        if value is not True:
            raise ValueError("explicit boolean confirmation is required")
        return True


def _canonical(raw: dict[str, Any]) -> bytes:
    return json.dumps(raw, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _require_separate_original(directory: Path, database: Path | None) -> None:
    native = directory / "investigations.sqlite3"
    if database is not None and database.exists() and native.exists() and database.samefile(native):
        raise ValueError("original source and native investigation databases must be separate")


def _source_metadata(session: Session, record: CeqaRecord | PermitRecord) -> dict[str, Any]:
    kind: Literal["ceqa", "permit"] = "ceqa" if isinstance(record, CeqaRecord) else "permit"
    record_id = record.ceqa_key if isinstance(record, CeqaRecord) else record.permit_key
    preview = build_source_candidate_preview(session, kind=kind, record_id=record_id)
    if preview.normalized_source_sha256 != hashlib.sha256(
        _canonical(record.model_dump(mode="json", round_trip=True))
    ).hexdigest():
        raise ValueError("original source changed during selection")
    return {
        "kind": kind, "record_id": record_id, "candidate_key": preview.candidate_key,
        "source_sha256": preview.normalized_source_sha256, "preview_id": preview.preview_id,
    }


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
            ensure_database_transaction(session)
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
                "candidate_key": original.candidate_key,
                "source_sha256": original.normalized_source_sha256,
                "preview_id": original.preview_id,
            }, raw
    finally:
        engine.dispose()


def _native_state(
    *, kind: Literal["ceqa", "permit", "parcel"], raw: dict[str, Any],
    store: IntelligenceStore | None,
) -> dict[str, Any]:
    observation = normalize_retained_record(kind, raw)
    base: dict[str, Any] = {
        "source_entity_id": observation.source_entity_id,
        "unreviewed_investigation_id": observation.investigation_id,
        "expected_evidence_id": observation.evidence.evidence_id,
        "native_evidence_id": None, "canonical_investigation_id": None,
        "worker_event_cursor": store.runtime_event_cursor() if store else None,
        "native_state": "not_in_native_store",
        "source_effective_at": observation.effective_at.isoformat(),
        "native_effective_at": None,
        "revision_replay_eligible": False,
        "independent_project_identity_verified": False,
        "commercial_authority_granted": False,
    }
    if store is None or store.get_entity(observation.source_entity_id) is None:
        return base
    current = InvestigationService(store).current_observation(observation.source_entity_id)
    base.update(
        native_effective_at=current.effective_at.isoformat(),
        native_evidence_id=current.evidence.evidence_id,
        canonical_investigation_id=canonical_investigation_id(store, observation.investigation_id),
        native_state=(
            "exact_observation_already_retained"
            if current.evidence.evidence_id == observation.evidence.evidence_id
            else "current_observation_disagrees_requires_review"
        ),
        revision_replay_eligible=(
            current.evidence.evidence_id != observation.evidence.evidence_id
            and observation.effective_at >= current.effective_at
            and store.get_runtime_event(observation.receipt_id) is None
        ),
    )
    return base


def _native(
    directory: Path, *, kind: Literal["ceqa", "permit", "parcel"], raw: dict[str, Any],
) -> dict[str, Any]:
    db = directory / "investigations.sqlite3"
    if not db.exists() and not db.is_symlink():
        return _native_state(kind=kind, raw=raw, store=None)
    prepare_private_database(db, create=False)
    engine = create_operator_read_engine(db)
    try:
        with Session(engine, autoflush=False) as session:
            ensure_database_transaction(session)
            return _native_state(kind=kind, raw=raw, store=IntelligenceStore(session))
    finally:
        engine.dispose()


def preview_legacy_reconciliation(
    directory: Path, operator_database: Path | None, *,
    kind: Literal["ceqa", "permit"], record_id: str,
) -> dict[str, Any]:
    """Inspect exact original source evidence and its deterministic native identity."""

    _require_separate_original(directory, operator_database)
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
    """Queue an exact reviewed snapshot against absent or explicitly reviewed prior evidence."""

    request = LegacyReplayRequest.model_validate(payload)
    previous = preview_legacy_reconciliation(
        directory, operator_database, kind=request.kind, record_id=request.record_id
    )
    if previous["original_source"]["source_sha256"] != request.expected_source_sha256:
        raise ValueError("original source changed; inspect the current evidence again")
    if previous["native_evidence_id"] != request.expected_native_evidence_id:
        raise ValueError("canonical source evidence changed; inspect again")
    revision = request.action == "retain_revision"
    if revision and not previous["revision_replay_eligible"]:
        raise ValueError(
            "source revision is unchanged, historical or requires fresh evidence review"
        )
    if not revision and not previous["replay_eligible"]:
        raise ValueError("source already present or contradictory; review native evidence first")
    metadata, raw = _source(
        operator_database, kind=request.kind, record_id=request.record_id
    )
    canonical = json.dumps(raw, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False, allow_nan=False).encode("utf-8")
    if hashlib.sha256(canonical).hexdigest() != request.expected_source_sha256:
        raise ValueError("source changed during replay selection")
    jobs: list[dict[str, Any]] = _queue_sources(
        directory, [(metadata, raw)], request.review_reason,
        previous_evidence_id=previous["native_evidence_id"] if revision else None,
    )["jobs"]
    return jobs[0]


def _queue_sources(
    directory: Path, sources: list[tuple[dict[str, Any], dict[str, Any]]], reason: str,
    *, batch_plan: dict[str, Any] | None = None,
    previous_evidence_id: str | None = None,
) -> dict[str, Any]:
    """The single-source and scoped paths share one atomic job/approval boundary."""
    if not 1 <= len(sources) <= 25:
        raise ValueError("reviewed replay must contain between 1 and 25 source observations")
    if previous_evidence_id is not None and len(sources) != 1:
        raise ValueError("original revisions require individual source review")
    canonical_sources = [(metadata, raw, _canonical(raw)) for metadata, raw in sources]
    if sum(len(content) for _, _, content in canonical_sources) > MAX_INPUT_BYTES:
        raise ValueError("reviewed source page exceeds the total retained input size limit")
    runtime = InvestigationRuntime(directory)
    receipts: list[dict[str, Any]] = []
    try:
        prepared = []
        for metadata, raw, content in canonical_sources:
            if hashlib.sha256(content).hexdigest() != metadata["source_sha256"]:
                raise ValueError("source changed during replay selection")
            observation = normalize_retained_record(metadata["kind"], raw)
            approval = OriginalReplayApproval(
                kind=metadata["kind"], record_id=metadata["record_id"],
                source_sha256=metadata["source_sha256"],
                source_entity_id=observation.source_entity_id,
                expected_evidence_id=observation.evidence.evidence_id,
                previous_evidence_id=previous_evidence_id,
                review_reason=reason, local_user_confirmation=True,
            )
            reference = retain_input(runtime.directory, content)
            definition = JobDefinition(kind="retained_json_replay", inputs={
                "input": reference.model_dump(), "source_kind": metadata["kind"],
                "offset": 0, "row_count": 1,
                "original_replay_approval": approval.retained_payload(),
            })
            prepared.append((metadata, approval, definition, raw))
        with managed_session(runtime.queue.factory) as session:
            runtime.queue.begin_write(session)
            store = IntelligenceStore(session)
            for metadata, approval, definition, raw in prepared:
                state = _native_state(kind=metadata["kind"], raw=raw, store=store)
                if previous_evidence_id is None:
                    if state["native_evidence_id"] is not None:
                        raise ValueError(
                            "source changed in native investigation; re-review required"
                        )
                elif (
                    state["native_evidence_id"] != previous_evidence_id
                    or not state["revision_replay_eligible"]
                ):
                    raise ValueError("native evidence changed; re-review the original revision")
                pending = runtime.queue.pending_original_replay(store, approval.source_entity_id)
                if pending is not None and pending.definition != definition:
                    raise ValueError(
                        "source already has a pending reviewed replay; inspect its approval first"
                    )
                queued = runtime.queue.enqueue_in_transaction(store, definition)
                audit_id = _identity("event:original-source-replay-approval", queued.job_id)
                store.add_runtime_event(RuntimeEvent(
                    event_id=audit_id, event_type=RuntimeEventType.BACKGROUND_JOB_QUEUED,
                    source_service="original_source_replay_approval", correlation_id=queued.job_id,
                    created_at=datetime.fromtimestamp(queued.created_at, UTC),
                    source_record_refs=[approval.source_entity_id],
                    payload=approval.retained_payload(),
                    message=("Original exact source replay reviewed and queued; "
                             "no identity approval."),
                ))
                receipts.append({
                    "schema_version": "constructionsight.original-native-replay-queued/v1",
                    "source_entity_id": approval.source_entity_id,
                    "approval_audit_event_id": audit_id, "approval_audit_retained": True,
                    "original_source": metadata, "job_id": queued.job_id,
                    "job_status": queued.status, "worker_required": True,
                    "source_identity_verified": False, "project_identity_verified": False,
                    "outreach_authorized": False, "bid_authorized": False,
                    **({"reconciliation_action": "retain_revision",
                        "previous_native_evidence_id": previous_evidence_id}
                       if previous_evidence_id is not None else {}),
                })
            batch_id = None
            if batch_plan is not None:
                batch_id = _identity("event:original-source-batch-approval", {
                    "plan_sha256": batch_plan["plan_sha256"], "review_reason": reason,
                })
                store.add_runtime_event(RuntimeEvent(
                    event_id=batch_id, event_type=RuntimeEventType.BACKGROUND_JOB_QUEUED,
                    source_service="original_source_replay_batch_approval", correlation_id=batch_id,
                    created_at=datetime.fromtimestamp(queued.created_at, UTC),
                    source_record_refs=[r["source_entity_id"] for r in receipts],
                    payload={"plan": batch_plan, "review_reason": reason,
                             "local_user_confirmation": True,
                             "job_ids": [r["job_id"] for r in receipts]},
                    message=("Reviewed bounded original source page queued; "
                             "no project or sales authority."),
                ))
    finally:
        runtime.close()
    return {"jobs": receipts, "batch_approval_audit_event_id": batch_id}


def _scoped_reconciliation(
    directory: Path, operator_database: Path | None, scope: LegacyReplayScope,
) -> tuple[dict[str, Any], list[tuple[dict[str, Any], dict[str, Any]]]]:
    if operator_database is None:
        raise ValueError("original operator source database is not configured")
    if operator_database.is_symlink() or not operator_database.is_file():
        raise ValueError("original operator database must be an existing regular file")
    _require_separate_original(directory, operator_database)
    with ExitStack() as stack:
        original_engine = create_operator_read_engine(operator_database)
        stack.callback(original_engine.dispose)
        original = stack.enter_context(Session(original_engine, autoflush=False))
        ensure_database_transaction(original)
        records, total = read_project_page(
            original, kind=scope.kind, county=scope.county, query=scope.query.strip(),
            offset=scope.offset, limit=scope.limit,
        )
        store: IntelligenceStore | None = None
        database = directory / "investigations.sqlite3"
        if database.exists() or database.is_symlink():
            prepare_private_database(database, create=False)
            native_engine = create_operator_read_engine(database)
            stack.callback(native_engine.dispose)
            native = stack.enter_context(Session(native_engine, autoflush=False))
            ensure_database_transaction(native)
            store = IntelligenceStore(native)
        items = []
        eligible = []
        byte_count = 0
        for record in records:
            metadata = _source_metadata(original, record)
            raw = record.model_dump(mode="json", round_trip=True)
            state = _native_state(
                kind="ceqa" if isinstance(record, CeqaRecord) else "permit", raw=raw, store=store,
            )
            # Unrelated worker activity does not change this exact source review.
            state.pop("worker_event_cursor")
            missing = state["native_state"] == "not_in_native_store"
            items.append({"original_source": metadata, "title": (
                record.title if isinstance(record, CeqaRecord) else record.permit_number
            ), **state, "replay_eligible": missing})
            if missing:
                eligible.append((metadata, raw))
                byte_count += len(_canonical(raw))
        if byte_count > MAX_INPUT_BYTES:
            raise ValueError("source page exceeds total retained input size; choose a smaller page")
        core = {
            "scope": scope.model_dump(mode="json"), "total_source_records": total,
            "items": items, "returned": len(items), "eligible_count": len(eligible),
            "already_retained_count": sum(
                item["native_state"] == "exact_observation_already_retained" for item in items
            ),
            "requires_review_count": sum(
                item["native_state"] == "current_observation_disagrees_requires_review"
                for item in items
            ),
            "has_more": scope.offset + len(records) < total,
            "next_offset": (
                scope.offset + len(records) if scope.offset + len(records) < total else None
            ),
        }
        return {
            "schema_version": "constructionsight.original-native-reconciliation-page/v1",
            **core, "plan_sha256": hashlib.sha256(_canonical(core)).hexdigest(),
            "read_only": True, "worker_required": True,
            "no_network_collection": True, "commercial_authority_granted": False,
            "meaning": (
                "One bounded source page, not proof of complete scope migration. "
                "Review subsequent pages and rescan after source changes. "
                "Existing contradictory observations remain held for individual review."
            ),
        }, eligible


def preview_legacy_reconciliation_batch(
    directory: Path, operator_database: Path | None, scope: dict[str, Any],
) -> dict[str, Any]:
    plan, _ = _scoped_reconciliation(
        directory, operator_database, LegacyReplayScope.model_validate(scope)
    )
    return plan


def enqueue_legacy_reconciliation_batch(
    directory: Path, operator_database: Path | None, payload: dict[str, Any],
) -> dict[str, Any]:
    request = LegacyReplayBatchRequest.model_validate(payload)
    plan, sources = _scoped_reconciliation(directory, operator_database, request.scope)
    if plan["plan_sha256"] != request.expected_plan_sha256:
        raise ValueError("source page or native evidence changed; inspect the current page again")
    if not sources:
        raise ValueError("this reviewed source page has no eligible missing observations")
    receipt = _queue_sources(directory, sources, request.review_reason, batch_plan=plan)
    return {
        "schema_version": "constructionsight.original-native-batch-queued/v1",
        "scope": plan["scope"], "approved_plan_sha256": plan["plan_sha256"],
        **receipt, "queued_count": len(receipt["jobs"]),
        "already_retained_count": plan["already_retained_count"],
        "requires_review_count": plan["requires_review_count"],
        "has_more": plan["has_more"], "next_offset": plan["next_offset"],
        "worker_required": True, "project_identity_verified": False,
        "commercial_authority_granted": False, "source_records_mutated": False,
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
                != approval.retained_payload()
            ):
                raise ValueError("original replay approval lost its exact job lineage")
            return {
                "schema_version": "constructionsight.original-replay-audit/v1",
                "audit_event_id": audit_id,
                "approval_retained_at": audit.created_at.isoformat(),
                "approval": approval.retained_payload(),
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
