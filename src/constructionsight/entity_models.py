"""Named entity models for ConstructionSight."""

from __future__ import annotations

from pydantic import BaseModel, Field

from constructionsight.domain_types import PartyRole
from constructionsight.provenance import Provenance


class Entity(BaseModel):
    """Normalized person, organization, agency, or project participant."""

    entity_key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    role: PartyRole = PartyRole.UNKNOWN
    license_number: str | None = None
    business_address: str | None = None
    jurisdiction: str | None = None
    county: str | None = None
    state: str = "CA"
    provenance: list[Provenance] = Field(default_factory=list)
