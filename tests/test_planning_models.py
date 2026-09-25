from datetime import date

import pytest
from pydantic import ValidationError

from constructionsight.domain_types import PartyRole
from constructionsight.entity_models import Entity
from constructionsight.planning_models import PlanningCaseRecord
from constructionsight.provenance import Provenance, ProvenanceConfidenceBasis
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


@pytest.mark.parametrize(
    ("filed", "hearing", "approval"),
    (
        (date(2026, 3, 2), date(2026, 3, 1), None),
        (date(2026, 3, 2), None, date(2026, 3, 1)),
        (None, date(2026, 3, 2), date(2026, 3, 1)),
    ),
)
def test_planning_case_rejects_contradictory_lifecycle_dates(
    filed: date | None,
    hearing: date | None,
    approval: date | None,
) -> None:
    with pytest.raises(ValidationError):
        PlanningCaseRecord(
            case_key="planning:test:chronology",
            case_number="PC-CHRONO",
            jurisdiction="Test Jurisdiction",
            county="Test County",
            filed_date=filed,
            hearing_date=hearing,
            approval_date=approval,
        )


def test_planning_case_allows_partial_and_ordered_lifecycle_dates() -> None:
    partial = PlanningCaseRecord(
        case_key="planning:test:partial",
        case_number="PC-PARTIAL",
        jurisdiction="Test Jurisdiction",
        county="Test County",
        hearing_date=date(2026, 3, 2),
    )
    ordered = PlanningCaseRecord(
        case_key="planning:test:ordered",
        case_number="PC-ORDERED",
        jurisdiction="Test Jurisdiction",
        county="Test County",
        filed_date=date(2026, 3, 1),
        hearing_date=date(2026, 3, 2),
        approval_date=date(2026, 3, 3),
    )

    assert partial.filed_date is None
    assert ordered.approval_date == date(2026, 3, 3)


def test_planning_case_links_site_entity_and_provenance() -> None:
    site = Site(site_key="site:test:planning", county="Test County")
    entity = Entity(
        entity_key="entity:test:applicant",
        name="Synthetic Applicant LLC",
        role=PartyRole.APPLICANT,
    )
    provenance = Provenance(
        source_name="Synthetic Public Source",
        adapter_family="synthetic-test",
        raw_reference="synthetic:test",
        evidence_text="retained synthetic public evidence",
        confidence_basis=ProvenanceConfidenceBasis.DETERMINISTIC_NORMALIZATION,
    )

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
