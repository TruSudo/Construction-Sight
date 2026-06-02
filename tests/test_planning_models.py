import pytest
from pydantic import ValidationError

from constructionsight.domain_types import PartyRole
from constructionsight.entity_models import Entity
from constructionsight.planning_models import PlanningCaseRecord
from constructionsight.provenance import Provenance
from constructionsight.site_models import Site


def test_planning_case_accepts_minimum_required_fields() -> None:
    case = PlanningCaseRecord(
        case_key="planning:test:001",
        case_number="PC-001",
        jurisdiction="Test Jurisdiction",
        county="Test County",
    )

    assert case.case_key == "planning:test:001"
    assert case.has_hearing is False
    assert case.is_approved is False


def test_planning_case_detects_approval_status() -> None:
    case = PlanningCaseRecord(
        case_key="planning:test:approved",
        case_number="PC-002",
        jurisdiction="Test Jurisdiction",
        county="Test County",
        status="Approved With Conditions",
    )

    assert case.is_approved is True


def test_planning_case_requires_case_number() -> None:
    with pytest.raises(ValidationError):
        PlanningCaseRecord(
            case_key="planning:test:missing-number",
            case_number="",
            jurisdiction="Test Jurisdiction",
            county="Test County",
        )


def test_planning_case_links_site_entity_and_provenance() -> None:
    site = Site(site_key="site:test:planning", county="Test County")
    entity = Entity(
        entity_key="entity:test:applicant",
        name="Synthetic Applicant LLC",
        role=PartyRole.APPLICANT,
    )
    provenance = Provenance(source_name="Synthetic Public Source", confidence_score=75)

    case = PlanningCaseRecord(
        case_key="planning:test:linked",
        case_number="PC-003",
        jurisdiction="Test Jurisdiction",
        county="Test County",
        site=site,
        entities=[entity],
        provenance=[provenance],
    )

    assert case.site is not None
    assert case.site.site_key == "site:test:planning"
    assert case.entities[0].role is PartyRole.APPLICANT
    assert case.provenance[0].band.value == "high"
