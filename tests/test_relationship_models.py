import pytest
from pydantic import ValidationError

from constructionsight.domain_types import RelationshipType
from constructionsight.provenance import Provenance, ProvenanceConfidenceBasis
from constructionsight.relationship_models import RelationshipRecord


def test_relationship_model_accepts_low_confidence_without_provenance() -> None:
    relationship = RelationshipRecord(
        relationship_key="relationship:test:001",
        subject_key="entity:test:a",
        relationship_type=RelationshipType.RELATED_TO,
        object_key="project:test:b",
        confidence_score=25,
    )

    assert relationship.is_high_confidence is False


def test_relationship_model_requires_provenance_for_high_confidence() -> None:
    with pytest.raises(ValidationError):
        RelationshipRecord(
            relationship_key="relationship:test:high-no-evidence",
            subject_key="entity:test:a",
            relationship_type=RelationshipType.ASSOCIATED_WITH,
            object_key="project:test:b",
            confidence_score=90,
        )


def test_relationship_model_accepts_high_confidence_with_provenance() -> None:
    provenance = Provenance(
        source_name="Synthetic Public Source",
        adapter_family="synthetic-test",
        raw_reference="synthetic:test",
        evidence_text="retained synthetic public evidence",
        confidence_basis=ProvenanceConfidenceBasis.DETERMINISTIC_NORMALIZATION,
    )
    relationship = RelationshipRecord(
        relationship_key="relationship:test:high-with-evidence",
        subject_key="entity:test:a",
        relationship_type=RelationshipType.ASSOCIATED_WITH,
        object_key="project:test:b",
        confidence_score=90,
        provenance=[provenance],
    )

    assert relationship.is_high_confidence is True
    assert relationship.provenance[0].band.value == "high"
