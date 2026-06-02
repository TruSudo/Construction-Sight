"""Stores for normalized ConstructionSight domain records."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from constructionsight.entity_models import Entity
from constructionsight.site_models import Site
from constructionsight.storage.domain_orm import EntityRecord, SiteRecord
from constructionsight.storage.domain_serialization import json_to_list, models_to_json


class SiteStore:
    """Repository object for normalized site records."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(self, site: Site) -> SiteRecord:
        """Insert or update a site record."""

        record = self.session.scalar(select(SiteRecord).where(SiteRecord.site_key == site.site_key))
        if record is None:
            record = SiteRecord()
            self.session.add(record)

        record.site_key = site.site_key
        record.county = site.county
        record.state = site.state
        record.jurisdiction = site.jurisdiction
        record.apn = site.apn
        record.address = site.address
        record.city = site.city
        record.latitude = site.latitude
        record.longitude = site.longitude
        record.lot_size_acres = site.lot_size_acres
        record.provenance_json = models_to_json(site.provenance)

        self.session.flush()
        return record

    def get(self, site_key: str) -> Site | None:
        """Return one site by key."""

        self.session.flush()
        record = self.session.scalar(select(SiteRecord).where(SiteRecord.site_key == site_key))
        if record is None:
            return None
        return self._to_model(record)

    def list_all(self) -> list[Site]:
        """Return all persisted sites."""

        self.session.flush()
        records = self.session.scalars(select(SiteRecord).order_by(SiteRecord.site_key)).all()
        return [self._to_model(record) for record in records]

    @staticmethod
    def _to_model(record: SiteRecord) -> Site:
        """Convert an ORM site record to a Pydantic model."""

        return Site.model_validate(
            {
                "site_key": record.site_key,
                "county": record.county,
                "state": record.state,
                "jurisdiction": record.jurisdiction,
                "apn": record.apn,
                "address": record.address,
                "city": record.city,
                "latitude": record.latitude,
                "longitude": record.longitude,
                "lot_size_acres": record.lot_size_acres,
                "provenance": json_to_list(record.provenance_json),
            }
        )


class EntityStore:
    """Repository object for normalized entity records."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(self, entity: Entity) -> EntityRecord:
        """Insert or update an entity record."""

        record = self.session.scalar(
            select(EntityRecord).where(EntityRecord.entity_key == entity.entity_key)
        )
        if record is None:
            record = EntityRecord()
            self.session.add(record)

        record.entity_key = entity.entity_key
        record.name = entity.name
        record.role = entity.role.value
        record.license_number = entity.license_number
        record.business_address = entity.business_address
        record.jurisdiction = entity.jurisdiction
        record.county = entity.county
        record.state = entity.state
        record.provenance_json = models_to_json(entity.provenance)

        self.session.flush()
        return record

    def get(self, entity_key: str) -> Entity | None:
        """Return one entity by key."""

        self.session.flush()
        record = self.session.scalar(select(EntityRecord).where(EntityRecord.entity_key == entity_key))
        if record is None:
            return None
        return self._to_model(record)

    def list_all(self) -> list[Entity]:
        """Return all persisted entities."""

        self.session.flush()
        records = self.session.scalars(select(EntityRecord).order_by(EntityRecord.entity_key)).all()
        return [self._to_model(record) for record in records]

    @staticmethod
    def _to_model(record: EntityRecord) -> Entity:
        """Convert an ORM entity record to a Pydantic model."""

        return Entity.model_validate(
            {
                "entity_key": record.entity_key,
                "name": record.name,
                "role": record.role,
                "license_number": record.license_number,
                "business_address": record.business_address,
                "jurisdiction": record.jurisdiction,
                "county": record.county,
                "state": record.state,
                "provenance": json_to_list(record.provenance_json),
            }
        )
