"""Stores for normalized ConstructionSight domain records."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from constructionsight.entity_models import Entity
from constructionsight.permit_models import PermitRecord
from constructionsight.planning_models import PlanningCaseRecord
from constructionsight.site_models import Site
from constructionsight.storage.domain_orm import (
    EntityRecord,
    PermitDomainRecord,
    PlanningDomainRecord,
    SiteRecord,
)
from constructionsight.storage.domain_serialization import (
    json_to_dict,
    json_to_list,
    model_to_json,
    models_to_json,
)


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


class PermitStore:
    """Repository object for normalized permit records."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(self, permit: PermitRecord) -> PermitDomainRecord:
        """Insert or update a permit record."""

        record = self.session.scalar(
            select(PermitDomainRecord).where(PermitDomainRecord.permit_key == permit.permit_key)
        )
        if record is None:
            record = PermitDomainRecord()
            self.session.add(record)

        record.permit_key = permit.permit_key
        record.permit_number = permit.permit_number
        record.jurisdiction = permit.jurisdiction
        record.county = permit.county
        record.permit_type = permit.permit_type
        record.status = permit.status
        record.applied_date = permit.applied_date
        record.issued_date = permit.issued_date
        record.finaled_date = permit.finaled_date
        record.description = permit.description
        record.valuation = permit.valuation
        record.square_feet = permit.square_feet
        record.site_json = model_to_json(permit.site)
        record.entities_json = models_to_json(permit.entities)
        record.provenance_json = models_to_json(permit.provenance)

        self.session.flush()
        return record

    def get(self, permit_key: str) -> PermitRecord | None:
        """Return one permit by key."""

        self.session.flush()
        record = self.session.scalar(
            select(PermitDomainRecord).where(PermitDomainRecord.permit_key == permit_key)
        )
        if record is None:
            return None
        return self._to_model(record)

    def list_all(self) -> list[PermitRecord]:
        """Return all persisted permit records."""

        self.session.flush()
        records = self.session.scalars(
            select(PermitDomainRecord).order_by(PermitDomainRecord.permit_key)
        ).all()
        return [self._to_model(record) for record in records]

    @staticmethod
    def _to_model(record: PermitDomainRecord) -> PermitRecord:
        """Convert an ORM permit record to a Pydantic model."""

        return PermitRecord.model_validate(
            {
                "permit_key": record.permit_key,
                "permit_number": record.permit_number,
                "jurisdiction": record.jurisdiction,
                "county": record.county,
                "permit_type": record.permit_type,
                "status": record.status,
                "applied_date": record.applied_date,
                "issued_date": record.issued_date,
                "finaled_date": record.finaled_date,
                "description": record.description,
                "valuation": record.valuation,
                "square_feet": record.square_feet,
                "site": json_to_dict(record.site_json),
                "entities": json_to_list(record.entities_json),
                "provenance": json_to_list(record.provenance_json),
            }
        )


class PlanningCaseStore:
    """Repository object for normalized planning case records."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(self, case: PlanningCaseRecord) -> PlanningDomainRecord:
        """Insert or update a planning case record."""

        record = self.session.scalar(
            select(PlanningDomainRecord).where(PlanningDomainRecord.case_key == case.case_key)
        )
        if record is None:
            record = PlanningDomainRecord()
            self.session.add(record)

        record.case_key = case.case_key
        record.case_number = case.case_number
        record.jurisdiction = case.jurisdiction
        record.county = case.county
        record.case_type = case.case_type
        record.status = case.status
        record.filed_date = case.filed_date
        record.hearing_date = case.hearing_date
        record.approval_date = case.approval_date
        record.description = case.description
        record.site_json = model_to_json(case.site)
        record.entities_json = models_to_json(case.entities)
        record.provenance_json = models_to_json(case.provenance)

        self.session.flush()
        return record

    def get(self, case_key: str) -> PlanningCaseRecord | None:
        """Return one planning case by key."""

        self.session.flush()
        record = self.session.scalar(
            select(PlanningDomainRecord).where(PlanningDomainRecord.case_key == case_key)
        )
        if record is None:
            return None
        return self._to_model(record)

    def list_all(self) -> list[PlanningCaseRecord]:
        """Return all persisted planning cases."""

        self.session.flush()
        records = self.session.scalars(
            select(PlanningDomainRecord).order_by(PlanningDomainRecord.case_key)
        ).all()
        return [self._to_model(record) for record in records]

    @staticmethod
    def _to_model(record: PlanningDomainRecord) -> PlanningCaseRecord:
        """Convert an ORM planning case record to a Pydantic model."""

        return PlanningCaseRecord.model_validate(
            {
                "case_key": record.case_key,
                "case_number": record.case_number,
                "jurisdiction": record.jurisdiction,
                "county": record.county,
                "case_type": record.case_type,
                "status": record.status,
                "filed_date": record.filed_date,
                "hearing_date": record.hearing_date,
                "approval_date": record.approval_date,
                "description": record.description,
                "site": json_to_dict(record.site_json),
                "entities": json_to_list(record.entities_json),
                "provenance": json_to_list(record.provenance_json),
            }
        )
