"""Site and parcel models for ConstructionSight."""

from __future__ import annotations

from pydantic import BaseModel, Field

from constructionsight.provenance import Provenance


class Site(BaseModel):
    """Normalized site or parcel location from public records."""

    site_key: str = Field(min_length=1)
    county: str = Field(min_length=1)
    state: str = Field(default="CA", min_length=2, max_length=2)
    jurisdiction: str | None = None
    apn: str | None = None
    address: str | None = None
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    lot_size_acres: float | None = None
    provenance: list[Provenance] = Field(default_factory=list)
