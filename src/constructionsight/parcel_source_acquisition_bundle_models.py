"""Portable, digest-bound ArcGIS bounded-proof bundle models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from constructionsight.parcel_source_acquisition_models import (
    ParcelArcGISAcquisitionAssessment,
    ParcelArcGISAcquisitionStatus,
    ParcelArcGISCapabilitySnapshot,
    ParcelArcGISProbeObservation,
    ParcelArcGISProbePlan,
    digest_identity,
)
from constructionsight.parcel_source_verification_models import (
    ParcelSourceEvidence,
    ParcelSourceVerificationProfile,
    ParcelSourceVerificationStatus,
)

_BUNDLE_SCHEMA_VERSION = "parcel-arcgis-bounded-proof-bundle/v1"


class ParcelArcGISBoundedProofBundle(BaseModel):
    """Self-contained official evidence and executed bounded ArcGIS proof."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = _BUNDLE_SCHEMA_VERSION
    bundle_id: str = Field(pattern=r"^parcel-arcgis-bounded-proof-bundle:[0-9a-f]{64}$")
    source_key: str = Field(min_length=1)
    county: str = Field(min_length=1)
    profile: ParcelSourceVerificationProfile
    source_evidence: tuple[ParcelSourceEvidence, ...] = Field(min_length=1)
    snapshot: ParcelArcGISCapabilitySnapshot
    plan: ParcelArcGISProbePlan
    observations: tuple[ParcelArcGISProbeObservation, ...] = Field(
        min_length=4,
        max_length=4,
    )
    assessment: ParcelArcGISAcquisitionAssessment
    network_request_count: int = Field(default=5, ge=5, le=5)
    bulk_run_authorized: bool = False
    limitations: tuple[str, ...] = Field(min_length=1)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def require_aware_created_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("ArcGIS bounded-proof bundle created_at must be timezone-aware")
        return value

    @field_validator("limitations")
    @classmethod
    def require_canonical_limitations(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value.strip() for value in values):
            raise ValueError("ArcGIS bounded-proof limitations cannot be blank")
        if tuple(sorted(set(values), key=str.casefold)) != values:
            raise ValueError("ArcGIS bounded-proof limitations must be unique and sorted")
        return values

    @model_validator(mode="after")
    def require_complete_bounded_chain(self) -> ParcelArcGISBoundedProofBundle:
        if self.schema_version != _BUNDLE_SCHEMA_VERSION:
            raise ValueError("unsupported ArcGIS bounded-proof bundle schema version")
        if self.bulk_run_authorized:
            raise ValueError("ArcGIS bounded-proof bundles cannot authorize bulk acquisition")
        if self.network_request_count != 1 + len(self.plan.requests):
            raise ValueError("ArcGIS bounded-proof request count must cover metadata and probes")
        if self.profile.status != ParcelSourceVerificationStatus.VERIFIED_PREVIEW:
            raise ValueError("ArcGIS bounded proof requires a verified-preview profile")
        scope = (self.source_key, self.county, self.profile.profile_id)
        if (
            (self.profile.source_key, self.profile.county, self.profile.profile_id) != scope
            or (self.snapshot.source_key, self.snapshot.county, self.snapshot.profile_id) != scope
            or (self.plan.source_key, self.plan.county, self.plan.profile_id) != scope
            or (
                self.assessment.source_key,
                self.assessment.county,
                self.assessment.profile_id,
            )
            != scope
        ):
            raise ValueError("ArcGIS bounded-proof records must share one source scope")
        if (
            self.plan.snapshot_id != self.snapshot.snapshot_id
            or self.assessment.snapshot_id != self.snapshot.snapshot_id
            or self.assessment.plan_id != self.plan.plan_id
        ):
            raise ValueError("ArcGIS bounded-proof plan and assessment dependencies disagree")
        expected_evidence_ids = tuple(sorted(self.profile.evidence_ids))
        observed_evidence_ids = tuple(
            sorted(evidence.evidence_id for evidence in self.source_evidence)
        )
        if observed_evidence_ids != expected_evidence_ids:
            raise ValueError("ArcGIS bounded-proof evidence must exactly satisfy the profile")
        if any(
            evidence.source_key != self.source_key or evidence.county != self.county
            for evidence in self.source_evidence
        ):
            raise ValueError("ArcGIS bounded-proof evidence scope mismatch")
        if self.snapshot.layer_url != self.profile.source_url:
            raise ValueError("ArcGIS bounded-proof layer URL does not match the profile")
        if {field.name for field in self.snapshot.fields} | {"geometry"} != set(
            self.profile.schema_fields
        ):
            raise ValueError("ArcGIS bounded-proof schema does not match the profile")
        if (
            self.snapshot.max_record_count != self.profile.max_record_count
            or self.snapshot.spatial_reference != self.profile.spatial_reference
        ):
            raise ValueError("ArcGIS bounded-proof service limits disagree with the profile")
        if tuple(item.request_id for item in self.observations) != tuple(
            request.request_id for request in self.plan.requests
        ):
            raise ValueError("ArcGIS bounded-proof observations must follow the plan order")
        if any(
            observation.snapshot_id != self.snapshot.snapshot_id
            or observation.profile_id != self.profile.profile_id
            or observation.source_key != self.source_key
            or observation.county != self.county
            or observation.schema_fingerprint != self.snapshot.schema_fingerprint
            for observation in self.observations
        ):
            raise ValueError("ArcGIS bounded-proof observations disagree with the snapshot")
        if self.assessment.probe_observation_ids != tuple(
            sorted(observation.observation_id for observation in self.observations)
        ):
            raise ValueError("ArcGIS bounded-proof assessment must reference every observation")
        if self.assessment.bulk_manifest_id is not None:
            raise ValueError("ArcGIS bounded-proof bundles cannot contain a bulk manifest")
        if self.assessment.status not in {
            ParcelArcGISAcquisitionStatus.BOUNDED_QUERY_VERIFIED,
            ParcelArcGISAcquisitionStatus.BLOCKED,
        }:
            raise ValueError("ArcGIS bounded-proof assessment must be executed or blocked")
        if self.assessment.bulk_acquisition_verified:
            raise ValueError("ArcGIS bounded proof cannot verify bulk acquisition")
        payload = self.model_dump(mode="json", exclude={"bundle_id", "created_at"})
        if self.bundle_id != digest_identity(
            "parcel-arcgis-bounded-proof-bundle",
            payload,
        ):
            raise ValueError("ArcGIS bounded-proof bundle ID does not match its content")
        return self

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class ParcelArcGISBoundedProofVerification(BaseModel):
    """Independent offline recomputation result for one portable proof bundle."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    verification_id: str = Field(pattern=r"^parcel-arcgis-bounded-proof-verification:[0-9a-f]{64}$")
    bundle_id: str = Field(pattern=r"^parcel-arcgis-bounded-proof-bundle:[0-9a-f]{64}$")
    source_key: str = Field(min_length=1)
    county: str = Field(min_length=1)
    status: ParcelArcGISAcquisitionStatus
    assessment_id: str = Field(pattern=r"^parcel-arcgis-acquisition:[0-9a-f]{64}$")
    evidence_count: int = Field(ge=1)
    observation_count: int = Field(ge=4, le=4)
    network_request_count: int = Field(ge=5, le=5)
    assessment_recomputed: bool = True
    response_digests_recomputed: bool = True
    valid: bool = True
    bulk_run_authorized: bool = False
    next_action: str = Field(min_length=1)
    verified_at: datetime

    @field_validator("verified_at")
    @classmethod
    def require_aware_verified_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("ArcGIS proof verification time must be timezone-aware")
        return value

    @model_validator(mode="after")
    def require_safe_verification(self) -> ParcelArcGISBoundedProofVerification:
        if not all(
            (
                self.assessment_recomputed,
                self.response_digests_recomputed,
                self.valid,
            )
        ):
            raise ValueError("ArcGIS bounded-proof verification must pass every offline check")
        if self.bulk_run_authorized:
            raise ValueError("ArcGIS bounded-proof verification cannot authorize bulk")
        if self.status not in {
            ParcelArcGISAcquisitionStatus.BOUNDED_QUERY_VERIFIED,
            ParcelArcGISAcquisitionStatus.BLOCKED,
        }:
            raise ValueError("ArcGIS bounded-proof verification status is invalid")
        payload = self.model_dump(mode="json", exclude={"verification_id", "verified_at"})
        if self.verification_id != digest_identity(
            "parcel-arcgis-bounded-proof-verification",
            payload,
        ):
            raise ValueError("ArcGIS proof verification ID does not match its content")
        return self

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class ParcelArcGISProofPersistenceReceipt(BaseModel):
    """Digest-bound receipt for an explicitly authorized local proof write."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    receipt_id: str = Field(pattern=r"^parcel-arcgis-proof-persistence:[0-9a-f]{64}$")
    bundle_id: str = Field(pattern=r"^parcel-arcgis-bounded-proof-bundle:[0-9a-f]{64}$")
    source_key: str = Field(min_length=1)
    county: str = Field(min_length=1)
    profile_id: str = Field(pattern=r"^parcel-source-verification:[0-9a-f]{64}$")
    snapshot_id: str = Field(pattern=r"^parcel-arcgis-capability:[0-9a-f]{64}$")
    plan_id: str = Field(pattern=r"^parcel-arcgis-probe-plan:[0-9a-f]{64}$")
    observation_ids: tuple[str, ...] = Field(min_length=4, max_length=4)
    assessment_id: str = Field(pattern=r"^parcel-arcgis-acquisition:[0-9a-f]{64}$")
    evidence_count: int = Field(ge=1)
    mutation_authorized: bool = True
    replay_policy: str = "insert_or_exact_replay"
    bulk_run_authorized: bool = False
    persisted_at: datetime

    @field_validator("persisted_at")
    @classmethod
    def require_aware_persisted_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("ArcGIS proof persistence time must be timezone-aware")
        return value

    @model_validator(mode="after")
    def require_safe_receipt(self) -> ParcelArcGISProofPersistenceReceipt:
        if not self.mutation_authorized:
            raise ValueError("ArcGIS proof persistence receipt requires authorization")
        if self.replay_policy != "insert_or_exact_replay":
            raise ValueError("unsupported ArcGIS proof persistence replay policy")
        if self.bulk_run_authorized:
            raise ValueError("ArcGIS proof persistence cannot authorize bulk")
        if tuple(sorted(set(self.observation_ids))) != self.observation_ids:
            raise ValueError("ArcGIS proof receipt observation IDs must be unique and sorted")
        payload = self.model_dump(mode="json", exclude={"receipt_id"})
        if self.receipt_id != digest_identity(
            "parcel-arcgis-proof-persistence",
            payload,
        ):
            raise ValueError("ArcGIS proof persistence receipt ID does not match content")
        return self

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
