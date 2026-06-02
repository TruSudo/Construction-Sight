"""CEQA domain models for ConstructionSight."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from constructionsight.entity_models import Entity
from constructionsight.provenance import Provenance
from constructionsight.site_models import Site


class CeqaRecord(BaseModel):
    """Normalized CEQA environmental review record."""

    ceqa_key: str = Field(min_length=1)
    title: str = Field(min_length=1)
    county: str | None = None
    lead_agency: str | None = None
    document_type: str | None = None
    state_clearinghouse_number: str | None = None
    received_date: date | None = None
    posted_date: date | None = None
    project_location: str | None = None
    description: str | None = None
    site: Site | None = None
    entities: list[Entity] = Field(default_factory=list)
    provenance: list[Provenance] = Field(default_factory=list)

    @property
    def has_state_clearinghouse_number(self) -> bool:
        """Return true when the record has a State Clearinghouse number."""

        return bool(self.state_clearinghouse_number and self.state_clearinghouse_number.strip())

    @property
    def is_high_signal_document(self) -> bool:
        """Return true for CEQA document types that usually indicate advanced project activity."""

        if self.document_type is None:
            return False
        normalized = self.document_type.strip().lower()
        return normalized in {
            "environmental impact report",
            "eir",
            "mitigated negative declaration",
            "mnd",
            "notice of preparation",
            "nop",
        }
