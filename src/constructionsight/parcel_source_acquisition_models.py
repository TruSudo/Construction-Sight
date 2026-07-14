"""Digest-bound ArcGIS acquisition capability and proof models."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from constructionsight.parcel_source_bulk_rehearsal_models import (
    ParcelArcGISBulkRehearsalEvidence,
)


class ParcelArcGISProbeKind(StrEnum):
    """Bounded query operations required before a bulk rehearsal."""

    COUNT = "count"
    INITIAL_PAGE = "initial_page"
    NEXT_PAGE = "next_page"
    REPLAY_PAGE = "replay_page"


class ParcelArcGISAcquisitionStatus(StrEnum):
    """Acquisition maturity without conflating advertised and proven behavior."""

    METADATA_ONLY = "metadata_only"
    BOUNDED_QUERY_VERIFIED = "bounded_query_verified"
    BULK_REHEARSAL_VERIFIED = "bulk_rehearsal_verified"
    BLOCKED = "blocked"


class ParcelArcGISAcquisitionGapCode(StrEnum):
    """Reasons a source cannot advance to a complete bulk rehearsal."""

    QUERY_NOT_ADVERTISED = "query_not_advertised"
    COUNT_NOT_ADVERTISED = "count_not_advertised"
    ORDERING_NOT_ADVERTISED = "ordering_not_advertised"
    PAGINATION_NOT_ADVERTISED = "pagination_not_advertised"
    UNIQUE_OBJECT_ID_UNVERIFIED = "unique_object_id_unverified"
    COUNT_PROBE_MISSING = "count_probe_missing"
    PAGE_PROBE_MISSING = "page_probe_missing"
    PAGE_REPLAY_MISSING = "page_replay_missing"
    SCHEMA_DRIFT = "schema_drift"
    PAGE_SEQUENCE_INVALID = "page_sequence_invalid"
    BULK_REHEARSAL_MISSING = "bulk_rehearsal_missing"


class ParcelArcGISFieldDefinition(BaseModel):
    """Canonical projection of one ArcGIS service field definition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    field_type: str = Field(min_length=1)
    nullable: bool | None = None
    length: int | None = Field(default=None, ge=0)


class ParcelArcGISCapabilitySnapshot(BaseModel):
    """Immutable metadata observation of advertised ArcGIS capabilities."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_id: str = Field(pattern=r"^parcel-arcgis-capability:[0-9a-f]{64}$")
    profile_id: str = Field(pattern=r"^parcel-source-verification:[0-9a-f]{64}$")
    source_key: str = Field(min_length=1)
    county: str = Field(min_length=1)
    layer_url: str = Field(min_length=1)
    observed_at: datetime
    service_version: str = Field(min_length=1)
    geometry_type: str = Field(min_length=1)
    spatial_reference: str = Field(min_length=1)
    fields: tuple[ParcelArcGISFieldDefinition, ...] = Field(min_length=1)
    schema_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    metadata_projection_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    object_id_field: str = Field(min_length=1)
    object_id_is_unique: bool
    max_record_count: int = Field(ge=1)
    supports_query: bool
    supports_count: bool
    supports_order_by: bool
    supports_pagination: bool
    supported_query_formats: tuple[str, ...] = Field(min_length=1)
    limitations: tuple[str, ...] = Field(min_length=1)

    @field_validator("layer_url")
    @classmethod
    def require_https_layer_url(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("ArcGIS capability layer URLs must use HTTPS")
        return value

    @field_validator("observed_at")
    @classmethod
    def require_aware_observed_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("ArcGIS capability observed_at must be timezone-aware")
        return value

    @field_validator("supported_query_formats", "limitations")
    @classmethod
    def require_canonical_text(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value.strip() for value in values):
            raise ValueError("ArcGIS capability text values cannot be blank")
        if tuple(sorted(set(values), key=str.casefold)) != values:
            raise ValueError("ArcGIS capability text values must be unique and sorted")
        return values

    @model_validator(mode="after")
    def require_snapshot_consistency(self) -> ParcelArcGISCapabilitySnapshot:
        field_order = tuple((field.name.casefold(), field.field_type) for field in self.fields)
        if field_order != tuple(sorted(field_order)):
            raise ValueError("ArcGIS capability fields must be canonically sorted")
        names = [field.name.casefold() for field in self.fields]
        if len(names) != len(set(names)):
            raise ValueError("ArcGIS capability fields must have unique names")
        if self.object_id_field.casefold() not in set(names):
            raise ValueError("ArcGIS object ID field must exist in the schema snapshot")
        expected_fingerprint = arcgis_schema_fingerprint(
            self.fields,
            geometry_type=self.geometry_type,
            spatial_reference=self.spatial_reference,
        )
        if self.schema_fingerprint != expected_fingerprint:
            raise ValueError("ArcGIS schema fingerprint does not match field definitions")
        expected_projection_digest = arcgis_capability_projection_digest(
            service_version=self.service_version,
            geometry_type=self.geometry_type,
            spatial_reference=self.spatial_reference,
            fields=self.fields,
            object_id_field=self.object_id_field,
            object_id_is_unique=self.object_id_is_unique,
            max_record_count=self.max_record_count,
            supports_query=self.supports_query,
            supports_count=self.supports_count,
            supports_order_by=self.supports_order_by,
            supports_pagination=self.supports_pagination,
            supported_query_formats=self.supported_query_formats,
        )
        if self.metadata_projection_digest != expected_projection_digest:
            raise ValueError("ArcGIS metadata projection digest does not match capabilities")
        payload = self.model_dump(mode="json", exclude={"snapshot_id"})
        if self.snapshot_id != _digest_id("parcel-arcgis-capability", payload):
            raise ValueError("ArcGIS capability ID does not match snapshot content")
        return self

    @property
    def advertised_ready_for_probe(self) -> bool:
        """Return whether metadata advertises every bounded-probe primitive."""

        return all(
            (
                self.supports_query,
                self.supports_count,
                self.supports_order_by,
                self.supports_pagination,
                self.object_id_is_unique,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class ParcelArcGISProbeRequest(BaseModel):
    """Digest-bound, non-mutating ArcGIS query request specification."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str = Field(pattern=r"^parcel-arcgis-probe-request:[0-9a-f]{64}$")
    snapshot_id: str = Field(pattern=r"^parcel-arcgis-capability:[0-9a-f]{64}$")
    profile_id: str = Field(pattern=r"^parcel-source-verification:[0-9a-f]{64}$")
    source_key: str = Field(min_length=1)
    county: str = Field(min_length=1)
    kind: ParcelArcGISProbeKind
    where: str = "1=1"
    object_id_field: str = Field(min_length=1)
    schema_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    out_fields: tuple[str, ...] = ()
    order_by_fields: tuple[str, ...] = ()
    return_geometry: bool = False
    return_count_only: bool = False
    offset: int | None = Field(default=None, ge=0)
    record_count: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def require_safe_query_shape(self) -> ParcelArcGISProbeRequest:
        if self.where != "1=1":
            raise ValueError("ArcGIS acquisition probes must use the full-layer 1=1 filter")
        if self.return_geometry:
            raise ValueError("ArcGIS acquisition probes cannot request geometry")
        if self.kind == ParcelArcGISProbeKind.COUNT:
            if not self.return_count_only:
                raise ValueError("ArcGIS count probes must request count only")
            if self.out_fields or self.order_by_fields:
                raise ValueError("ArcGIS count probes cannot request fields or ordering")
            if self.offset is not None or self.record_count is not None:
                raise ValueError("ArcGIS count probes cannot request a page")
        else:
            if self.return_count_only:
                raise ValueError("ArcGIS page probes cannot request count only")
            if self.out_fields != (self.object_id_field,):
                raise ValueError("ArcGIS page probes may request only the object ID field")
            if self.order_by_fields != (f"{self.object_id_field} ASC",):
                raise ValueError("ArcGIS page probes require ascending object ID order")
            if self.offset is None or self.record_count is None:
                raise ValueError("ArcGIS page probes require offset and record count")
        payload = self.model_dump(mode="json", exclude={"request_id"})
        if self.request_id != _digest_id("parcel-arcgis-probe-request", payload):
            raise ValueError("ArcGIS probe request ID does not match request content")
        return self

    @property
    def query_parameters(self) -> dict[str, str | int | bool]:
        """Return the exact non-mutating ArcGIS REST parameters."""

        parameters: dict[str, str | int | bool] = {
            "f": "json",
            "where": self.where,
            "returnGeometry": False,
        }
        if self.kind == ParcelArcGISProbeKind.COUNT:
            parameters["returnCountOnly"] = True
            return parameters
        parameters.update(
            {
                "outFields": self.object_id_field,
                "orderByFields": f"{self.object_id_field} ASC",
                "resultOffset": self.offset or 0,
                "resultRecordCount": self.record_count or 1,
            }
        )
        return parameters

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class ParcelArcGISProbePlan(BaseModel):
    """Safe bounded plan that cannot authorize a complete acquisition run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    plan_id: str = Field(pattern=r"^parcel-arcgis-probe-plan:[0-9a-f]{64}$")
    snapshot_id: str = Field(pattern=r"^parcel-arcgis-capability:[0-9a-f]{64}$")
    profile_id: str = Field(pattern=r"^parcel-source-verification:[0-9a-f]{64}$")
    source_key: str = Field(min_length=1)
    county: str = Field(min_length=1)
    sample_size: int = Field(ge=1, le=100)
    requests: tuple[ParcelArcGISProbeRequest, ...] = Field(min_length=4, max_length=4)
    bulk_run_authorized: bool = False
    next_action: str = Field(min_length=1)
    generated_at: datetime

    @field_validator("generated_at")
    @classmethod
    def require_aware_generated_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("ArcGIS probe plan generated_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def require_plan_consistency(self) -> ParcelArcGISProbePlan:
        if self.bulk_run_authorized:
            raise ValueError("bounded ArcGIS probe plans cannot authorize bulk acquisition")
        kinds = tuple(request.kind for request in self.requests)
        expected_kinds = tuple(ParcelArcGISProbeKind)
        if kinds != expected_kinds:
            raise ValueError("ArcGIS probe requests must follow the canonical probe sequence")
        if any(
            request.snapshot_id != self.snapshot_id
            or request.profile_id != self.profile_id
            or request.source_key != self.source_key
            or request.county != self.county
            for request in self.requests
        ):
            raise ValueError("ArcGIS probe requests must match their plan scope")
        initial, next_page, replay = self.requests[1:]
        if initial.offset != 0 or replay.offset != 0:
            raise ValueError("initial and replay ArcGIS probes must start at offset zero")
        if next_page.offset != self.sample_size:
            raise ValueError("next ArcGIS probe must start after the initial sample")
        if any(request.record_count != self.sample_size for request in self.requests[1:]):
            raise ValueError("ArcGIS page probes must use the plan sample size")
        payload = self.model_dump(mode="json", exclude={"plan_id", "generated_at"})
        if self.plan_id != _digest_id("parcel-arcgis-probe-plan", payload):
            raise ValueError("ArcGIS probe plan ID does not match plan content")
        return self

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class ParcelArcGISProbeObservation(BaseModel):
    """Immutable response observation for one planned count or page request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_id: str = Field(pattern=r"^parcel-arcgis-probe-observation:[0-9a-f]{64}$")
    request_id: str = Field(pattern=r"^parcel-arcgis-probe-request:[0-9a-f]{64}$")
    snapshot_id: str = Field(pattern=r"^parcel-arcgis-capability:[0-9a-f]{64}$")
    profile_id: str = Field(pattern=r"^parcel-source-verification:[0-9a-f]{64}$")
    source_key: str = Field(min_length=1)
    county: str = Field(min_length=1)
    kind: ParcelArcGISProbeKind
    observed_at: datetime
    response_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    response_payload_json: str = Field(min_length=2)
    schema_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    total_count: int | None = Field(default=None, ge=0)
    object_ids: tuple[int, ...] = ()
    exceeded_transfer_limit: bool | None = None

    @field_validator("observed_at")
    @classmethod
    def require_aware_observed_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("ArcGIS probe observed_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def require_observation_consistency(self) -> ParcelArcGISProbeObservation:
        try:
            response_payload: Any = json.loads(self.response_payload_json)
        except json.JSONDecodeError as exc:
            raise ValueError("ArcGIS probe response payload must be valid JSON") from exc
        if not isinstance(response_payload, dict):
            raise ValueError("ArcGIS probe response payload must be a JSON object")
        canonical_response = canonical_json_payload(response_payload)
        if self.response_payload_json != canonical_response:
            raise ValueError("ArcGIS probe response payload must be canonical JSON")
        if self.response_digest != hashlib.sha256(
            canonical_response.encode("utf-8")
        ).hexdigest():
            raise ValueError("ArcGIS probe response digest does not match its payload")
        if self.kind == ParcelArcGISProbeKind.COUNT:
            if self.total_count is None or self.object_ids:
                raise ValueError("ArcGIS count observations require only a total count")
            if self.exceeded_transfer_limit is not None:
                raise ValueError("ArcGIS count observations cannot carry a transfer limit")
        else:
            if self.total_count is not None:
                raise ValueError("ArcGIS page observations cannot carry a total count")
            if self.object_ids != tuple(sorted(set(self.object_ids))):
                raise ValueError("ArcGIS page object IDs must be unique and ascending")
        payload = self.model_dump(mode="json", exclude={"observation_id"})
        if self.observation_id != _digest_id(
            "parcel-arcgis-probe-observation", payload
        ):
            raise ValueError("ArcGIS probe observation ID does not match response content")
        return self

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class ParcelArcGISBulkManifest(BaseModel):
    """Complete-run reconciliation proof required for bulk rehearsal maturity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest_id: str = Field(pattern=r"^parcel-arcgis-bulk-manifest:[0-9a-f]{64}$")
    snapshot_id: str = Field(pattern=r"^parcel-arcgis-capability:[0-9a-f]{64}$")
    profile_id: str = Field(pattern=r"^parcel-source-verification:[0-9a-f]{64}$")
    source_key: str = Field(min_length=1)
    county: str = Field(min_length=1)
    schema_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    started_at: datetime
    completed_at: datetime
    starting_count: int = Field(ge=0)
    ending_count: int = Field(ge=0)
    page_size: int = Field(ge=1)
    page_count: int = Field(ge=0)
    retrieved_count: int = Field(ge=0)
    unique_object_id_count: int = Field(ge=0)
    duplicate_object_id_count: int = Field(ge=0)
    failed_page_count: int = Field(ge=0)
    terminal_page_observed: bool
    checkpoint_resume_verified: bool
    retry_recovery_verified: bool
    page_response_digests: tuple[str, ...]
    object_id_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    rehearsal_evidence: ParcelArcGISBulkRehearsalEvidence

    @field_validator("started_at", "completed_at")
    @classmethod
    def require_aware_times(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("ArcGIS bulk manifest times must be timezone-aware")
        return value

    @field_validator("page_response_digests")
    @classmethod
    def require_page_digests(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(
            len(value) != 64
            or any(char not in "0123456789abcdef" for char in value)
            for value in values
        ):
            raise ValueError("ArcGIS page response digests must be lowercase SHA-256 values")
        return values

    @model_validator(mode="after")
    def require_complete_reconciliation(self) -> ParcelArcGISBulkManifest:
        if self.completed_at < self.started_at:
            raise ValueError("ArcGIS bulk manifest cannot complete before it starts")
        if self.starting_count != self.ending_count:
            raise ValueError("ArcGIS bulk rehearsal requires a stable start and end count")
        if self.retrieved_count != self.starting_count:
            raise ValueError("ArcGIS bulk retrieved count must reconcile to source count")
        if self.unique_object_id_count != self.retrieved_count:
            raise ValueError("ArcGIS bulk object IDs must reconcile to retrieved records")
        if self.duplicate_object_id_count or self.failed_page_count:
            raise ValueError("ArcGIS bulk rehearsal cannot contain duplicate IDs or failures")
        if not all(
            (
                self.terminal_page_observed,
                self.checkpoint_resume_verified,
                self.retry_recovery_verified,
            )
        ):
            raise ValueError("ArcGIS bulk rehearsal requires terminal, resume, and retry proof")
        expected_pages = (
            0
            if self.starting_count == 0
            else (self.starting_count + self.page_size - 1) // self.page_size
        )
        if self.page_count != expected_pages:
            raise ValueError("ArcGIS bulk page count does not match count and page size")
        if len(self.page_response_digests) != self.page_count:
            raise ValueError("ArcGIS bulk manifest requires one digest per data page")
        evidence = self.rehearsal_evidence
        evidence_times = (
  evidence.created_at,
  evidence.checkpoint.created_at,
  evidence.resume.resumed_at,
  *(page.observed_at for page in evidence.page_evidence),
  *(event.recorded_at for event in evidence.retry_events),
        )
        if any(
  timestamp < self.started_at or timestamp > self.completed_at
  for timestamp in evidence_times
        ):
  raise ValueError(
      "ArcGIS bulk rehearsal evidence falls outside the manifest execution window"
  )
        if (
            evidence.snapshot_id != self.snapshot_id
            or evidence.profile_id != self.profile_id
            or evidence.source_key != self.source_key
            or evidence.county != self.county
            or evidence.schema_fingerprint != self.schema_fingerprint
        ):
            raise ValueError("ArcGIS bulk rehearsal evidence scope mismatch")
        if evidence.page_size != self.page_size:
            raise ValueError("ArcGIS bulk rehearsal evidence page size mismatch")
        if len(evidence.page_evidence) != self.page_count:
            raise ValueError("ArcGIS bulk rehearsal evidence page count mismatch")
        if evidence.retrieved_count != self.retrieved_count:
            raise ValueError("ArcGIS bulk rehearsal evidence retrieved count mismatch")
        if evidence.unique_object_id_count != self.unique_object_id_count:
            raise ValueError("ArcGIS bulk rehearsal evidence unique-ID count mismatch")
        if evidence.duplicate_object_id_count != self.duplicate_object_id_count:
            raise ValueError("ArcGIS bulk rehearsal evidence duplicate count mismatch")
        if evidence.terminal_page_observed != self.terminal_page_observed:
            raise ValueError("ArcGIS bulk rehearsal terminal-page proof mismatch")
        if evidence.checkpoint_resume_verified != self.checkpoint_resume_verified:
            raise ValueError("ArcGIS bulk rehearsal checkpoint proof mismatch")
        if evidence.retry_recovery_verified != self.retry_recovery_verified:
            raise ValueError("ArcGIS bulk rehearsal retry proof mismatch")
        if evidence.page_response_digests != self.page_response_digests:
            raise ValueError("ArcGIS bulk rehearsal page digest mismatch")
        if evidence.object_id_set_digest != self.object_id_set_digest:
            raise ValueError("ArcGIS bulk rehearsal object-ID digest mismatch")
        payload = self.model_dump(mode="json", exclude={"manifest_id"})
        if self.manifest_id != _digest_id("parcel-arcgis-bulk-manifest", payload):
            raise ValueError("ArcGIS bulk manifest ID does not match manifest content")
        return self

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class ParcelArcGISAcquisitionGap(BaseModel):
    """One explicit capability, probe, or reconciliation gap."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: ParcelArcGISAcquisitionGapCode
    explanation: str = Field(min_length=1)
    next_action: str = Field(min_length=1)


class ParcelArcGISAcquisitionAssessment(BaseModel):
    """Conservative readiness result over metadata and executed proof records."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    assessment_id: str = Field(pattern=r"^parcel-arcgis-acquisition:[0-9a-f]{64}$")
    snapshot_id: str = Field(pattern=r"^parcel-arcgis-capability:[0-9a-f]{64}$")
    plan_id: str = Field(pattern=r"^parcel-arcgis-probe-plan:[0-9a-f]{64}$")
    profile_id: str = Field(pattern=r"^parcel-source-verification:[0-9a-f]{64}$")
    source_key: str = Field(min_length=1)
    county: str = Field(min_length=1)
    status: ParcelArcGISAcquisitionStatus
    probe_observation_ids: tuple[str, ...] = ()
    bulk_manifest_id: str | None = Field(
        default=None,
        pattern=r"^parcel-arcgis-bulk-manifest:[0-9a-f]{64}$",
    )
    expected_record_count: int | None = Field(default=None, ge=0)
    observed_unique_sample_count: int = Field(ge=0)
    bulk_acquisition_verified: bool
    gaps: tuple[ParcelArcGISAcquisitionGap, ...] = ()
    generated_at: datetime

    @field_validator("generated_at")
    @classmethod
    def require_aware_generated_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("ArcGIS acquisition generated_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def require_assessment_consistency(self) -> ParcelArcGISAcquisitionAssessment:
        if tuple(sorted(set(self.probe_observation_ids))) != self.probe_observation_ids:
            raise ValueError("ArcGIS assessment observation IDs must be unique and sorted")
        codes = tuple(gap.code.value for gap in self.gaps)
        if codes != tuple(sorted(set(codes))):
            raise ValueError("ArcGIS acquisition gaps must be unique and sorted")
        blockers = {
            ParcelArcGISAcquisitionGapCode.QUERY_NOT_ADVERTISED,
            ParcelArcGISAcquisitionGapCode.COUNT_NOT_ADVERTISED,
            ParcelArcGISAcquisitionGapCode.ORDERING_NOT_ADVERTISED,
            ParcelArcGISAcquisitionGapCode.PAGINATION_NOT_ADVERTISED,
            ParcelArcGISAcquisitionGapCode.UNIQUE_OBJECT_ID_UNVERIFIED,
            ParcelArcGISAcquisitionGapCode.SCHEMA_DRIFT,
            ParcelArcGISAcquisitionGapCode.PAGE_SEQUENCE_INVALID,
        }
        gap_codes = {gap.code for gap in self.gaps}
        if gap_codes & blockers:
            expected_status = ParcelArcGISAcquisitionStatus.BLOCKED
        elif not self.gaps:
            expected_status = ParcelArcGISAcquisitionStatus.BULK_REHEARSAL_VERIFIED
        elif gap_codes == {ParcelArcGISAcquisitionGapCode.BULK_REHEARSAL_MISSING}:
            expected_status = ParcelArcGISAcquisitionStatus.BOUNDED_QUERY_VERIFIED
        else:
            expected_status = ParcelArcGISAcquisitionStatus.METADATA_ONLY
        if self.status != expected_status:
            raise ValueError("ArcGIS acquisition status does not match its gaps")
        if self.bulk_acquisition_verified != (
            self.status == ParcelArcGISAcquisitionStatus.BULK_REHEARSAL_VERIFIED
        ):
            raise ValueError("ArcGIS bulk verification flag does not match assessment status")
        if self.bulk_acquisition_verified and self.bulk_manifest_id is None:
            raise ValueError("verified ArcGIS bulk acquisition requires a manifest")
        payload = self.model_dump(mode="json", exclude={"assessment_id", "generated_at"})
        if self.assessment_id != _digest_id("parcel-arcgis-acquisition", payload):
            raise ValueError("ArcGIS acquisition ID does not match assessment content")
        return self

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def arcgis_schema_fingerprint(
    fields: tuple[ParcelArcGISFieldDefinition, ...],
    *,
    geometry_type: str,
    spatial_reference: str,
) -> str:
    """Return a deterministic type-aware schema fingerprint."""

    payload = {
        "fields": [field.model_dump(mode="json") for field in fields],
        "geometry_type": geometry_type,
        "spatial_reference": spatial_reference,
    }
    return _sha256(payload)


def arcgis_capability_projection_digest(
    *,
    service_version: str,
    geometry_type: str,
    spatial_reference: str,
    fields: tuple[ParcelArcGISFieldDefinition, ...],
    object_id_field: str,
    object_id_is_unique: bool,
    max_record_count: int,
    supports_query: bool,
    supports_count: bool,
    supports_order_by: bool,
    supports_pagination: bool,
    supported_query_formats: tuple[str, ...],
) -> str:
    """Return a digest over the normalized capability metadata projection."""

    return _sha256(
        {
            "service_version": service_version,
            "geometry_type": geometry_type,
            "spatial_reference": spatial_reference,
            "fields": [field.model_dump(mode="json") for field in fields],
            "object_id_field": object_id_field,
            "object_id_is_unique": object_id_is_unique,
            "max_record_count": max_record_count,
            "supports_query": supports_query,
            "supports_count": supports_count,
            "supports_order_by": supports_order_by,
            "supports_pagination": supports_pagination,
            "supported_query_formats": supported_query_formats,
        }
    )


def canonical_json_payload(payload: Any) -> str:
    """Return deterministic compact JSON for retained response evidence."""

    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def digest_json_payload(payload: Any) -> str:
    """Return a deterministic SHA-256 for an arbitrary JSON-safe payload."""

    return _sha256(payload)


def digest_identity(namespace: str, payload: dict[str, Any]) -> str:
    """Return a namespaced digest identity for factory functions."""

    return _digest_id(namespace, payload)


def _digest_id(namespace: str, payload: dict[str, Any]) -> str:
    return f"{namespace}:{_sha256(payload)}"


def _sha256(payload: Any) -> str:
    encoded = canonical_json_payload(payload)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
