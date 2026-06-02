import pytest
from pydantic import ValidationError

from constructionsight.agenda_models import AgendaItemRecord
from constructionsight.domain_types import PartyRole
from constructionsight.entity_models import Entity
from constructionsight.provenance import Provenance
from constructionsight.site_models import Site


def test_agenda_item_accepts_minimum_required_fields() -> None:
    item = AgendaItemRecord(
        agenda_key="agenda:test:001",
        meeting_body="Test Planning Body",
        jurisdiction="Test Jurisdiction",
        county="Test County",
    )

    assert item.agenda_key == "agenda:test:001"
    assert item.has_documents is False
    assert item.appears_development_related is False


def test_agenda_item_detects_development_related_terms() -> None:
    item = AgendaItemRecord(
        agenda_key="agenda:test:development",
        meeting_body="Test Planning Body",
        jurisdiction="Test Jurisdiction",
        county="Test County",
        title="Synthetic Tentative Tract Review",
        description="Consideration of a site plan and design review item.",
    )

    assert item.appears_development_related is True


def test_agenda_item_detects_document_links() -> None:
    item = AgendaItemRecord(
        agenda_key="agenda:test:documents",
        meeting_body="Test Planning Body",
        jurisdiction="Test Jurisdiction",
        county="Test County",
        document_urls=["https://example.gov/staff-report.pdf"],
    )

    assert item.has_documents is True


def test_agenda_item_requires_meeting_body() -> None:
    with pytest.raises(ValidationError):
        AgendaItemRecord(
            agenda_key="agenda:test:missing-body",
            meeting_body="",
            jurisdiction="Test Jurisdiction",
            county="Test County",
        )


def test_agenda_item_links_site_entity_and_provenance() -> None:
    site = Site(site_key="site:test:agenda", county="Test County")
    entity = Entity(
        entity_key="entity:test:developer",
        name="Synthetic Developer LLC",
        role=PartyRole.DEVELOPER,
    )
    provenance = Provenance(source_name="Synthetic Public Source", confidence_score=80)

    item = AgendaItemRecord(
        agenda_key="agenda:test:linked",
        meeting_body="Test Planning Body",
        jurisdiction="Test Jurisdiction",
        county="Test County",
        site=site,
        entities=[entity],
        provenance=[provenance],
    )

    assert item.site is not None
    assert item.site.site_key == "site:test:agenda"
    assert item.entities[0].role is PartyRole.DEVELOPER
    assert item.provenance[0].band.value == "high"
