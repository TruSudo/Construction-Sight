import hashlib

import pytest
from pydantic import ValidationError

from constructionsight.domain_types import ConfidenceBand, confidence_band
from constructionsight.provenance import Provenance, ProvenanceConfidenceBasis


def _normalized_provenance(
    *,
    source_name: str = "County public portal",
    source_url: str = "https://example.gov/records",
) -> Provenance:
    return Provenance(
        source_name=source_name,
        source_url=source_url,
        adapter_family="synthetic-adapter",
        raw_reference="record:123",
        evidence_text="retained public record evidence",
        confidence_basis=ProvenanceConfidenceBasis.DETERMINISTIC_NORMALIZATION,
    )


def test_numeric_confidence_never_manufactures_verified_band() -> None:
    assert confidence_band(100) is ConfidenceBand.HIGH


def test_generic_provenance_rejects_self_asserted_verified_state() -> None:
    with pytest.raises(ValidationError):
        Provenance(
            source_name="Synthetic",
            verified=True,
        )


def test_generic_provenance_rejects_caller_supplied_confidence_score() -> None:
    with pytest.raises(ValidationError):
        Provenance(
            source_name="Synthetic",
            confidence_score=100,
        )


def test_assessed_provenance_requires_retained_evidence() -> None:
    with pytest.raises(ValidationError, match="evidence_text"):
        Provenance(
            source_name="Synthetic",
            adapter_family="synthetic-adapter",
            confidence_basis=ProvenanceConfidenceBasis.DETERMINISTIC_NORMALIZATION,
        )


def test_provenance_derives_evidence_digest_lineage_and_confidence() -> None:
    provenance = _normalized_provenance()

    assert provenance.evidence_sha256 == hashlib.sha256(
        b"retained public record evidence"
    ).hexdigest()
    assert provenance.lineage_id.startswith("provenance-lineage:")
    assert provenance.confidence_score == 75
    assert provenance.band is ConfidenceBand.HIGH
    assert provenance.verified is False


def test_same_source_lineage_cannot_be_made_independent_by_record_reference() -> None:
    first = _normalized_provenance()
    second = first.model_copy(update={"raw_reference": "record:456"})

    assert first.lineage_id == second.lineage_id


def test_distinct_source_lineage_changes_derived_lineage_identity() -> None:
    first = _normalized_provenance()
    second = _normalized_provenance(
        source_name="Independent county archive",
        source_url="https://archive.example.gov/records",
    )

    assert first.lineage_id != second.lineage_id
