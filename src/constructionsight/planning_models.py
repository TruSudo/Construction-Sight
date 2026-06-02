"""Planning and entitlement domain models for ConstructionSight."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from constructionsight.entity_models import Entity
from constructionsight.provenance import Provenance
from constructionsight.site_models import Site


class PlanningCaseRecord(BaseModel):
    """Normalized planning, entitlement, zoning, design review, or map case."""

    case_key: str = Field(min_length=1)
    case_number: str = Field(min_length=1)
    jurisdiction: str = Field(min_length=1)
    county: str = Field(min_length=1)
    case_type: str | None = None
    status: str | None = None
    filed_date: date | None = None
    hearing_date: date | None = None
    approval_date: date | None = None
    description: str | None = None
    site: Site | None = None
    entities: list[Entity] = Field(default_factory=list)
    provenance: list[Provenance] = Field(default_factory=list)

    @property
    def has_hearing(self) -> bool:
        """Return true when a public hearing date is present."""

        return self.hearing_date is not None

    @property
    def is_approved(self) -> bool:
        """Return true when the case status appears approved."""

        if self.status is None:
            return False
        return self.status.strip().lower() in {"approved", "adopted", "approved with conditions"}
