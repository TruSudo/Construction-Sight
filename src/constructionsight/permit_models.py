"""Permit domain models for ConstructionSight."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, model_validator

from constructionsight.entity_models import Entity
from constructionsight.provenance import Provenance
from constructionsight.site_models import Site


class PermitRecord(BaseModel):
    """Normalized permit record from a public permitting source."""

    permit_key: str = Field(min_length=1)
    permit_number: str = Field(min_length=1)
    jurisdiction: str = Field(min_length=1)
    county: str = Field(min_length=1)
    permit_type: str | None = None
    status: str | None = None
    applied_date: date | None = None
    issued_date: date | None = None
    finaled_date: date | None = None
    description: str | None = None
    valuation: float | None = Field(default=None, ge=0)
    square_feet: float | None = Field(default=None, ge=0)
    site: Site | None = None
    entities: list[Entity] = Field(default_factory=list)
    provenance: list[Provenance] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_lifecycle_order(self) -> PermitRecord:
        """Reject contradictory known permit lifecycle dates."""

        if (
            self.applied_date is not None
            and self.issued_date is not None
            and self.issued_date < self.applied_date
        ):
            raise ValueError("issued_date cannot precede applied_date")
        if (
            self.applied_date is not None
            and self.finaled_date is not None
            and self.finaled_date < self.applied_date
        ):
            raise ValueError("finaled_date cannot precede applied_date")
        if (
            self.issued_date is not None
            and self.finaled_date is not None
            and self.finaled_date < self.issued_date
        ):
            raise ValueError("finaled_date cannot precede issued_date")
        return self

    @property
    def is_issued(self) -> bool:
        """Return true when the permit status appears issued."""

        if self.status is None:
            return False
        return self.status.strip().lower() in {"issued", "permit issued"}
