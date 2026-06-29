from constructionsight.intake_models import (
    ExtractedMaterialFact,
    FormatDetection,
    IntakeEvidenceRef,
    IntakeRouting,
    IntakeUnderstandingStatus,
    MaterialFactKind,
    UniversalIntakeRecord,
)
from constructionsight.site_resolution_models import SiteResolutionStatus
from constructionsight.site_resolution_service import (
    build_site_resolution_input_from_intake,
    normalize_address,
    normalize_apn,
    resolve_site_from_intake,
)


def _intake(facts: list[ExtractedMaterialFact]) -> UniversalIntakeRecord:
    return UniversalIntakeRecord(
        intake_id="intake:test",
        evidence=IntakeEvidenceRef(
            evidence_id="evidence:test",
            source_name="test source",
            byte_count=10,
            sha256="0" * 64,
        ),
        format_detection=FormatDetection(format_family="plain_text"),
        understanding_status=IntakeUnderstandingStatus.PARTIALLY_UNDERSTOOD,
        routing=IntakeRouting.OPPORTUNITY_INTAKE,
        extracted_facts=facts,
        source_hints={"county": "San Bernardino County"},
        next_action="test",
    )


def _fact(
    fact_id: str,
    fact_kind: MaterialFactKind,
    value: str,
) -> ExtractedMaterialFact:
    return ExtractedMaterialFact(
        fact_id=fact_id,
        fact_kind=fact_kind,
        value=value,
        evidence_id="evidence:test",
    )


def test_normalize_apn_and_address_are_deterministic() -> None:
    assert normalize_apn("123-456-78") == "12345678"
    assert normalize_address("  123   Main St  ") == "123 MAIN ST"


def test_build_site_resolution_input_from_intake_extracts_site_identifiers() -> None:
    record = _intake(
        [
            _fact("fact:1", MaterialFactKind.APN, "123-456-78"),
            _fact("fact:2", MaterialFactKind.ADDRESS, "123 Main St"),
            _fact("fact:3", MaterialFactKind.AGENCY, "City of Hesperia"),
        ]
    )

    site_input = build_site_resolution_input_from_intake(record)

    assert [identifier.identifier_kind for identifier in site_input.identifiers] == [
        "apn",
        "address",
        "jurisdiction",
    ]
    assert site_input.identifiers[0].normalized_value == "12345678"
    assert site_input.identifiers[1].normalized_value == "123 MAIN ST"
    assert site_input.source_hints["county"] == "San Bernardino County"


def test_resolve_site_from_intake_creates_strong_site_anchor() -> None:
    record = _intake(
        [
            _fact("fact:1", MaterialFactKind.APN, "123-456-78"),
            _fact("fact:2", MaterialFactKind.ADDRESS, "123 Main St"),
            _fact("fact:3", MaterialFactKind.KEYWORD, "34.123456, -117.123456"),
        ]
    )

    result = resolve_site_from_intake(record)
    candidate = result.candidates[0]

    assert result.status == SiteResolutionStatus.RESOLVED
    assert result.primary_site_key == candidate.site_key
    assert candidate.apn == "12345678"
    assert candidate.address == "123 MAIN ST"
    assert candidate.latitude == 34.123456
    assert candidate.longitude == -117.123456
    assert candidate.confidence_score == 95
    assert candidate.match_strength == "exact"


def test_resolve_site_from_intake_exposes_conflicting_apns() -> None:
    record = _intake(
        [
            _fact("fact:1", MaterialFactKind.APN, "123-456-78"),
            _fact("fact:2", MaterialFactKind.APN, "999-888-77"),
            _fact("fact:3", MaterialFactKind.ADDRESS, "123 Main St"),
        ]
    )

    result = resolve_site_from_intake(record)

    assert result.status == SiteResolutionStatus.CONFLICTING
    assert result.conflicts == ["multiple apn values found: 12345678, 99988877"]
    assert (
        "conflicts must be resolved before treating this as one parcel"
        in result.limitations
    )


def test_resolve_site_from_intake_allows_partial_address_anchor() -> None:
    record = _intake([_fact("fact:1", MaterialFactKind.ADDRESS, "123 Main St")])

    result = resolve_site_from_intake(record)
    candidate = result.candidates[0]

    assert result.status == SiteResolutionStatus.PARTIAL
    assert candidate.confidence_score == 30
    assert "no APN was available for parcel-exact matching" in candidate.limitations
