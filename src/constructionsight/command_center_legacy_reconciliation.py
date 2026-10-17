"""Evidence-bound source replay from original operator records to one native worker.

Preview compares deterministic source identities across existing databases.
The source store remains read-only. Confirmed replay queues a retained snapshot
through the existing native investigation job engine, never an identity merge,
commercial lead, outreach or bid.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from constructionsight.ceqa_models import CeqaRecord
from constructionsight.intelligence.investigation_service import InvestigationService
from constructionsight.intelligence.investigation_sources import from_domain
from constructionsight.intelligence.relationship_query_service import canonical_investigation_id
from constructionsight.investigation_runtime import InvestigationRuntime
from constructionsight.operator_source_candidate import (
    SourceRecordNotFound,
    build_source_candidate_preview,
)
from constructionsight.permit_models import PermitRecord
from constructionsight.storage.database import prepare_private_database
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
        queued = runtime.enqueue_bytes(canonical, request.kind)
    finally:
        runtime.close()
    return {
        "schema_version": "constructionsight.original-native-replay-queued/v1",
        "source_entity_id": previous["source_entity_id"],
        "original_source": metadata,
        "job_id": queued.job_id,
        "job_status": queued.status,
        "worker_required": True,
        "source_identity_verified": False,
        "project_identity_verified": False,
        "outreach_authorized": False,
        "bid_authorized": False,
    }
