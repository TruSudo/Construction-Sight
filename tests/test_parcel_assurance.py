from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from constructionsight.parcel_assurance import build_parcel_assurance_report
from constructionsight.parcel_assurance_models import (
    ParcelAssuranceReviewStatus,
    ParcelAssuranceSourceContext,
    ParcelAssuranceStatus,
    ParcelClaimMethod,
    ParcelEvidenceAuthority,
    ParcelEvidenceClaim,
)
from constructionsight.parcel_core_models import ParcelCoreRecord
from constructionsight.parcel_source_models import ParcelFieldRole


OBSERVED_AT = datetime(2026, 7, 14, 12, 0, tzinfo=UTC)


def _record(
    *,
    source_key: str,
    parcel_record_id: str,
    address: str = "1 Main St",
    zoning: str = "industrial",
    geometry_hash: str = "geometry:test",
):
    geometry = SimpleNamespace(
        geometry_hash=geometry_hash,
        raw_geometry="POINT(-117.0 34.0)",
        centroid_latitude=34.0,
        centroid_longitude=-117.0,
        limitations=["point geometry only"],
    )
    return SimpleNamespace(
        parcel_record_id=parcel_record_id,
        source_key=source_key,
        source_record_id=f"row:{parcel_record_id}",
        apn="123-456-78",
        normalized_apn="12345678",
        county="San Bernardino",
        state="CA",
        address=address,
        normalized_address=" ".join(address.split()).upper(),
        jurisdiction="Redlands",
        zoning=zoning,
        land_use="warehouse",
        acreage=2.5,
        geometry=geometry,
        source_updated_at=OBSERVED_AT - timedelta(days=1),
        limitations=["not survey-grade"],
        created_at=OBSERVED_AT,
    )


def _context(
    source_key: str,
    lineage_key: str,
    *,
    authoritative_fields: list[ParcelFieldRole] | None = None,
) -> ParcelAssuranceSourceContext:
    return ParcelAssuranceSourceContext(
        source_key=source_key,
        lineage_key=lineage_key,
        default_authority=ParcelEvidenceAuthority.OFFICIAL,
        authoritative_fields=authoritative_fields or [],
        limitations=[f"{source_key} currency must be checked"],
    )


def _field(report, field_role: ParcelFieldRole):
    return next(
        assurance
        for assurance in report.field_assurances
        if assurance.field_role == field_role
    )


def test_authoritative_claim_and_independent_lineage_are_corroborated() -> None:
    report = build_parcel_assurance_report(
        records=[
            _record(source_key="assessor", parcel_record_id="parcel:assessor"),
            _record(source_key="county-gis", parcel_record_id="parcel:gis"),
        ],
        source_contexts=[
            _context(
                "assessor",
                "county-assessor-roll",
                authoritative_fields=[ParcelFieldRole.APN, ParcelFieldRole.ACREAGE],
            ),
            _context("county-gis", "county-gis-system"),
        ],
        field_roles=[ParcelFieldRole.APN, ParcelFieldRole.ACREAGE],
        generated_at=OBSERVED_AT,
    )

    apn = _field(report, ParcelFieldRole.APN)
    assert apn.status == ParcelAssuranceStatus.AUTHORITATIVE_CORROBORATED
    assert apn.selected_normalized_value == "12345678"
    assert apn.independent_lineage_count == 2
    assert apn.authoritative_claim_count == 1
    assert report.review_status == ParcelAssuranceReviewStatus.EVALUATED
    assert report.source_count == 2
    assert report.independent_lineage_count == 2


def test_shared_lineage_is_not_counted_as_independent_corroboration() -> None:
    report = build_parcel_assurance_report(
        records=[
            _record(source_key="portal", parcel_record_id="parcel:portal"),
            _record(source_key="mirror", parcel_record_id="parcel:mirror"),
        ],
        source_contexts=[
            _context("portal", "county-gis-system"),
            _context("mirror", "county-gis-system"),
        ],
        field_roles=[ParcelFieldRole.ZONING],
        generated_at=OBSERVED_AT,
    )

    zoning = _field(report, ParcelFieldRole.ZONING)
    assert zoning.status == ParcelAssuranceStatus.DEPENDENT_SOURCES_AGREE
    assert zoning.independent_lineage_count == 1
    assert zoning.value_groups[0].lineage_keys == ["county-gis-system"]


def test_conflict_retains_each_value_and_requires_review() -> None:
    report = build_parcel_assurance_report(
        records=[
            _record(
                source_key="assessor",
                parcel_record_id="parcel:assessor",
                zoning="industrial",
            ),
            _record(
                source_key="planning",
                parcel_record_id="parcel:planning",
                zoning="commercial",
            ),
        ],
        source_contexts=[
            _context("assessor", "county-assessor-roll"),
            _context(
                "planning",
                "county-planning-system",
                authoritative_fields=[ParcelFieldRole.ZONING],
            ),
        ],
        field_roles=[ParcelFieldRole.ZONING],
        generated_at=OBSERVED_AT,
    )

    zoning = _field(report, ParcelFieldRole.ZONING)
    assert zoning.status == ParcelAssuranceStatus.CONFLICT
    assert zoning.selected_normalized_value is None
    assert zoning.requires_human_review is True
    assert [group.normalized_value for group in zoning.value_groups] == [
        "commercial",
        "industrial",
    ]
    assert report.review_status == ParcelAssuranceReviewStatus.REVIEW_REQUIRED


def test_missing_field_is_explicit_and_does_not_assert_absence() -> None:
    report = build_parcel_assurance_report(
        records=[_record(source_key="assessor", parcel_record_id="parcel:assessor")],
        source_contexts=[_context("assessor", "county-assessor-roll")],
        field_roles=[ParcelFieldRole.OWNER],
        generated_at=OBSERVED_AT,
    )

    owner = _field(report, ParcelFieldRole.OWNER)
    assert owner.status == ParcelAssuranceStatus.MISSING
    assert owner.claim_ids == []
    assert owner.limitations == [
        "Missing evidence is not evidence that the fact is absent."
    ]
    assert report.review_status == ParcelAssuranceReviewStatus.INCOMPLETE


def test_report_identity_is_independent_of_generation_time() -> None:
    record = _record(source_key="assessor", parcel_record_id="parcel:assessor")
    context = _context("assessor", "county-assessor-roll")

    first = build_parcel_assurance_report(
        records=[record],
        source_contexts=[context],
        field_roles=[ParcelFieldRole.APN],
        generated_at=OBSERVED_AT,
    )
    second = build_parcel_assurance_report(
        records=[record],
        source_contexts=[context],
        field_roles=[ParcelFieldRole.APN],
        generated_at=OBSERVED_AT + timedelta(hours=1),
    )

    assert first.report_id == second.report_id
    assert first.claims[0].claim_id == second.claims[0].claim_id
    assert first.generated_at != second.generated_at


def test_builder_requires_explicit_context_and_one_current_record_per_source() -> None:
    record = _record(source_key="assessor", parcel_record_id="parcel:assessor")
    with pytest.raises(ValueError, match="missing parcel assurance source context"):
        build_parcel_assurance_report(records=[record], source_contexts=[])

    duplicate_source = _record(
        source_key="assessor",
        parcel_record_id="parcel:assessor:newer",
    )
    with pytest.raises(ValueError, match="one current record per source key"):
        build_parcel_assurance_report(
            records=[record, duplicate_source],
            source_contexts=[_context("assessor", "county-assessor-roll")],
        )


def test_authority_must_be_field_specific_and_direct() -> None:
    with pytest.raises(ValidationError, match="assigned by field"):
        ParcelAssuranceSourceContext(
            source_key="assessor",
            lineage_key="county-assessor-roll",
            default_authority=ParcelEvidenceAuthority.AUTHORITATIVE,
        )

    with pytest.raises(ValidationError, match="cannot be authoritative"):
        ParcelEvidenceClaim(
            claim_id="parcel-claim:test",
            parcel_record_id="parcel:test",
            source_key="assessor",
            lineage_key="county-assessor-roll",
            field_role=ParcelFieldRole.APN,
            original_value="123-456-78",
            normalized_value="12345678",
            authority=ParcelEvidenceAuthority.AUTHORITATIVE,
            claim_method=ParcelClaimMethod.INFERENCE,
            evidence_reference="parcel-record:parcel:test",
            observed_at=OBSERVED_AT,
        )


def test_derived_centroid_does_not_inherit_authoritative_status() -> None:
    report = build_parcel_assurance_report(
        records=[_record(source_key="gis", parcel_record_id="parcel:gis")],
        source_contexts=[
            _context(
                "gis",
                "county-gis-system",
                authoritative_fields=[ParcelFieldRole.CENTROID_LATITUDE],
            )
        ],
        field_roles=[ParcelFieldRole.CENTROID_LATITUDE],
        generated_at=OBSERVED_AT,
    )

    claim = report.claims[0]
    latitude = _field(report, ParcelFieldRole.CENTROID_LATITUDE)
    assert claim.claim_method == ParcelClaimMethod.DETERMINISTIC_DERIVATION
    assert claim.authority == ParcelEvidenceAuthority.OFFICIAL
    assert latitude.status == ParcelAssuranceStatus.SINGLE_SOURCE


def test_report_payload_preserves_claim_provenance_without_global_score() -> None:
    report = build_parcel_assurance_report(
        records=[_record(source_key="assessor", parcel_record_id="parcel:assessor")],
        source_contexts=[_context("assessor", "county-assessor-roll")],
        field_roles=[ParcelFieldRole.APN],
        generated_at=OBSERVED_AT,
    )

    payload = report.to_dict()
    assert payload["claims"][0]["source_key"] == "assessor"
    assert payload["claims"][0]["lineage_key"] == "county-assessor-roll"
    assert "confidence_score" not in payload


def test_assurance_does_not_mutate_existing_parcel_record_payload() -> None:
    parcel = ParcelCoreRecord(
        parcel_record_id="parcel:compatibility",
        source_key="assessor",
        source_record_id="row:1",
        apn="123-456-78",
        normalized_apn="12345678",
        county="San Bernardino",
        address="1 Main St",
        normalized_address="1 MAIN ST",
        created_at=OBSERVED_AT,
    )
    original_payload = parcel.to_dict()

    build_parcel_assurance_report(
        records=[parcel],
        source_contexts=[_context("assessor", "county-assessor-roll")],
        field_roles=[ParcelFieldRole.APN],
        generated_at=OBSERVED_AT,
    )

    assert parcel.to_dict() == original_payload
    assert "claims" not in original_payload
    assert "field_assurances" not in original_payload
