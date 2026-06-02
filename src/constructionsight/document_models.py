"""Document domain models for ConstructionSight."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl

from constructionsight.provenance import Provenance


class DocumentRecord(BaseModel):
    """Normalized public document reference or text extraction."""

    document_key: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    title: str | None = None
    url: HttpUrl | None = None
    document_type: str | None = None
    captured_at: datetime | None = None
    text_extract: str | None = None
    provenance: list[Provenance] = Field(default_factory=list)

    @property
    def has_text(self) -> bool:
        """Return true when extracted text is present."""

        return bool(self.text_extract and self.text_extract.strip())

    @property
    def has_url(self) -> bool:
        """Return true when a public document URL is present."""

        return self.url is not None
