import pytest
from pydantic import ValidationError

from constructionsight.domain_types import PartyRole
from constructionsight.entity_models import Entity
from constructionsight.permit_models import PermitRecord
from constructionsight.provenance import Provenance
from constructionsight.site_models import Site


def test_permit_model_accepts_minimum_required_fields() -> None:
    permit = PermitRecord(
        permit_key="permit:test:001",
        permit_number="P-001",
        jurisdiction="Test Jurisdiction",
        county="Test County",
    )

    assert permit.permit_key == "permit:test:001"
    assert permit.permit_number == "P-001"
    assert permit.is_issued is False


def test_permit_model_detects_issued_status() -> None:
    permit = PermitRecord(
        permit_key="permit:test:issued",
        permit_number="P-002",
        jurisdiction="Test Jurisdiction",
        county="Test County",
        status="Issued",
    )

    assert permit.is_issued is True


def test_permit_model_rejects_negative_valuation() -> None:
    with pytest.raises(ValidationError):
        PermitRecord(
            permit_key="permit:test:negative",
            permit_number="P-003",
            jurisdiction="Test Jurisdiction",
            county="Test County",
            valuation=-1,
        )


def test_permit_model_links_site_entity_and_provenance() -> None:
    site = Site(site_key="site:test:001", county="Test County")
    entity = Entity(
        entity_key="entity:test:builder",
        name="Synthetic Builder LLC",
        role=PartyRole.GENERAL_CONTRACTOR,
    )
    provenance = Provenance(
        source_name="Synthetic Public Source", confidence_score=90, verified=True
    )

    permit = PermitRecord(
        permit_key="permit:test:linked",
        permit_number="P-004",
        jurisdiction="Test Jurisdiction",
        county="Test County",
        site=site,
        entities=[entity],
        provenance=[provenance],
    )

    assert permit.site is not None
    assert permit.site.site_key == "site:test:001"
    assert permit.entities[0].role is PartyRole.GENERAL_CONTRACTOR
    assert permit.provenance[0].band.value == "verified"
