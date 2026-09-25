"""Scope-bound append-only staging of exactly one retained source-review preview.

Staging is not creation or approval of a scored commercial OpportunityCandidate.
The existing read-only operator HTTP server never calls this service.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import cast

import sqlalchemy
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from constructionsight.authorization_decision import AuthorizationDeniedError
from constructionsight.authorization_decision_models import authorization_digest
from constructionsight.effect_consumption import _execute_owned_effect
from constructionsight.effect_consumption_models import EffectReplayPolicy
from constructionsight.local_operator_authorization import (
    LocalAuthorizationResult,
    authorize_local_operator_operation,
)
from constructionsight.operator_dashboard_models import RecordKind, SourceCandidatePreview
from constructionsight.operator_source_candidate import build_source_candidate_preview
from constructionsight.storage.source_candidate_docket_orm import SourceCandidateDocketRow

_MAX_PREVIEW_BYTES = 1_000_000


class CandidateDocketError(ValueError):
    """Docket operation is missing a necessary precondition or fails integrity."""


class CandidateSourceChanged(CandidateDocketError):
    """The authorized normalized source has changed before protected insertion."""


class CandidateDocketEntry(BaseModel):
    """Integrity-checked one-time source-review staging result, not a lead."""

    stage_id: str = Field(min_length=1)
    preview_id: str = Field(min_length=1)
    candidate_key: str = Field(min_length=1)
    record_kind: RecordKind
    source_record_id: str = Field(min_length=1)
    normalized_source_sha256: str = Field(min_length=64, max_length=64)
    preview_payload_sha256: str = Field(min_length=64, max_length=64)
    entry_integrity_sha256: str = Field(min_length=64, max_length=64)
    actor_id: str = Field(min_length=1)
    authorization_decision_id: str = Field(min_length=1)
    authorization_audit_identity: str = Field(min_length=1)
    reason_digest: str = Field(min_length=1)
    reason_text: str = Field(min_length=1, max_length=1_000)
    recorded_at: datetime
    preview: SourceCandidatePreview
    recorded_new: bool
    commercial_lead_created: bool = False
    outreach_authorized: bool = False
    bid_authorized: bool = False


@dataclass(frozen=True)
class AuthorizedCandidateDocketResult:
    """Observed docket entry and locally recorded claimed authorization."""

    entry: CandidateDocketEntry
    authorization: LocalAuthorizationResult


def _canonical_preview(preview: SourceCandidatePreview) -> str:
    """Canonicalize only the detached, typed source-review preview."""

    payload = json.dumps(
        preview.model_dump(mode="json", round_trip=True), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    )
    if len(payload.encode("utf-8")) > _MAX_PREVIEW_BYTES:
        raise CandidateDocketError("source review preview exceeds the retention size limit")
    return payload


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _row_integrity(row: SourceCandidateDocketRow) -> str:
    """Bind every persisted docket identity and audit-metadata field to a digest."""

    fields = {
        "stage_id": row.stage_id,
        "preview_id": row.preview_id,
        "candidate_key": row.candidate_key,
        "record_kind": row.record_kind,
        "source_record_id": row.source_record_id,
        "normalized_source_sha256": row.normalized_source_sha256,
        "preview_payload_sha256": row.preview_payload_sha256,
        "actor_id": row.actor_id,
        "authorization_decision_id": row.authorization_decision_id,
        "authorization_audit_identity": row.authorization_audit_identity,
        "reason_digest": row.reason_digest,
        "reason_text": row.reason_text,
        "recorded_at": row.recorded_at,
    }
    return _sha256(
        json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    )


def _read_entry(row: SourceCandidateDocketRow, *, recorded_new: bool) -> CandidateDocketEntry:
    """Reject inconsistent or altered normalized review evidence on read."""

    if row.record_kind not in {"ceqa", "permit"}:
        raise CandidateDocketError("persisted source family is invalid")
    preview = SourceCandidatePreview.model_validate_json(row.preview_json)
    payload = _canonical_preview(preview)
    source_json = json.dumps(
        preview.source_snapshot.model_dump(mode="json", round_trip=True),
        sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
    )
    expected_candidate = "source-candidate:" + _sha256(
        json.dumps(
            [row.record_kind, row.source_record_id],
            separators=(",", ":"), ensure_ascii=False,
        )
    )
    expected_preview = "source-candidate-preview:" + _sha256(
        expected_candidate + "|" + row.normalized_source_sha256 + "|v1"
    )
    if (
        row.preview_json != payload
        or _sha256(payload) != row.preview_payload_sha256
        or _row_integrity(row) != row.entry_integrity_sha256
        or authorization_digest(
            "source-candidate-docket-reason", {"reason": row.reason_text}
        ) != row.reason_digest
        or _sha256(source_json) != row.normalized_source_sha256
        or row.candidate_key != expected_candidate
        or row.preview_id != expected_preview
        or preview.source_record.record_kind != row.record_kind
        or preview.source_snapshot.model_dump(mode="json").get(
            "ceqa_key" if row.record_kind == "ceqa" else "permit_key"
        ) != row.source_record_id
        or preview.preview_id != row.preview_id
        or preview.candidate_key != row.candidate_key
        or preview.normalized_source_sha256 != row.normalized_source_sha256
        or preview.source_record.record_id != row.source_record_id
        or preview.source_record.record_kind != row.record_kind
        or row.stage_id != "candidate-review-stage:" + row.preview_id.removeprefix(
            "source-candidate-preview:"
        )
        or preview.persisted
        or preview.commercial_lead_created
        or preview.outreach_authorized
        or preview.bid_authorized
    ):
        raise CandidateDocketError("persisted candidate-review identity or payload changed")
    return CandidateDocketEntry(
        stage_id=row.stage_id,
        preview_id=row.preview_id,
        candidate_key=row.candidate_key,
        record_kind=cast(RecordKind, row.record_kind),
        source_record_id=row.source_record_id,
        normalized_source_sha256=row.normalized_source_sha256,
        preview_payload_sha256=row.preview_payload_sha256,
        entry_integrity_sha256=row.entry_integrity_sha256,
        actor_id=row.actor_id,
        authorization_decision_id=row.authorization_decision_id,
        authorization_audit_identity=row.authorization_audit_identity,
        reason_digest=row.reason_digest,
        reason_text=row.reason_text,
        recorded_at=datetime.fromisoformat(row.recorded_at),
        preview=preview,
        recorded_new=recorded_new,
    )


def _engine_for_existing_sqlite(path: Path) -> sqlalchemy.Engine:
    """Never create a source database as a side effect of preview or staging."""

    resolved = path.resolve(strict=True)
    if not resolved.is_file():
        raise CandidateDocketError("source database must be an existing regular file")
    return sqlalchemy.create_engine(
        sqlalchemy.URL.create("sqlite+pysqlite", database=str(resolved)),
        connect_args={"timeout": 30},
    )


def _preflight(
    engine: sqlalchemy.Engine, *, kind: RecordKind, record_id: str
) -> SourceCandidatePreview:
    with Session(engine, autoflush=False) as session:
        return build_source_candidate_preview(session, kind=kind, record_id=record_id)


def preview_source_for_docket(
    database_path: Path, *, kind: RecordKind, record_id: str
) -> SourceCandidatePreview:
    """Produce a read-only exact record review and copyable optimistic identities."""

    engine = _engine_for_existing_sqlite(database_path)
    try:
        return _preflight(engine, kind=kind, record_id=record_id)
    finally:
        engine.dispose()


def list_staged_source_candidates(
    database_path: Path, *, kind: RecordKind, record_id: str, limit: int = 100
) -> list[CandidateDocketEntry]:
    """Inspect capped, integrity-checked records without changing database schema."""

    if not 1 <= limit <= 100:
        raise CandidateDocketError("docket list limit must be between 1 and 100")
    if kind not in {"ceqa", "permit"} or not record_id:
        raise CandidateDocketError("list requires one exact source-family/key pair")
    engine = _engine_for_existing_sqlite(database_path)
    try:
        if not sqlalchemy.inspect(engine).has_table(SourceCandidateDocketRow.__tablename__):
            raise CandidateDocketError("docket table is absent; explicitly initialize the schema")
        with Session(engine, autoflush=False) as session:
            rows = session.scalars(
                sqlalchemy.select(SourceCandidateDocketRow)
                .where(
                    SourceCandidateDocketRow.record_kind == kind,
                    SourceCandidateDocketRow.source_record_id == record_id,
                )
                .order_by(SourceCandidateDocketRow.id.desc())
                .limit(limit)
            ).all()
            return [_read_entry(row, recorded_new=False) for row in rows]
    finally:
        engine.dispose()


def _append_exact_entry(
    engine: sqlalchemy.Engine,
    *,
    kind: RecordKind,
    record_id: str,
    expected_preview_id: str,
    expected_source_sha256: str,
    authority: LocalAuthorizationResult,
    reason_digest: str,
    reason_text: str,
    trusted_at: datetime,
) -> CandidateDocketEntry:
    """Serialize source read and unique insert under one SQLite writer lock."""

    with engine.connect() as connection:
        try:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            with Session(bind=connection, autoflush=False) as session:
                current = build_source_candidate_preview(
                    session, kind=kind, record_id=record_id
                )
                if (
                    current.preview_id != expected_preview_id
                    or current.normalized_source_sha256 != expected_source_sha256
                ):
                    raise CandidateSourceChanged(
                        "source preview changed; inspect it again before staging"
                    )
                payload = _canonical_preview(current)
                payload_digest = _sha256(payload)
                existing = session.scalar(
                    sqlalchemy.select(SourceCandidateDocketRow).where(
                        SourceCandidateDocketRow.preview_id == current.preview_id
                    )
                )
                if existing is not None:
                    if (
                        existing.actor_id != authority.decision.actor_id
                        or existing.reason_digest != reason_digest
                    ):
                        raise CandidateDocketError(
                            "exact preview was staged under another actor or reason; "
                            "review its original docket entry instead of relabeling it"
                        )
                    if existing.preview_payload_sha256 != payload_digest:
                        raise CandidateDocketError(
                            "existing staged preview has conflicting payload identity"
                        )
                    result = _read_entry(existing, recorded_new=False)
                else:
                    row = SourceCandidateDocketRow(
                        stage_id="candidate-review-stage:" + current.preview_id.removeprefix(
                            "source-candidate-preview:"
                        ),
                        preview_id=current.preview_id,
                        candidate_key=current.candidate_key,
                        record_kind=kind,
                        source_record_id=record_id,
                        normalized_source_sha256=current.normalized_source_sha256,
                        preview_json=payload,
                        preview_payload_sha256=payload_digest,
                        entry_integrity_sha256="",
                        actor_id=authority.decision.actor_id,
                        authorization_decision_id=authority.decision.decision_id,
                        authorization_audit_identity=authority.decision.audit_identity,
                        reason_digest=reason_digest,
                        reason_text=reason_text,
                        recorded_at=trusted_at.isoformat(),
                    )
                    row.entry_integrity_sha256 = _row_integrity(row)
                    session.add(row)
                    session.flush()
                    result = _read_entry(row, recorded_new=True)
            connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise


def stage_authorized_source_candidate(
    database_path: Path,
    *,
    kind: RecordKind,
    record_id: str,
    expected_preview_id: str,
    expected_source_sha256: str,
    caller_confirmation: bool,
    reason: str,
    operator_id: str | None = None,
) -> AuthorizedCandidateDocketResult:
    """Authorize one exact source snapshot; no outreach, scoring, or approval."""

    if not caller_confirmation:
        raise AuthorizationDeniedError(
            "caller confirmation is required in addition to scope-bound authority"
        )
    if not reason.strip() or reason != reason.strip() or len(reason) > 1_000:
        raise CandidateDocketError("stage reason must be nonblank and trimmed")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_source_sha256):
        raise CandidateDocketError("expected normalized source SHA-256 must be exact")
    if not expected_preview_id or expected_preview_id != expected_preview_id.strip():
        raise CandidateDocketError("expected preview ID must be nonblank and trimmed")
    resolved = database_path.resolve(strict=True)
    engine = _engine_for_existing_sqlite(resolved)
    try:
        if not sqlalchemy.inspect(engine).has_table(SourceCandidateDocketRow.__tablename__):
            raise CandidateDocketError(
                "docket table is absent; use the existing explicit init-db command"
            )
        observed = _preflight(engine, kind=kind, record_id=record_id)
        _canonical_preview(observed)
        if (
            observed.preview_id != expected_preview_id
            or observed.normalized_source_sha256 != expected_source_sha256
        ):
            raise CandidateSourceChanged(
                "expected preview differs from current source; inspect the source again"
            )
        destination = authorization_digest(
            "source-candidate-docket-destination", {"path": str(resolved)}
        )
        state = authorization_digest(
            "source-candidate-docket-state",
            {
                "destination": destination,
                "source_family": kind,
                "source_record_id": record_id,
                "preview_id": observed.preview_id,
                "normalized_source_sha256": observed.normalized_source_sha256,
            },
        )
        scope = (
            f"destination:{destination}",
            f"family:{kind}",
            f"record:{record_id}",
            f"preview:{observed.preview_id}",
            f"source-sha256:{expected_source_sha256}",
            "effect:append-one-unapproved-review-snapshot",
        )
        authority = authorize_local_operator_operation(
            action="stage-source-candidate-review",
            resource_type="persisted-normalized-source-review",
            resource_id=observed.preview_id,
            exact_scope=scope,
            current_state_identity=state,
            expected_identity=state,
            granted_authority=("append one exact unapproved source review snapshot",),
            denied_authority=(
                "automatic recurrence",
                "commercial lead qualification",
                "external network or outreach",
                "lead score creation",
                "bid submission",
                "source record alteration",
                "review approval",
                "generic record editing",
                "unreviewed operation",
            ),
            reason=reason,
            caller_confirmation=True,
            limitations=(
                "local operator identity is not authentication",
                "review staging does not authorize commercial workflows or outbound actions",
                "only a normalized persisted source snapshot, not raw source body, is bound",
            ),
            operator_id=operator_id,
            current_revocation_identity=state,
        )
        reason_digest = authorization_digest(
            "source-candidate-docket-reason", {"reason": reason}
        )

        def effect(trusted_at: datetime) -> CandidateDocketEntry:
            return _append_exact_entry(
                engine,
                kind=kind,
                record_id=record_id,
                expected_preview_id=expected_preview_id,
                expected_source_sha256=expected_source_sha256,
                authority=authority,
                reason_digest=reason_digest,
                reason_text=reason,
                trusted_at=trusted_at,
            )

        entry = _execute_owned_effect(
            authority,
            allowance_identity=authorization_digest(
                "source-candidate-docket-allowance",
                {"destination": destination, "preview_id": observed.preview_id},
            ),
            content_identity=state,
            implementation_id=(
                "constructionsight.source_candidate_docket_service."
                "_append_exact_entry.v1"
            ),
            replay_policy=EffectReplayPolicy.EXACT,
            effect=effect,
            encode_result=lambda result: result.model_dump(mode="json", round_trip=True),
            decode_result=lambda payload: CandidateDocketEntry.model_validate(payload),
        )
        # Reservation replay alone does not prove the separately stored entry
        # survived a database restore or direct tampering. Recheck the actual
        # persisted exact entry after the owned effect returns.
        with Session(engine, autoflush=False) as session:
            row = session.scalar(
                sqlalchemy.select(SourceCandidateDocketRow).where(
                    SourceCandidateDocketRow.stage_id == entry.stage_id
                )
            )
            if row is None:
                raise CandidateDocketError(
                    "effect ledger reports staged review but database entry is absent"
                )
            persisted = _read_entry(row, recorded_new=entry.recorded_new)
            if persisted != entry:
                raise CandidateDocketError(
                    "effect ledger and staged database evidence identities disagree"
                )
        return AuthorizedCandidateDocketResult(entry=entry, authorization=authority)
    finally:
        engine.dispose()
