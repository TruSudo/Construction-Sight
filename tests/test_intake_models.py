import hashlib

import pytest

from constructionsight.intake_models import (
    DigitalFormatFamily,
    ExtractedMaterialFact,
    FactConfidence,
    FormatDetection,
    IntakeEvidenceRef,
    IntakeRouting,
    IntakeUnderstandingStatus,
    MaterialFactKind,
    UniversalIntakeRecord,
    UnmappedEvidenceFragment,
)


def test_intake_evidence_ref_requires_lower_hex_sha256() -> None:
    with pytest.raises(ValueError, match="sha256"):
        IntakeEvidenceRef(
            evidence_id="evidence:bad",
            source_name="Example",
            byte_count=1,
            sha256="A" * 64,
        )


def test_universal_intake_rejects_preserved_only_with_extracted_facts() -> None:
    digest = hashlib.sha256(b"example").hexdigest()
    evidence = IntakeEvidenceRef(
        evidence_id="evidence:example",
        source_name="Example",
        byte_count=7,
        sha256=digest,
    )
    fact = ExtractedMaterialFact(
        fact_id="fact:example:001",
        fact_kind=MaterialFactKind.ADDRESS,
        value="123 Main St",
        confidence=FactConfidence.SOURCE_CLAIMED,
        evidence_id="evidence:example",
    )

    with pytest.raises(ValueError, match="preserved-only"):
        UniversalIntakeRecord(
            intake_id="intake:example",
            evidence=evidence,
            format_detection=FormatDetection(format_family=DigitalFormatFamily.BINARY),
            understanding_status=IntakeUnderstandingStatus.PRESERVED_ONLY,
            routing=IntakeRouting.HUMAN_REVIEW,
            extracted_facts=[fact],
            unmapped_fragments=[
                UnmappedEvidenceFragment(
                    fragment_id="fragment:example:001",
                    evidence_id="evidence:example",
                    reason="binary requires review",
                )
            ],
            next_action="Review binary evidence.",
        )


def test_universal_intake_requires_facts_for_opportunity_route() -> None:
    digest = hashlib.sha256(b"example").hexdigest()
    evidence = IntakeEvidenceRef(
        evidence_id="evidence:example",
        source_name="Example",
        byte_count=7,
        sha256=digest,
    )

    with pytest.raises(ValueError, match="opportunity intake requires extracted facts"):
        UniversalIntakeRecord(
            intake_id="intake:example",
            evidence=evidence,
            format_detection=FormatDetection(format_family=DigitalFormatFamily.PLAIN_TEXT),
            understanding_status=IntakeUnderstandingStatus.PARTIALLY_UNDERSTOOD,
            routing=IntakeRouting.OPPORTUNITY_INTAKE,
            next_action="Review extracted facts.",
        )
