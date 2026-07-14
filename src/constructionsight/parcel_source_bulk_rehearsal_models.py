"""Structured, digest-bound proof records for ArcGIS bulk rehearsals."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ArcGISBulkScope(Protocol):
    """Structural scope required to bind rehearsal evidence to a live snapshot."""

    snapshot_id: str
    profile_id: str
    source_key: str
    county: str
    schema_fingerprint: str


class ParcelArcGISBulkPageEvidence(BaseModel):
    """Normalized evidence for one ordered, object-ID-only rehearsal page."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    page_evidence_id: str = Field(
        pattern=r"^parcel-arcgis-bulk-page-evidence:[0-9a-f]{64}$"
    )
    page_index: int = Field(ge=0)
    offset: int = Field(ge=0)
    requested_record_count: int = Field(ge=1)
    object_ids: tuple[int, ...] = Field(min_length=1)
    response_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    page_content_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    attempt_count: int = Field(ge=1, le=5)
    terminal_page: bool
    observed_at: datetime

    @field_validator("observed_at")
    @classmethod
    def require_aware_observed_at(cls, value: datetime) -> datetime:
        _require_aware(value, "ArcGIS bulk page observed_at")
        return value

    @model_validator(mode="after")
    def require_page_consistency(self) -> ParcelArcGISBulkPageEvidence:
        if self.offset != self.page_index * self.requested_record_count:
            raise ValueError("ArcGIS bulk page offset must match page index and size")
        if self.object_ids != tuple(sorted(set(self.object_ids))):
            raise ValueError("ArcGIS bulk page object IDs must be unique and ascending")
        if len(self.object_ids) > self.requested_record_count:
            raise ValueError("ArcGIS bulk page cannot exceed its requested record count")
        expected_content_digest = digest_json_payload(
            {
                "page_index": self.page_index,
                "offset": self.offset,
                "requested_record_count": self.requested_record_count,
                "object_ids": list(self.object_ids),
                "terminal_page": self.terminal_page,
            }
        )
        if self.page_content_digest != expected_content_digest:
            raise ValueError("ArcGIS bulk page content digest does not match normalized data")
        payload = self.model_dump(mode="json", exclude={"page_evidence_id"})
        if self.page_evidence_id != digest_identity(
            "parcel-arcgis-bulk-page-evidence", payload
        ):
            raise ValueError("ArcGIS bulk page evidence ID does not match content")
        return self

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class ParcelArcGISBulkCheckpointEvidence(BaseModel):
    """Persisted prefix state used to prove a real checkpoint boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    checkpoint_id: str = Field(
        pattern=r"^parcel-arcgis-bulk-checkpoint:[0-9a-f]{64}$"
    )
    completed_page_count: int = Field(ge=1)
    page_size: int = Field(ge=1)
    next_offset: int = Field(ge=1)
    completed_page_evidence_ids: tuple[str, ...] = Field(min_length=1)
    object_id_count: int = Field(ge=1)
    object_id_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def require_aware_created_at(cls, value: datetime) -> datetime:
        _require_aware(value, "ArcGIS bulk checkpoint created_at")
        return value

    @field_validator("completed_page_evidence_ids")
    @classmethod
    def require_canonical_page_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(
            not value.startswith("parcel-arcgis-bulk-page-evidence:")
            for value in values
        ):
            raise ValueError("ArcGIS checkpoint page evidence IDs are malformed")
        if len(values) != len(set(values)):
            raise ValueError("ArcGIS checkpoint page evidence IDs must be unique")
        return values

    @model_validator(mode="after")
    def require_checkpoint_consistency(self) -> ParcelArcGISBulkCheckpointEvidence:
        if len(self.completed_page_evidence_ids) != self.completed_page_count:
            raise ValueError("ArcGIS checkpoint must reference every completed page")
        if self.next_offset != self.completed_page_count * self.page_size:
            raise ValueError("ArcGIS checkpoint next offset must follow its completed prefix")
        payload = self.model_dump(mode="json", exclude={"checkpoint_id"})
        if self.checkpoint_id != digest_identity(
            "parcel-arcgis-bulk-checkpoint", payload
        ):
            raise ValueError("ArcGIS bulk checkpoint ID does not match content")
        return self

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class ParcelArcGISBulkResumeEvidence(BaseModel):
    """Evidence that execution resumed from one retained checkpoint."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    resume_id: str = Field(pattern=r"^parcel-arcgis-bulk-resume:[0-9a-f]{64}$")
    checkpoint_id: str = Field(
        pattern=r"^parcel-arcgis-bulk-checkpoint:[0-9a-f]{64}$"
    )
    first_resumed_page_evidence_id: str = Field(
        pattern=r"^parcel-arcgis-bulk-page-evidence:[0-9a-f]{64}$"
    )
    resumed_at: datetime

    @field_validator("resumed_at")
    @classmethod
    def require_aware_resumed_at(cls, value: datetime) -> datetime:
        _require_aware(value, "ArcGIS bulk resume resumed_at")
        return value

    @model_validator(mode="after")
    def require_resume_identity(self) -> ParcelArcGISBulkResumeEvidence:
        payload = self.model_dump(mode="json", exclude={"resume_id"})
        if self.resume_id != digest_identity("parcel-arcgis-bulk-resume", payload):
            raise ValueError("ArcGIS bulk resume ID does not match content")
        return self

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class ParcelArcGISBulkRetryEvidence(BaseModel):
    """Evidence of a bounded transient failure followed by successful recovery."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    retry_id: str = Field(pattern=r"^parcel-arcgis-bulk-retry:[0-9a-f]{64}$")
    page_evidence_id: str = Field(
        pattern=r"^parcel-arcgis-bulk-page-evidence:[0-9a-f]{64}$"
    )
    failure_kind: str = Field(min_length=1)
    failed_attempt_count: int = Field(ge=1, le=4)
    recovered_attempt_number: int = Field(ge=2, le=5)
    recovered_response_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    fault_injected: bool
    recorded_at: datetime

    @field_validator("recorded_at")
    @classmethod
    def require_aware_recorded_at(cls, value: datetime) -> datetime:
        _require_aware(value, "ArcGIS bulk retry recorded_at")
        return value

    @field_validator("failure_kind")
    @classmethod
    def require_trimmed_failure_kind(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("ArcGIS bulk retry failure kind must be trimmed")
        return value

    @model_validator(mode="after")
    def require_retry_consistency(self) -> ParcelArcGISBulkRetryEvidence:
        if self.recovered_attempt_number != self.failed_attempt_count + 1:
            raise ValueError("ArcGIS bulk retry recovery attempt must follow failures")
        payload = self.model_dump(mode="json", exclude={"retry_id"})
        if self.retry_id != digest_identity("parcel-arcgis-bulk-retry", payload):
            raise ValueError("ArcGIS bulk retry ID does not match content")
        return self

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class ParcelArcGISBulkRehearsalEvidence(BaseModel):
    """Complete structured proof behind a bulk-rehearsal manifest summary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: str = Field(
        pattern=r"^parcel-arcgis-bulk-rehearsal-evidence:[0-9a-f]{64}$"
    )
    snapshot_id: str = Field(pattern=r"^parcel-arcgis-capability:[0-9a-f]{64}$")
    profile_id: str = Field(pattern=r"^parcel-source-verification:[0-9a-f]{64}$")
    source_key: str = Field(min_length=1)
    county: str = Field(min_length=1)
    schema_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    page_size: int = Field(ge=1)
    page_evidence: tuple[ParcelArcGISBulkPageEvidence, ...] = Field(min_length=2)
    checkpoint: ParcelArcGISBulkCheckpointEvidence
    resume: ParcelArcGISBulkResumeEvidence
    retry_events: tuple[ParcelArcGISBulkRetryEvidence, ...] = Field(min_length=1)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def require_aware_created_at(cls, value: datetime) -> datetime:
        _require_aware(value, "ArcGIS bulk rehearsal evidence created_at")
        return value

    @model_validator(mode="after")
    def require_rehearsal_consistency(self) -> ParcelArcGISBulkRehearsalEvidence:
        pages = self.page_evidence
        if tuple(page.page_index for page in pages) != tuple(range(len(pages))):
            raise ValueError("ArcGIS rehearsal pages must be contiguous and ordered")
        if any(page.requested_record_count != self.page_size for page in pages):
            raise ValueError("ArcGIS rehearsal pages must use one exact page size")
        if any(page.offset != index * self.page_size for index, page in enumerate(pages)):
            raise ValueError("ArcGIS rehearsal page offsets must be contiguous")
        if any(page.terminal_page for page in pages[:-1]) or not pages[-1].terminal_page:
            raise ValueError("ArcGIS rehearsal requires exactly one final terminal page")
        if any(len(page.object_ids) != self.page_size for page in pages[:-1]):
            raise ValueError("ArcGIS nonterminal rehearsal pages must be full")

        object_ids = tuple(value for page in pages for value in page.object_ids)
        if object_ids != tuple(sorted(set(object_ids))):
            raise ValueError("ArcGIS rehearsal object IDs must be globally unique and ascending")

        checkpoint = self.checkpoint
        if checkpoint.page_size != self.page_size:
            raise ValueError("ArcGIS checkpoint page size must match rehearsal evidence")
        if checkpoint.completed_page_count >= len(pages):
            raise ValueError("ArcGIS checkpoint must precede at least one resumed page")
        completed_pages = pages[: checkpoint.completed_page_count]
        completed_ids = tuple(page.page_evidence_id for page in completed_pages)
        if checkpoint.completed_page_evidence_ids != completed_ids:
            raise ValueError("ArcGIS checkpoint must bind the exact completed page prefix")
        checkpoint_object_ids = tuple(
            value for page in completed_pages for value in page.object_ids
        )
        if checkpoint.object_id_count != len(checkpoint_object_ids):
            raise ValueError("ArcGIS checkpoint object-ID count does not match its prefix")
        if checkpoint.object_id_set_digest != digest_json_payload(
            list(checkpoint_object_ids)
        ):
            raise ValueError("ArcGIS checkpoint object-ID digest does not match its prefix")
        if completed_pages[-1].observed_at > checkpoint.created_at:
            raise ValueError(
                "ArcGIS checkpoint cannot precede its completed page prefix"
            )

        first_resumed_page = pages[checkpoint.completed_page_count]
        if self.resume.checkpoint_id != checkpoint.checkpoint_id:
            raise ValueError("ArcGIS resume evidence must reference the retained checkpoint")
        if (
            self.resume.first_resumed_page_evidence_id
            != first_resumed_page.page_evidence_id
        ):
            raise ValueError("ArcGIS resume evidence must bind the first resumed page")
        if self.resume.resumed_at < checkpoint.created_at:
            raise ValueError("ArcGIS resume cannot precede checkpoint creation")
        if first_resumed_page.observed_at < self.resume.resumed_at:
            raise ValueError("ArcGIS resumed page cannot precede the resume event")

        retry_page_ids = tuple(event.page_evidence_id for event in self.retry_events)
        expected_retry_page_ids = tuple(
            sorted(
                page.page_evidence_id
                for page in pages
                if page.attempt_count > 1
            )
        )
        if retry_page_ids != expected_retry_page_ids:
            raise ValueError(
                "ArcGIS retry evidence must cover every and only retried page"
            )
        pages_by_id = {page.page_evidence_id: page for page in pages}
        for event in self.retry_events:
            page = pages_by_id.get(event.page_evidence_id)
            if page is None:
                raise ValueError("ArcGIS retry evidence references an unknown page")
            if page.attempt_count != event.recovered_attempt_number:
                raise ValueError("ArcGIS retry attempts do not match page evidence")
            if page.response_digest != event.recovered_response_digest:
                raise ValueError("ArcGIS retry response digest does not match recovered page")
            if event.recorded_at > page.observed_at:
                raise ValueError("ArcGIS retry record cannot follow its recovered page")

        latest_evidence_time = max(
            self.resume.resumed_at,
            checkpoint.created_at,
            *(page.observed_at for page in pages),
            *(event.recorded_at for event in self.retry_events),
        )
        if self.created_at < latest_evidence_time:
            raise ValueError("ArcGIS rehearsal evidence cannot predate its proof records")

        payload = self.model_dump(mode="json", exclude={"evidence_id"})
        if self.evidence_id != digest_identity(
            "parcel-arcgis-bulk-rehearsal-evidence", payload
        ):
            raise ValueError("ArcGIS bulk rehearsal evidence ID does not match content")
        return self

    @property
    def retrieved_count(self) -> int:
        return sum(len(page.object_ids) for page in self.page_evidence)

    @property
    def unique_object_id_count(self) -> int:
        return len({value for page in self.page_evidence for value in page.object_ids})

    @property
    def duplicate_object_id_count(self) -> int:
        return self.retrieved_count - self.unique_object_id_count

    @property
    def terminal_page_observed(self) -> bool:
        return bool(self.page_evidence and self.page_evidence[-1].terminal_page)

    @property
    def checkpoint_resume_verified(self) -> bool:
        return True

    @property
    def retry_recovery_verified(self) -> bool:
        return bool(self.retry_events)

    @property
    def page_response_digests(self) -> tuple[str, ...]:
        return tuple(page.response_digest for page in self.page_evidence)

    @property
    def object_id_set_digest(self) -> str:
        object_ids = [value for page in self.page_evidence for value in page.object_ids]
        return digest_json_payload(object_ids)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def build_arcgis_bulk_page_evidence(
    *,
    page_index: int,
    page_size: int,
    object_ids: Sequence[int],
    response_digest: str,
    attempt_count: int,
    terminal_page: bool,
    observed_at: datetime,
) -> ParcelArcGISBulkPageEvidence:
    """Build one digest-bound normalized page evidence record."""

    canonical_ids = tuple(object_ids)
    content_payload = {
        "page_index": page_index,
        "offset": page_index * page_size,
        "requested_record_count": page_size,
        "object_ids": list(canonical_ids),
        "terminal_page": terminal_page,
    }
    candidate = ParcelArcGISBulkPageEvidence.model_construct(
        page_evidence_id="parcel-arcgis-bulk-page-evidence:" + ("0" * 64),
        page_index=page_index,
        offset=page_index * page_size,
        requested_record_count=page_size,
        object_ids=canonical_ids,
        response_digest=response_digest,
        page_content_digest=digest_json_payload(content_payload),
        attempt_count=attempt_count,
        terminal_page=terminal_page,
        observed_at=observed_at,
    )
    payload = candidate.model_dump(mode="json", exclude={"page_evidence_id"})
    return ParcelArcGISBulkPageEvidence.model_validate(
        {
            **payload,
            "page_evidence_id": digest_identity(
                "parcel-arcgis-bulk-page-evidence", payload
            ),
        }
    )


def build_arcgis_bulk_checkpoint_evidence(
    page_evidence: Sequence[ParcelArcGISBulkPageEvidence],
    *,
    completed_page_count: int,
    page_size: int,
    created_at: datetime,
) -> ParcelArcGISBulkCheckpointEvidence:
    """Build a checkpoint over an exact completed page prefix."""

    completed_pages = tuple(page_evidence[:completed_page_count])
    object_ids = [value for page in completed_pages for value in page.object_ids]
    candidate = ParcelArcGISBulkCheckpointEvidence.model_construct(
        checkpoint_id="parcel-arcgis-bulk-checkpoint:" + ("0" * 64),
        completed_page_count=completed_page_count,
        page_size=page_size,
        next_offset=completed_page_count * page_size,
        completed_page_evidence_ids=tuple(
            page.page_evidence_id for page in completed_pages
        ),
        object_id_count=len(object_ids),
        object_id_set_digest=digest_json_payload(object_ids),
        created_at=created_at,
    )
    payload = candidate.model_dump(mode="json", exclude={"checkpoint_id"})
    return ParcelArcGISBulkCheckpointEvidence.model_validate(
        {
            **payload,
            "checkpoint_id": digest_identity(
                "parcel-arcgis-bulk-checkpoint", payload
            ),
        }
    )


def build_arcgis_bulk_resume_evidence(
    checkpoint: ParcelArcGISBulkCheckpointEvidence,
    first_resumed_page: ParcelArcGISBulkPageEvidence,
    *,
    resumed_at: datetime,
) -> ParcelArcGISBulkResumeEvidence:
    """Build evidence linking a checkpoint to the first resumed page."""

    candidate = ParcelArcGISBulkResumeEvidence.model_construct(
        resume_id="parcel-arcgis-bulk-resume:" + ("0" * 64),
        checkpoint_id=checkpoint.checkpoint_id,
        first_resumed_page_evidence_id=first_resumed_page.page_evidence_id,
        resumed_at=resumed_at,
    )
    payload = candidate.model_dump(mode="json", exclude={"resume_id"})
    return ParcelArcGISBulkResumeEvidence.model_validate(
        {
            **payload,
            "resume_id": digest_identity("parcel-arcgis-bulk-resume", payload),
        }
    )


def build_arcgis_bulk_retry_evidence(
    page_evidence: ParcelArcGISBulkPageEvidence,
    *,
    failure_kind: str,
    failed_attempt_count: int,
    fault_injected: bool,
    recorded_at: datetime,
) -> ParcelArcGISBulkRetryEvidence:
    """Build a retry record bound to the recovered page response."""

    candidate = ParcelArcGISBulkRetryEvidence.model_construct(
        retry_id="parcel-arcgis-bulk-retry:" + ("0" * 64),
        page_evidence_id=page_evidence.page_evidence_id,
        failure_kind=failure_kind,
        failed_attempt_count=failed_attempt_count,
        recovered_attempt_number=failed_attempt_count + 1,
        recovered_response_digest=page_evidence.response_digest,
        fault_injected=fault_injected,
        recorded_at=recorded_at,
    )
    payload = candidate.model_dump(mode="json", exclude={"retry_id"})
    return ParcelArcGISBulkRetryEvidence.model_validate(
        {
            **payload,
            "retry_id": digest_identity("parcel-arcgis-bulk-retry", payload),
        }
    )


def build_arcgis_bulk_rehearsal_evidence(
    scope: ArcGISBulkScope,
    *,
    page_size: int,
    page_evidence: Sequence[ParcelArcGISBulkPageEvidence],
    checkpoint: ParcelArcGISBulkCheckpointEvidence,
    resume: ParcelArcGISBulkResumeEvidence,
    retry_events: Sequence[ParcelArcGISBulkRetryEvidence],
    created_at: datetime,
) -> ParcelArcGISBulkRehearsalEvidence:
    """Build a complete structured rehearsal evidence envelope."""

    canonical_pages = tuple(page_evidence)
    canonical_retries = tuple(sorted(retry_events, key=lambda event: event.page_evidence_id))
    candidate = ParcelArcGISBulkRehearsalEvidence.model_construct(
        evidence_id="parcel-arcgis-bulk-rehearsal-evidence:" + ("0" * 64),
        snapshot_id=scope.snapshot_id,
        profile_id=scope.profile_id,
        source_key=scope.source_key,
        county=scope.county,
        schema_fingerprint=scope.schema_fingerprint,
        page_size=page_size,
        page_evidence=canonical_pages,
        checkpoint=checkpoint,
        resume=resume,
        retry_events=canonical_retries,
        created_at=created_at,
    )
    payload = candidate.model_dump(mode="json", exclude={"evidence_id"})
    return ParcelArcGISBulkRehearsalEvidence.model_validate(
        {
            **payload,
            "evidence_id": digest_identity(
                "parcel-arcgis-bulk-rehearsal-evidence", payload
            ),
        }
    )



def assemble_arcgis_bulk_rehearsal_evidence(
    scope: ArcGISBulkScope,
    *,
    page_size: int,
    page_object_ids: Sequence[Sequence[int]],
    page_response_digests: Sequence[str],
    page_attempt_counts: Sequence[int],
    page_observed_at: Sequence[datetime],
    checkpoint_completed_page_count: int,
    checkpoint_created_at: datetime,
    resumed_at: datetime,
    retry_page_index: int,
    retry_failure_kind: str,
    retry_failed_attempt_count: int,
    retry_fault_injected: bool,
    retry_recorded_at: datetime,
    created_at: datetime,
) -> ParcelArcGISBulkRehearsalEvidence:
    """Assemble a complete evidence chain from normalized page observations."""

    page_count = len(page_object_ids)
    if page_count < 2:
        raise ValueError("ArcGIS bulk rehearsal requires at least two pages")
    if not (
        len(page_response_digests)
        == len(page_attempt_counts)
        == len(page_observed_at)
        == page_count
    ):
        raise ValueError("ArcGIS bulk rehearsal page evidence lengths must match")
    if retry_page_index < 0 or retry_page_index >= page_count:
        raise ValueError("ArcGIS retry page index is outside the rehearsal")
    if not 1 <= checkpoint_completed_page_count < page_count:
        raise ValueError(
  "ArcGIS checkpoint completed page count must precede a resumed page"
        )

    pages = tuple(
        build_arcgis_bulk_page_evidence(
  page_index=index,
  page_size=page_size,
  object_ids=page_object_ids[index],
  response_digest=page_response_digests[index],
  attempt_count=page_attempt_counts[index],
  terminal_page=index == page_count - 1,
  observed_at=page_observed_at[index],
        )
        for index in range(page_count)
    )
    checkpoint = build_arcgis_bulk_checkpoint_evidence(
        pages,
        completed_page_count=checkpoint_completed_page_count,
        page_size=page_size,
        created_at=checkpoint_created_at,
    )
    resume = build_arcgis_bulk_resume_evidence(
        checkpoint,
        pages[checkpoint_completed_page_count],
        resumed_at=resumed_at,
    )
    retry = build_arcgis_bulk_retry_evidence(
        pages[retry_page_index],
        failure_kind=retry_failure_kind,
        failed_attempt_count=retry_failed_attempt_count,
        fault_injected=retry_fault_injected,
        recorded_at=retry_recorded_at,
    )
    return build_arcgis_bulk_rehearsal_evidence(
        scope,
        page_size=page_size,
        page_evidence=pages,
        checkpoint=checkpoint,
        resume=resume,
        retry_events=(retry,),
        created_at=created_at,
    )

def digest_identity(namespace: str, payload: dict[str, Any]) -> str:
    """Return a namespaced SHA-256 identity for one canonical payload."""

    return f"{namespace}:{digest_json_payload(payload)}"


def digest_json_payload(payload: Any) -> str:
    """Return SHA-256 over deterministic compact JSON."""

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _require_aware(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
