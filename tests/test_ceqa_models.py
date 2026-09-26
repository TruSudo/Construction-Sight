import pytest
from pydantic import ValidationError

from constructionsight.ceqa_models import CeqaRecord
from constructionsight.domain_types import PartyRole
from constructionsight.entity_models import Entity
from constructionsight.provenance import Provenance, ProvenanceConfidenceBasis
from constructionsight.site_models import Site


def test_ceqa_record_accepts_minimum_required_fields() -> None:
    record = CeqaRecord(ceqa_key="ceqa:test:001", title="Synthetic CEQA Project")

    assert record.ceqa_key == "ceqa:test:001"
    assert record.title == "Synthetic CEQA Project"
    assert record.has_state_clearinghouse_number is False
    assert record.is_high_signal_document is False


def test_ceqa_record_detects_high_signal_document_type() -> None:
    record = CeqaRecord(
        ceqa_key="ceqa:test:eir",
        title="Synthetic Environmental Review",
        document_type="Environmental Impact Report",
        state_clearinghouse_number="2026000000",
    )

    assert record.has_state_clearinghouse_number is True
    assert record.is_high_signal_document is True


def test_ceqa_record_requires_title() -> None:
    with pytest.raises(ValidationError):
        CeqaRecord(ceqa_key="ceqa:test:missing-title", title="")


def test_ceqa_record_links_site_entity_and_provenance() -> None:
    site = Site(site_key="site:test:ceqa", county="Test County")
    entity = Entity(
        entity_key="entity:test:agency",
        name="Synthetic Lead Agency",
        role=PartyRole.AGENCY,
    )
    provenance = Provenance(
        source_name="Synthetic Public Source",
        adapter_family="synthetic-test",
        raw_reference="synthetic:test",
        evidence_text="retained synthetic public evidence",
        confidence_basis=ProvenanceConfidenceBasis.DETERMINISTIC_NORMALIZATION,
    )

    record = CeqaRecord(
        ceqa_key="ceqa:test:linked",
        title="Synthetic Linked CEQA Record",
        county="Test County",
        site=site,
        entities=[entity],
        provenance=[provenance],
    )

    assert record.site is not None
    assert record.site.site_key == "site:test:ceqa"
    assert record.entities[0].role is PartyRole.AGENCY
    assert record.provenance[0].band.value == "high"
