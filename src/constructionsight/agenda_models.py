"""Agenda and public meeting domain models for ConstructionSight."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, HttpUrl

from constructionsight.entity_models import Entity
from constructionsight.provenance import Provenance
from constructionsight.site_models import Site


class AgendaItemRecord(BaseModel):
    """Normalized public meeting agenda item or staff report item."""

    agenda_key: str = Field(min_length=1)
    meeting_body: str = Field(min_length=1)
    jurisdiction: str = Field(min_length=1)
    county: str = Field(min_length=1)
    meeting_date: date | None = None
    item_number: str | None = None
    title: str | None = None
    description: str | None = None
    document_urls: list[HttpUrl] = Field(default_factory=list)
    site: Site | None = None
    entities: list[Entity] = Field(default_factory=list)
    provenance: list[Provenance] = Field(default_factory=list)

    @property
    def has_documents(self) -> bool:
        """Return true when agenda documents are linked."""

        return bool(self.document_urls)

    @property
    def appears_development_related(self) -> bool:
        """Return true when agenda text contains common development-case terms."""

        searchable = " ".join(
            part for part in [self.title, self.description] if part is not None
        ).lower()
        terms = {
            "development agreement",
            "tentative tract",
            "conditional use permit",
            "site plan",
            "design review",
            "zoning amendment",
            "general plan amendment",
        }
        return any(term in searchable for term in terms)
