"""SQLite-backed source registry store."""

from __future__ import annotations

import json
from collections.abc import Iterable

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from constructionsight.models import Jurisdiction, PublicSource
from constructionsight.storage.orm import SourceRecord


class SourceRegistryStore:
    """Repository object for persisted public-source registry records."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def acquire_authorized_mutation_lock(self) -> None:
        """Serialize an authorized registry state read through its mutation commit.

        Source-registry authorization is bound to the exact current registry digest.
        SQLite BEGIN IMMEDIATE reserves the sole writer slot before that digest is
        read, so another process cannot change the authoritative registry between the
        authorization decision and the protected upsert. Entering with an existing
        transaction is rejected because its earlier reads could already be stale.
        """

        if self.session.in_transaction():
            raise RuntimeError(
                "authorized source-registry mutation requires a fresh transaction"
            )
        bind = self.session.get_bind()
        if bind.dialect.name != "sqlite":
            raise RuntimeError(
                "authorized source-registry mutation currently requires SQLite "
                "BEGIN IMMEDIATE serialization"
            )
        self.session.execute(text("BEGIN IMMEDIATE"))

    def upsert_source(self, source: PublicSource) -> SourceRecord:
        """Insert or update a public-source registry record.

        The store flushes after each upsert so later reads inside the same
        transaction can see pending inserts and so repeated upserts update the
        existing row instead of creating a duplicate pending insert.
        """

        statement = select(SourceRecord).where(
            SourceRecord.source_name == source.source_name,
            SourceRecord.public_url == str(source.public_url),
        )
        existing = self.session.scalar(statement)

        if existing is None:
            existing = SourceRecord()
            self.session.add(existing)

        existing.jurisdiction_name = source.jurisdiction.name
        existing.county = source.jurisdiction.county
        existing.state = source.jurisdiction.state
        existing.jurisdiction_type = source.jurisdiction.jurisdiction_type
        existing.source_name = source.source_name
        existing.source_type = source.source_type.value
        existing.platform_family = source.platform_family.value
        existing.public_url = str(source.public_url)
        existing.record_categories_json = json.dumps(
            [category.value for category in source.record_categories],
            sort_keys=True,
        )
        existing.search_method = source.search_method
        existing.extraction_difficulty = source.extraction_difficulty.value
        existing.update_frequency = source.update_frequency
        existing.confidence_score = source.confidence_score
        existing.verification_status = source.verification_status.value
        existing.provenance_notes = source.provenance_notes
        existing.last_checked_date = source.last_checked_date

        self.session.flush()
        return existing

    def upsert_many(self, sources: Iterable[PublicSource]) -> int:
        """Insert or update many source records and return the count processed."""

        count = 0
        for source in sources:
            self.upsert_source(source)
            count += 1
        return count

    def list_sources(self) -> list[PublicSource]:
        """Return all persisted source records as Pydantic models."""

        self.session.flush()
        records = self.session.scalars(
            select(SourceRecord).order_by(SourceRecord.county, SourceRecord.jurisdiction_name)
        ).all()
        return [self._to_public_source(record) for record in records]

    def get_by_name(self, source_name: str) -> PublicSource | None:
        """Return an unambiguous source by name, if present."""

        self.session.flush()
        records = self.session.scalars(
            select(SourceRecord).where(SourceRecord.source_name == source_name)
        ).all()
        if not records:
            return None
        if len(records) != 1:
            raise ValueError(
                "source name is ambiguous; use source name and public URL identity"
            )
        return self._to_public_source(records[0])

    def get_by_identity(self, source_name: str, public_url: str) -> PublicSource | None:
        """Return one source by the persisted name/URL identity pair."""

        self.session.flush()
        record = self.session.scalar(
            select(SourceRecord).where(
                SourceRecord.source_name == source_name,
                SourceRecord.public_url == public_url,
            )
        )
        if record is None:
            return None
        return self._to_public_source(record)

    @staticmethod
    def _to_public_source(record: SourceRecord) -> PublicSource:
        """Convert a persisted ORM record to a PublicSource model."""

        return PublicSource.model_validate(
            {
                "jurisdiction": Jurisdiction(
                    name=record.jurisdiction_name,
                    county=record.county,
                    state=record.state,
                    jurisdiction_type=record.jurisdiction_type,
                ).model_dump(),
                "source_name": record.source_name,
                "source_type": record.source_type,
                "platform_family": record.platform_family,
                "public_url": record.public_url,
                "record_categories": json.loads(record.record_categories_json),
                "search_method": record.search_method,
                "extraction_difficulty": record.extraction_difficulty,
                "update_frequency": record.update_frequency,
                "confidence_score": record.confidence_score,
                "verification_status": record.verification_status,
                "provenance_notes": record.provenance_notes,
                "last_checked_date": record.last_checked_date,
            }
        )
