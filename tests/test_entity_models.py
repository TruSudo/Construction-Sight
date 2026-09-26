from constructionsight.domain_types import PartyRole
from constructionsight.entity_models import Entity
from constructionsight.provenance import Provenance, ProvenanceConfidenceBasis


def test_entity_model_accepts_minimum_required_fields() -> None:
    entity = Entity(entity_key="entity:test:001", name="Synthetic Entity")

    assert entity.entity_key == "entity:test:001"
    assert entity.name == "Synthetic Entity"
    assert entity.role is PartyRole.UNKNOWN
    assert entity.state == "CA"


def test_entity_model_preserves_role_and_provenance() -> None:
    provenance = Provenance(
        source_name="Synthetic Public Source",
        adapter_family="synthetic-test",
        raw_reference="synthetic:test",
        evidence_text="retained synthetic public evidence",
        confidence_basis=ProvenanceConfidenceBasis.DETERMINISTIC_NORMALIZATION,
    )
    entity = Entity(
        entity_key="entity:test:contractor",
        name="Synthetic Builder LLC",
        role=PartyRole.GENERAL_CONTRACTOR,
        license_number="000000",
        provenance=[provenance],
    )

    assert entity.role is PartyRole.GENERAL_CONTRACTOR
    assert entity.license_number == "000000"
    assert entity.provenance[0].band.value == "high"
