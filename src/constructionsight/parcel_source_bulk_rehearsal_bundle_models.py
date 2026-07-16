"""Portable models for complete ArcGIS rehearsal proof bundles."""

from __future__ import annotations

import base64
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from constructionsight.parcel_source_acquisition_models import (
    ParcelArcGISBulkManifest,
    ParcelArcGISCapabilitySnapshot,
    digest_identity,
)
from constructionsight.parcel_source_bulk_rehearsal import parse_arcgis_object_id_page
from constructionsight.parcel_source_bulk_rehearsal_artifacts import (
    ParcelArcGISBulkArtifactKind,
    ParcelArcGISBulkCountResponse,
    ParcelArcGISBulkPageResponse,
    decode_json_object,
    digest_response_body,
)
from constructionsight.parcel_source_bulk_rehearsal_http import (
    ParcelArcGISBulkRehearsalPlan,
)

_BUNDLE_SCHEMA_VERSION = "parcel-arcgis-bulk-rehearsal-proof-bundle/v1"


class ParcelArcGISBulkPortableArtifact(BaseModel):
    """One exact successful response embedded in a portable proof bundle."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: ParcelArcGISBulkArtifactKind
    sequence_index: int = Field(ge=0)
    response_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    response_size: int = Field(ge=1)
    artifact_reference: str = Field(min_length=1)
    response_body_base64: str = Field(min_length=1)

    @field_validator("artifact_reference")
    @classmethod
    def require_safe_artifact_reference(cls, value: str) -> str:
        if value != value.strip() or "\\" in value:
            raise ValueError("ArcGIS portable artifact reference must be trimmed and portable")
        path = PurePosixPath(value)
        if path.is_absolute() or len(path.parts) != 1 or path.name != value:
            raise ValueError("ArcGIS portable artifact reference must be a single file name")
        if value in {".", ".."}:
            raise ValueError("ArcGIS portable artifact reference is unsafe")
        return value

    @model_validator(mode="after")
    def require_exact_embedded_response(self) -> ParcelArcGISBulkPortableArtifact:
        try:
            response_body = base64.b64decode(
                self.response_body_base64.encode("ascii"),
                validate=True,
            )
        except (UnicodeEncodeError, ValueError) as exc:
            raise ValueError("ArcGIS portable artifact body must be canonical base64") from exc
        canonical = base64.b64encode(response_body).decode("ascii")
        if canonical != self.response_body_base64:
            raise ValueError("ArcGIS portable artifact body must use canonical base64")
        if len(response_body) != self.response_size:
            raise ValueError("ArcGIS portable artifact response size does not match its body")
        if digest_response_body(response_body) != self.response_digest:
            raise ValueError("ArcGIS portable artifact response digest does not match its body")
        decode_json_object(response_body)
        return self

    def response_body(self) -> bytes:
        """Return the exact embedded response bytes."""

        return base64.b64decode(self.response_body_base64.encode("ascii"), validate=True)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class ParcelArcGISBulkRehearsalProofBundle(BaseModel):
    """Self-contained exact-response proof for one complete rehearsal."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    schema_version: str = _BUNDLE_SCHEMA_VERSION
    bundle_id: str = Field(
        pattern=r"^parcel-arcgis-bulk-rehearsal-proof-bundle:[0-9a-f]{64}$"
    )
    source_key: str = Field(min_length=1)
    county: str = Field(min_length=1)
    snapshot: ParcelArcGISCapabilitySnapshot
    plan: ParcelArcGISBulkRehearsalPlan
    manifest: ParcelArcGISBulkManifest
    checkpoint_reloaded: bool = True
    artifacts: tuple[ParcelArcGISBulkPortableArtifact, ...] = Field(min_length=3)
    bulk_run_authorized: bool = False
    limitations: tuple[str, ...] = Field(min_length=1)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def require_aware_created_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("ArcGIS rehearsal proof bundle created_at must be timezone-aware")
        return value

    @field_validator("limitations")
    @classmethod
    def require_canonical_limitations(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value.strip() for value in values):
            raise ValueError("ArcGIS rehearsal proof limitations cannot be blank")
        if tuple(sorted(set(values), key=str.casefold)) != values:
            raise ValueError("ArcGIS rehearsal proof limitations must be unique and sorted")
        return values

    @model_validator(mode="after")
    def require_complete_portable_chain(self) -> ParcelArcGISBulkRehearsalProofBundle:
        if self.schema_version != _BUNDLE_SCHEMA_VERSION:
            raise ValueError("unsupported ArcGIS rehearsal proof bundle schema version")
        if not self.checkpoint_reloaded:
            raise ValueError("ArcGIS rehearsal proof bundle requires checkpoint reload proof")
        if self.bulk_run_authorized:
            raise ValueError("ArcGIS rehearsal proof bundle cannot authorize a bulk run")
        if self.created_at < self.manifest.completed_at:
            raise ValueError(
                "ArcGIS rehearsal proof bundle created_at cannot precede manifest completion"
            )
        scope = (self.source_key, self.county)
        if (
            (self.snapshot.source_key, self.snapshot.county) != scope
            or (self.plan.source_key, self.plan.county) != scope
            or (self.manifest.source_key, self.manifest.county) != scope
        ):
            raise ValueError("ArcGIS rehearsal proof records must share one source scope")
        if (
            self.plan.snapshot_id != self.snapshot.snapshot_id
            or self.manifest.snapshot_id != self.snapshot.snapshot_id
            or self.plan.profile_id != self.snapshot.profile_id
            or self.manifest.profile_id != self.snapshot.profile_id
            or self.plan.object_id_field != self.snapshot.object_id_field
            or self.manifest.schema_fingerprint != self.snapshot.schema_fingerprint
        ):
            raise ValueError("ArcGIS rehearsal proof dependencies disagree")
        expected_query_url = self.snapshot.layer_url.rstrip("/") + "/query"
        if self.plan.query_url != expected_query_url:
            raise ValueError("ArcGIS rehearsal proof plan endpoint does not match snapshot")
        if self.plan.page_size != self.manifest.page_size:
            raise ValueError("ArcGIS rehearsal proof plan page size does not match manifest")
        expected_artifact_count = self.manifest.page_count + 2
        if len(self.artifacts) != expected_artifact_count:
            raise ValueError("ArcGIS rehearsal proof must embed both counts and every page")
        if tuple(artifact.sequence_index for artifact in self.artifacts) != tuple(
            range(expected_artifact_count)
        ):
            raise ValueError("ArcGIS rehearsal proof artifact sequence must be contiguous")
        first, *page_artifacts, last = self.artifacts
        if first.kind != ParcelArcGISBulkArtifactKind.STARTING_COUNT:
            raise ValueError("ArcGIS rehearsal proof first artifact must be starting count")
        if last.kind != ParcelArcGISBulkArtifactKind.ENDING_COUNT:
            raise ValueError("ArcGIS rehearsal proof last artifact must be ending count")
        if any(
            artifact.kind != ParcelArcGISBulkArtifactKind.PAGE
            for artifact in page_artifacts
        ):
            raise ValueError("ArcGIS rehearsal proof middle artifacts must be pages")
        if tuple(artifact.response_digest for artifact in page_artifacts) != (
            self.manifest.page_response_digests
        ):
            raise ValueError("ArcGIS rehearsal proof page artifacts do not match manifest")
        starting_payload = decode_json_object(first.response_body())
        ending_payload = decode_json_object(last.response_body())
        starting_count = starting_payload.get("count")
        ending_count = ending_payload.get("count")
        if (
            isinstance(starting_count, bool)
            or not isinstance(starting_count, int)
            or isinstance(ending_count, bool)
            or not isinstance(ending_count, int)
        ):
            raise ValueError("ArcGIS rehearsal proof count artifacts are malformed")
        ParcelArcGISBulkCountResponse(
            count=starting_count,
            response_body=first.response_body(),
        )
        ParcelArcGISBulkCountResponse(
            count=ending_count,
            response_body=last.response_body(),
        )
        if (
            starting_count != self.manifest.starting_count
            or ending_count != self.manifest.ending_count
        ):
            raise ValueError("ArcGIS rehearsal proof count artifacts do not match manifest")
        page_evidence = self.manifest.rehearsal_evidence.page_evidence
        for artifact, evidence in zip(page_artifacts, page_evidence, strict=True):
            page_response = ParcelArcGISBulkPageResponse(
                response_body=artifact.response_body()
            )
            object_ids = parse_arcgis_object_id_page(
                page_response.payload(),
                object_id_field=self.snapshot.object_id_field,
            )
            if object_ids != evidence.object_ids:
                raise ValueError("ArcGIS rehearsal proof page body does not match evidence")
            if artifact.response_digest != evidence.response_digest:
                raise ValueError("ArcGIS rehearsal proof page digest does not match evidence")
        if self.bundle_id != digest_identity(
            "parcel-arcgis-bulk-rehearsal-proof-bundle",
            self.identity_payload(),
        ):
            raise ValueError("ArcGIS rehearsal proof bundle ID does not match its content")
        return self

    def identity_payload(self) -> dict[str, Any]:
        """Return the complete immutable identity payload."""

        return {
            "schema_version": self.schema_version,
            "source_key": self.source_key,
            "county": self.county,
            "snapshot": self.snapshot.to_dict(),
            "plan": self.plan.to_dict(),
            "manifest": self.manifest.to_dict(),
            "checkpoint_reloaded": self.checkpoint_reloaded,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "bulk_run_authorized": self.bulk_run_authorized,
            "limitations": list(self.limitations),
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json", exclude={"plan"})
        payload["plan"] = self.plan.to_dict()
        return payload


class ParcelArcGISBulkRehearsalProofVerification(BaseModel):
    """Independent offline verification result for a portable rehearsal bundle."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    verification_id: str = Field(
        pattern=r"^parcel-arcgis-bulk-rehearsal-proof-verification:[0-9a-f]{64}$"
    )
    bundle_id: str = Field(
        pattern=r"^parcel-arcgis-bulk-rehearsal-proof-bundle:[0-9a-f]{64}$"
    )
    source_key: str = Field(min_length=1)
    county: str = Field(min_length=1)
    manifest_id: str = Field(pattern=r"^parcel-arcgis-bulk-manifest:[0-9a-f]{64}$")
    artifact_count: int = Field(ge=3)
    plan_recomputed: bool = True
    manifest_recomputed: bool = True
    response_bytes_recomputed: bool = True
    object_ids_recomputed: bool = True
    valid: bool = True
    bulk_run_authorized: bool = False
    next_action: str = Field(min_length=1)
    verified_at: datetime

    @field_validator("verified_at")
    @classmethod
    def require_aware_verified_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("ArcGIS rehearsal proof verification time must be aware")
        return value

    @model_validator(mode="after")
    def require_safe_verification(self) -> ParcelArcGISBulkRehearsalProofVerification:
        if not all(
            (
                self.plan_recomputed,
                self.manifest_recomputed,
                self.response_bytes_recomputed,
                self.object_ids_recomputed,
                self.valid,
            )
        ):
            raise ValueError("ArcGIS rehearsal proof verification must pass every check")
        if self.bulk_run_authorized:
            raise ValueError("ArcGIS rehearsal proof verification cannot authorize bulk")
        payload = self.model_dump(
            mode="json",
            exclude={"verification_id", "verified_at"},
        )
        if self.verification_id != digest_identity(
            "parcel-arcgis-bulk-rehearsal-proof-verification",
            payload,
        ):
            raise ValueError("ArcGIS rehearsal proof verification ID is invalid")
        return self

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
