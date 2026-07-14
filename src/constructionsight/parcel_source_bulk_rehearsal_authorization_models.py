"""Exact-plan, single-use authorization models for live ArcGIS rehearsals."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from constructionsight.parcel_source_acquisition_models import digest_identity

AUTHORIZATION_SCHEMA_VERSION: Final[
    Literal["parcel-arcgis-bulk-rehearsal-authorization/v1"]
] = "parcel-arcgis-bulk-rehearsal-authorization/v1"
PREFLIGHT_SCHEMA_VERSION: Final[
    Literal["parcel-arcgis-bulk-rehearsal-preflight/v1"]
] = "parcel-arcgis-bulk-rehearsal-preflight/v1"
_AUTHORIZATION_STATEMENT: Final[
    Literal["authorize one complete read-only ArcGIS rehearsal"]
] = "authorize one complete read-only ArcGIS rehearsal"


class ParcelArcGISBulkRehearsalAuthorization(BaseModel):
    """Expiring single-use authority for one exact read-only rehearsal plan."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["parcel-arcgis-bulk-rehearsal-authorization/v1"] = (
        AUTHORIZATION_SCHEMA_VERSION
    )
    authorization_id: str = Field(
        pattern=r"^parcel-arcgis-bulk-rehearsal-authorization:[0-9a-f]{64}$"
    )
    snapshot_id: str = Field(pattern=r"^parcel-arcgis-capability:[0-9a-f]{64}$")
    profile_id: str = Field(pattern=r"^parcel-source-verification:[0-9a-f]{64}$")
    plan_id: str = Field(pattern=r"^parcel-arcgis-bulk-rehearsal-plan:[0-9a-f]{64}$")
    source_key: str = Field(min_length=1)
    county: str = Field(min_length=1)
    query_url: str = Field(min_length=1)
    object_id_field: str = Field(min_length=1)
    page_size: int = Field(ge=1)
    checkpoint_after_pages: int = Field(ge=1)
    injected_retry_page_index: int = Field(ge=1)
    max_attempts: int = Field(ge=2, le=5)
    snapshot_observed_at: datetime
    plan_generated_at: datetime
    execution_nonce: str = Field(pattern=r"^[0-9a-f]{64}$")
    issued_by: str = Field(min_length=1)
    authorization_reason: str = Field(min_length=1)
    authorization_statement: Literal[
        "authorize one complete read-only ArcGIS rehearsal"
    ] = _AUTHORIZATION_STATEMENT
    issued_at: datetime
    not_before: datetime
    expires_at: datetime
    execution_limit: Literal[1] = 1
    count_request_limit: Literal[2] = 2
    method: Literal["GET"] = "GET"
    geometry_authorized: Literal[False] = False
    exact_response_retention_required: Literal[True] = True
    durable_checkpoint_required: Literal[True] = True
    portable_proof_bundle_required: Literal[True] = True
    independent_verification_required: Literal[True] = True
    explicit_operator_authorization: Literal[True] = True
    live_rehearsal_execution_authorized: Literal[True] = True
    credential_use_authorized: Literal[False] = False
    access_control_bypass_authorized: Literal[False] = False
    parcel_import_authorized: Literal[False] = False
    source_profile_promotion_authorized: Literal[False] = False
    recurring_execution_authorized: Literal[False] = False
    production_bulk_run_authorized: Literal[False] = False
    limitations: tuple[str, ...] = Field(min_length=1)

    @field_validator(
        "snapshot_observed_at",
        "plan_generated_at",
        "issued_at",
        "not_before",
        "expires_at",
    )
    @classmethod
    def require_aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("ArcGIS rehearsal authorization times must be timezone-aware")
        return value

    @field_validator(
        "source_key",
        "county",
        "object_id_field",
        "issued_by",
        "authorization_reason",
    )
    @classmethod
    def require_trimmed_text(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("ArcGIS rehearsal authorization text must be trimmed")
        return value

    @field_validator("query_url")
    @classmethod
    def require_exact_query_url(cls, value: str) -> str:
        if value != value.strip() or not value.startswith("https://"):
            raise ValueError("ArcGIS rehearsal authorization requires an HTTPS query URL")
        if not value.endswith("/query"):
            raise ValueError("ArcGIS rehearsal authorization must bind a layer query URL")
        return value

    @field_validator("limitations")
    @classmethod
    def require_canonical_limitations(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value.strip() or value != value.strip() for value in values):
            raise ValueError("ArcGIS rehearsal authorization limitations must be trimmed")
        if values != tuple(sorted(set(values), key=str.casefold)):
            raise ValueError(
                "ArcGIS rehearsal authorization limitations must be unique and sorted"
            )
        return values

    @model_validator(mode="after")
    def require_bounded_single_use_authority(
        self,
    ) -> ParcelArcGISBulkRehearsalAuthorization:
        if self.plan_generated_at < self.snapshot_observed_at:
            raise ValueError("authorization plan cannot predate its capability snapshot")
        if self.issued_at < self.plan_generated_at:
            raise ValueError("authorization issuance cannot predate plan generation")
        if self.issued_at > self.not_before:
            raise ValueError("authorization issued_at cannot follow not_before")
        if self.not_before >= self.expires_at:
            raise ValueError("authorization not_before must precede expires_at")
        if (self.expires_at - self.not_before).total_seconds() > 86_400:
            raise ValueError("ArcGIS rehearsal authorization cannot exceed 24 hours")
        if self.injected_retry_page_index < self.checkpoint_after_pages:
            raise ValueError("authorized retry proof must occur after checkpoint resume")
        if self.authorization_id != digest_identity(
            "parcel-arcgis-bulk-rehearsal-authorization",
            self.identity_payload(),
        ):
            raise ValueError("ArcGIS rehearsal authorization ID does not match content")
        return self

    def identity_payload(self) -> dict[str, Any]:
        """Return all authority-significant content without the stored identity."""

        return self.model_dump(mode="json", exclude={"authorization_id"})

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class ParcelArcGISBulkRehearsalPreflight(BaseModel):
    """Time-bound offline result proving one authorization is currently usable."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["parcel-arcgis-bulk-rehearsal-preflight/v1"] = (
        PREFLIGHT_SCHEMA_VERSION
    )
    preflight_id: str = Field(
        pattern=r"^parcel-arcgis-bulk-rehearsal-preflight:[0-9a-f]{64}$"
    )
    authorization_id: str = Field(
        pattern=r"^parcel-arcgis-bulk-rehearsal-authorization:[0-9a-f]{64}$"
    )
    snapshot_id: str = Field(pattern=r"^parcel-arcgis-capability:[0-9a-f]{64}$")
    profile_id: str = Field(pattern=r"^parcel-source-verification:[0-9a-f]{64}$")
    plan_id: str = Field(pattern=r"^parcel-arcgis-bulk-rehearsal-plan:[0-9a-f]{64}$")
    source_key: str = Field(min_length=1)
    county: str = Field(min_length=1)
    checked_at: datetime
    valid_until: datetime
    exact_snapshot_verified: Literal[True] = True
    exact_plan_verified: Literal[True] = True
    authorization_integrity_verified: Literal[True] = True
    authorization_window_verified: Literal[True] = True
    single_use_available: Literal[True] = True
    retention_requirements_verified: Literal[True] = True
    ready_for_single_live_rehearsal: Literal[True] = True
    live_rehearsal_execution_authorized: Literal[True] = True
    parcel_import_authorized: Literal[False] = False
    source_profile_promotion_authorized: Literal[False] = False
    recurring_execution_authorized: Literal[False] = False
    production_bulk_run_authorized: Literal[False] = False
    next_action: str = Field(min_length=1)

    @field_validator("checked_at", "valid_until")
    @classmethod
    def require_aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("ArcGIS rehearsal preflight times must be timezone-aware")
        return value

    @model_validator(mode="after")
    def require_consistent_preflight(self) -> ParcelArcGISBulkRehearsalPreflight:
        if self.checked_at >= self.valid_until:
            raise ValueError("ArcGIS rehearsal preflight must precede authorization expiry")
        if self.preflight_id != digest_identity(
            "parcel-arcgis-bulk-rehearsal-preflight",
            self.identity_payload(),
        ):
            raise ValueError("ArcGIS rehearsal preflight ID does not match content")
        return self

    def identity_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude={"preflight_id"})

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
