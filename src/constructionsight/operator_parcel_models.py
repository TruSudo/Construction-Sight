"""Bounded read-only parcel observations linked by exact normalized APN and county."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from constructionsight.operator_dashboard_models import RecordKind


class ParcelCandidatePoint(BaseModel):
    """Claimed geodetic parcel centroid, not a surveyed or verified boundary."""

    latitude: float = Field(ge=-85.05112878, le=85.05112878, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    classification: Literal["source_claimed_centroid"] = "source_claimed_centroid"


class ParcelCandidateClaim(BaseModel):
    """One exact APN/county source claim without entity or site-resolution authority."""

    parcel_record_id: str
    source_key: str
    source_record_id: str | None
    apn: str
    county: str
    address: str | None
    zoning: str | None
    land_use: str | None
    source_updated_at: str | None
    geometry_kind: str | None
    spatial_reference: str | None
    point: ParcelCandidatePoint | None
    map_reason: str
    limitations: list[str] = Field(default_factory=list)
    classification: Literal["unverified_parcel_claim"] = "unverified_parcel_claim"


class ParcelCandidatesSnapshot(BaseModel):
    """An exact source-record parcel lookup; none of its matches are established links."""

    source_kind: RecordKind
    source_record_id: str
    source_apn: str | None
    normalized_apn: str | None
    source_county: str | None
    matches: list[ParcelCandidateClaim]
    matching_total: int
    returned: int
    result_limit: int
    truncated: bool
    read_only: Literal[True] = True
    linked_site_verified: Literal[False] = False
    parcel_boundaries_rendered: Literal[False] = False
    limitations: list[str] = Field(default_factory=lambda: [
        "Exact normalized APN and county co-occurrence is a candidate, not a "
        "confirmed parcel-to-site relationship.",
        "Coordinates are stored source claims; no spatial containment or parcel "
        "boundary verification has been performed.",
        "This response does not establish current construction or commercial authorization.",
    ])
