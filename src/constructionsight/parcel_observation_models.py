"""Immutable parcel observations and conservative current-selection models."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from constructionsight.parcel_assurance_models import ParcelAssuranceReport
from constructionsight.parcel_core_models import ParcelCoreRecord


class ParcelObservationTimeBasis(StrEnum):
    """Clock used to compare observations from one source."""

    SOURCE_EFFECTIVE_AT = "source_effective_at"
    OBSERVED_AT = "observed_at"
    MIXED_UNCOMPARABLE = "mixed_uncomparable"


class ParcelSourceSelectionStatus(StrEnum):
    """Current-selection state for one parcel source."""

    SELECTED = "selected"
    AMBIGUOUS = "ambiguous"


class ParcelObservationDispositionStatus(StrEnum):
    """Derived position of one immutable observation in a selection report."""

    CURRENT = "current"
    CURRENT_CANDIDATE = "current_candidate"
    SUPERSEDED = "superseded"


class ParcelCurrentSelectionStatus(StrEnum):
    """Aggregate state across every supplied parcel source."""

    COMPLETE = "complete"
    REVIEW_REQUIRED = "review_required"


class ParcelLongitudinalAssuranceStatus(StrEnum):
    """Whether governed current records reached parcel assurance."""

    BUILT = "built"
    BLOCKED_REVIEW = "blocked_review"


class ParcelRecordObservation(BaseModel):
    """One complete, immutable observation of a canonical parcel record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_id: str = Field(pattern=r"^parcel-observation:[0-9a-f]{64}$")
    record_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    record: ParcelCoreRecord

    @model_validator(mode="after")
    def require_complete_integrity(self) -> ParcelRecordObservation:
        """Bind identity and digests to the complete retained record."""

        _require_aware(self.record.created_at, "parcel observation time")
        if self.record.source_updated_at is not None:
            _require_aware(self.record.source_updated_at, "source-effective time")
        payload = self.record.to_dict()
        expected_record_digest = _digest(payload)
        if self.record_digest != expected_record_digest:
            raise ValueError("parcel observation record digest mismatch")
        expected_content_digest = _digest(_content_payload(payload))
        if self.content_digest != expected_content_digest:
            raise ValueError("parcel observation content digest mismatch")
        if self.observation_id != f"parcel-observation:{expected_record_digest}":
            raise ValueError("parcel observation identity mismatch")
        return self

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe immutable observation payload."""

        return self.model_dump(mode="json")


class ParcelObservationDisposition(BaseModel):
    """Explicit current, candidate, or superseded state for one observation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_id: str = Field(pattern=r"^parcel-observation:[0-9a-f]{64}$")
    status: ParcelObservationDispositionStatus
    superseded_by_observation_ids: tuple[str, ...] = ()
    reasons: tuple[str, ...] = Field(min_length=1)

    @field_validator("superseded_by_observation_ids", "reasons")
    @classmethod
    def require_sorted_unique_values(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        """Keep explicit disposition evidence deterministic."""

        if values != tuple(sorted(set(values))):
            raise ValueError("parcel observation disposition lists must be sorted and unique")
        return values

    @model_validator(mode="after")
    def require_disposition_consistency(self) -> ParcelObservationDisposition:
        """Require supersession targets only for superseded observations."""

        if self.status is ParcelObservationDispositionStatus.SUPERSEDED:
            if not self.superseded_by_observation_ids:
                raise ValueError("superseded observations require explicit successors")
            if self.observation_id in self.superseded_by_observation_ids:
                raise ValueError("parcel observations cannot supersede themselves")
        elif self.superseded_by_observation_ids:
            raise ValueError("current observations cannot carry supersession targets")
        return self


class ParcelSourceCurrentSelection(BaseModel):
    """Explainable current selection for one source and one parcel."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_key: str = Field(min_length=1)
    status: ParcelSourceSelectionStatus
    time_basis: ParcelObservationTimeBasis
    governing_timestamp: datetime | None = None
    current_observation_id: str | None = None
    candidate_observation_ids: tuple[str, ...] = Field(min_length=1)
    dispositions: tuple[ParcelObservationDisposition, ...] = Field(min_length=1)
    requires_human_review: bool
    reasons: tuple[str, ...] = Field(min_length=1)
    limitations: tuple[str, ...] = ()

    @field_validator("governing_timestamp")
    @classmethod
    def normalize_governing_timestamp(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        """Normalize comparable selection time to UTC."""

        if value is None:
            return None
        _require_aware(value, "governing timestamp")
        return value.astimezone(UTC)

    @field_validator("candidate_observation_ids", "reasons", "limitations")
    @classmethod
    def require_sorted_unique_selection_values(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        """Keep selection evidence deterministic."""

        if values != tuple(sorted(set(values))):
            raise ValueError("parcel source selection lists must be sorted and unique")
        return values

    @model_validator(mode="after")
    def require_selection_consistency(self) -> ParcelSourceCurrentSelection:
        """Bind aggregate selection state to every observation disposition."""

        disposition_ids = [item.observation_id for item in self.dispositions]
        if disposition_ids != sorted(set(disposition_ids)):
            raise ValueError("parcel observation dispositions must be sorted and unique")
        by_status = {
            status: [
                item.observation_id
                for item in self.dispositions
                if item.status is status
            ]
            for status in ParcelObservationDispositionStatus
        }
        if self.status is ParcelSourceSelectionStatus.SELECTED:
            if self.requires_human_review:
                raise ValueError("selected parcel source cannot require timeline review")
            if self.time_basis is ParcelObservationTimeBasis.MIXED_UNCOMPARABLE:
                raise ValueError("mixed parcel times cannot produce a selected current record")
            if self.governing_timestamp is None:
                raise ValueError("selected parcel source requires a governing timestamp")
            if self.current_observation_id is None:
                raise ValueError("selected parcel source requires a current observation")
            if self.candidate_observation_ids != (self.current_observation_id,):
                raise ValueError("selected parcel source requires exactly one current candidate")
            if by_status[ParcelObservationDispositionStatus.CURRENT] != [
                self.current_observation_id
            ]:
                raise ValueError("selected parcel source requires one current disposition")
            if by_status[ParcelObservationDispositionStatus.CURRENT_CANDIDATE]:
                raise ValueError("selected parcel source cannot retain current candidates")
            for disposition in self.dispositions:
                if (
                    disposition.status is ParcelObservationDispositionStatus.SUPERSEDED
                    and disposition.superseded_by_observation_ids
                    != (self.current_observation_id,)
                ):
                    raise ValueError(
                        "superseded observations must identify the current observation"
                    )
            return self

        if not self.requires_human_review:
            raise ValueError("ambiguous parcel source must require human review")
        if self.current_observation_id is not None:
            raise ValueError("ambiguous parcel source cannot select a current observation")
        if by_status[ParcelObservationDispositionStatus.CURRENT]:
            raise ValueError("ambiguous parcel source cannot have a current disposition")
        if tuple(sorted(by_status[ParcelObservationDispositionStatus.CURRENT_CANDIDATE])) != (
            self.candidate_observation_ids
        ):
            raise ValueError("ambiguous parcel candidates must match candidate dispositions")
        if self.time_basis is ParcelObservationTimeBasis.MIXED_UNCOMPARABLE:
            if self.governing_timestamp is not None:
                raise ValueError("mixed parcel times cannot have one governing timestamp")
        elif self.governing_timestamp is None:
            raise ValueError("comparable ambiguous parcel source requires a timestamp")
        candidate_set = set(self.candidate_observation_ids)
        for disposition in self.dispositions:
            if (
                disposition.status is ParcelObservationDispositionStatus.SUPERSEDED
                and set(disposition.superseded_by_observation_ids) != candidate_set
            ):
                raise ValueError(
                    "superseded observations must identify every current candidate"
                )
        return self


class ParcelCurrentSelectionReport(BaseModel):
    """Deterministic current-selection report across supplied parcel sources."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    selection_report_id: str = Field(pattern=r"^parcel-current-selection:[0-9a-f]{64}$")
    normalized_apn: str = Field(min_length=1)
    county: str = Field(min_length=1)
    status: ParcelCurrentSelectionStatus
    source_count: int = Field(ge=1)
    current_observation_ids: tuple[str, ...]
    source_selections: tuple[ParcelSourceCurrentSelection, ...] = Field(min_length=1)
    requires_human_review: bool
    limitations: tuple[str, ...] = ()
    generated_at: datetime

    @field_validator("current_observation_ids", "limitations")
    @classmethod
    def require_sorted_unique_report_values(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        """Keep aggregate selection output deterministic."""

        if values != tuple(sorted(set(values))):
            raise ValueError("parcel current-selection lists must be sorted and unique")
        return values

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        """Require an aware report timestamp and normalize it to UTC."""

        _require_aware(value, "parcel current-selection generation time")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def require_report_consistency(self) -> ParcelCurrentSelectionReport:
        """Require aggregate state to match every source selection."""

        source_keys = [item.source_key for item in self.source_selections]
        if source_keys != sorted(set(source_keys)):
            raise ValueError("parcel source selections must be sorted and unique")
        if self.source_count != len(self.source_selections):
            raise ValueError("parcel source_count must equal source selections")
        current_ids = sorted(
            item.current_observation_id
            for item in self.source_selections
            if item.current_observation_id is not None
        )
        if self.current_observation_ids != tuple(current_ids):
            raise ValueError("current observation IDs must match source selections")
        review_required = any(
            item.requires_human_review for item in self.source_selections
        )
        if self.requires_human_review != review_required:
            raise ValueError("parcel report review state must match source selections")
        expected_status = (
            ParcelCurrentSelectionStatus.REVIEW_REQUIRED
            if review_required
            else ParcelCurrentSelectionStatus.COMPLETE
        )
        if self.status is not expected_status:
            raise ValueError("parcel current-selection status is inconsistent")
        if not review_required and len(current_ids) != self.source_count:
            raise ValueError("complete parcel selection requires one current record per source")
        expected_id = parcel_current_selection_id(
            normalized_apn=self.normalized_apn,
            county=self.county,
            status=self.status,
            source_count=self.source_count,
            current_observation_ids=self.current_observation_ids,
            source_selections=self.source_selections,
            requires_human_review=self.requires_human_review,
            limitations=self.limitations,
        )
        if self.selection_report_id != expected_id:
            raise ValueError("parcel current-selection identity mismatch")
        return self

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe selection report payload."""

        return self.model_dump(mode="json")


class ParcelLongitudinalAssuranceResult(BaseModel):
    """Selection evidence and the assurance report it did or did not authorize."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: ParcelLongitudinalAssuranceStatus
    selection: ParcelCurrentSelectionReport
    assurance_report: ParcelAssuranceReport | None = None
    limitations: tuple[str, ...] = ()

    @field_validator("limitations")
    @classmethod
    def require_sorted_unique_limitations(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        """Keep longitudinal assurance boundaries deterministic."""

        if values != tuple(sorted(set(values))):
            raise ValueError("longitudinal assurance limitations must be sorted and unique")
        return values

    @model_validator(mode="after")
    def require_assurance_consistency(self) -> ParcelLongitudinalAssuranceResult:
        """Never emit assurance from an unresolved current-selection timeline."""

        if self.status is ParcelLongitudinalAssuranceStatus.BUILT:
            if self.selection.requires_human_review or self.assurance_report is None:
                raise ValueError("built longitudinal assurance requires complete selection")
            return self
        if not self.selection.requires_human_review:
            raise ValueError("blocked longitudinal assurance requires timeline review")
        if self.assurance_report is not None:
            raise ValueError("blocked longitudinal assurance cannot carry an assurance report")
        return self

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe longitudinal assurance payload."""

        return self.model_dump(mode="json")


def parcel_record_digest(record: ParcelCoreRecord) -> str:
    """Return the complete canonical digest for a parcel record."""

    return _digest(record.to_dict())


def parcel_record_content_digest(record: ParcelCoreRecord) -> str:
    """Return parcel content identity without observation-specific identity/time."""

    return _digest(_content_payload(record.to_dict()))


def parcel_current_selection_id(
    *,
    normalized_apn: str,
    county: str,
    status: ParcelCurrentSelectionStatus,
    source_count: int,
    current_observation_ids: Sequence[str],
    source_selections: Sequence[ParcelSourceCurrentSelection],
    requires_human_review: bool,
    limitations: Sequence[str],
) -> str:
    """Return deterministic identity for complete current-selection evidence."""

    payload = {
        "county": county.strip().casefold(),
        "current_observation_ids": list(current_observation_ids),
        "limitations": list(limitations),
        "normalized_apn": normalized_apn,
        "requires_human_review": requires_human_review,
        "source_count": source_count,
        "source_selections": [
            item.model_dump(mode="json") for item in source_selections
        ],
        "status": status.value,
    }
    return f"parcel-current-selection:{_digest(payload)}"


def _content_payload(payload: dict[str, Any]) -> dict[str, Any]:
    content = dict(payload)
    content.pop("parcel_record_id", None)
    content.pop("created_at", None)
    return content


def _digest(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _require_aware(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
