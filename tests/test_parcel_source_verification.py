from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from constructionsight.parcel_assurance_models import ParcelEvidenceAuthority
from constructionsight.parcel_row_preview import preview_rows
from constructionsight.parcel_row_preview_models import (
    ParcelRowPreviewInput,
    ParcelRowPreviewStatus,
)
from constructionsight.parcel_schema_models import ParcelFieldRoleMatch
from constructionsight.parcel_schema_preview import preview_schema_for_source_key
from constructionsight.parcel_source_models import (
    ParcelAccessBoundary,
    ParcelConstantFieldValue,
    ParcelCoverageStatus,
    ParcelFieldRole,
    ParcelSourceFormat,
)
from constructionsight.parcel_source_registry import get_parcel_sources
from constructionsight.parcel_source_verification import (
    assurance_contexts_from_verified_profiles,
    build_parcel_county_coverage_report,
    get_parcel_source_evidence,
    get_verified_parcel_source_profiles,
)
from constructionsight.parcel_source_verification_models import (
    ParcelCountyCoverageGapCode,
    ParcelCountyCoverageStatus,
    ParcelSourceEvidence,
    ParcelSourceVerificationProfile,
    ParcelSourceVerificationStatus,
    parcel_source_verification_profile_id,
)


def test_official_county_sources_are_preview_ready_with_exact_schema_mappings() -> None:
    sources = {
        source.source_key: source
        for source in get_parcel_sources()
        if source.provider_kind.value == "county_gis"
    }
    san_bernardino = sources["san-bernardino:county-gis-parcels"]
    riverside = sources["riverside:county-gis-parcels"]

    assert san_bernardino.access_boundary == ParcelAccessBoundary.OPEN_PUBLIC_DATA
    assert san_bernardino.coverage_status == ParcelCoverageStatus.READY_FOR_PREVIEW
    assert san_bernardino.source_format == ParcelSourceFormat.ARCGIS_FEATURE_SERVICE
    assert {mapping.source_field for mapping in san_bernardino.field_mappings} == {
        "Acreage",
        "Jurisdiction",
        "OBJECTID",
        "OwnerName",
        "ParcelNumber",
        "Zoning",
        "geometry",
    }
    assert riverside.access_boundary == ParcelAccessBoundary.OPEN_PUBLIC_DATA
    assert riverside.coverage_status == ParcelCoverageStatus.READY_FOR_PREVIEW
    assert riverside.source_format == ParcelSourceFormat.ARCGIS_MAP_SERVICE
    assert {mapping.source_field for mapping in riverside.field_mappings} == {
        "ACREAGE",
        "APN",
        "OBJECTID",
        "SITUS_CITY",
        "SITUS_STREET",
        "geometry",
    }
    assert ParcelFieldRole.OWNER not in {
        mapping.field_role for mapping in riverside.field_mappings
    }
    for source in (san_bernardino, riverside):
        constants = {
            constant.field_role: constant.value for constant in source.constant_fields
        }
        assert constants == {
            ParcelFieldRole.COUNTY: source.coverage.county,
            ParcelFieldRole.STATE: "CA",
        }


def test_county_constants_satisfy_preview_without_fabricated_schema_columns() -> None:
    san_bernardino = preview_schema_for_source_key(
        "san-bernardino:county-gis-parcels"
    )
    riverside = preview_schema_for_source_key("riverside:county-gis-parcels")

    assert ParcelFieldRole.COUNTY not in san_bernardino.missing_required_roles
    assert ParcelFieldRole.COUNTY not in riverside.missing_required_roles
    assert {constant.field_role for constant in san_bernardino.constant_fields} == {
        ParcelFieldRole.COUNTY,
        ParcelFieldRole.STATE,
    }
    assert {constant.field_role for constant in riverside.constant_fields} == {
        ParcelFieldRole.COUNTY,
        ParcelFieldRole.STATE,
    }


def test_row_preview_uses_verified_county_constant() -> None:
    report = preview_rows(
        ParcelRowPreviewInput(
            source_key="test:county-source",
            source_name="Test county source",
            source_format=ParcelSourceFormat.ARCGIS_FEATURE_SERVICE,
            field_role_matches=[
                ParcelFieldRoleMatch(
                    source_field="APN",
                    field_role=ParcelFieldRole.APN,
                    match_reason="test mapping",
                    confidence_score=100,
                    required_role=True,
                )
            ],
            constant_fields=[
                ParcelConstantFieldValue(
                    field_role=ParcelFieldRole.COUNTY,
                    value="Riverside",
                    required=True,
                    evidence_reference="official county scope",
                )
            ],
            rows=[{"APN": "123-456-789"}],
        )
    )

    assert report.status == ParcelRowPreviewStatus.READY_FOR_PARCEL_RECORD_MODEL
    assert report.rows[0].county == "Riverside"
    assert report.rows[0].normalized_apn == "123456789"


def test_official_evidence_is_digest_bound_and_complete_for_each_source() -> None:
    evidence = get_parcel_source_evidence()

    assert len(evidence) == 8
    assert all(item.evidence_id.startswith("parcel-source-evidence:") for item in evidence)
    assert {item.county for item in evidence} == {"Riverside", "San Bernardino"}
    assert all(item.observed_at.tzinfo is not None for item in evidence)
    payload = evidence[0].to_dict()
    payload["facts"] = [*payload["facts"], "Unbound changed fact."]
    payload["facts"].sort()
    with pytest.raises(ValidationError, match="does not match evidence content"):
        ParcelSourceEvidence.model_validate(payload)


def test_profiles_bind_registry_schema_evidence_and_field_authority() -> None:
    evidence_ids = {item.evidence_id for item in get_parcel_source_evidence()}
    profiles = get_verified_parcel_source_profiles()

    assert len(profiles) == 2
    for profile in profiles:
        assert profile.status == ParcelSourceVerificationStatus.VERIFIED_PREVIEW
        assert profile.public_access_verified is True
        assert profile.schema_verified is True
        assert profile.county_extent_declared is True
        assert profile.countywide_record_coverage_verified is False
        assert profile.bulk_acquisition_verified is False
        assert set(profile.evidence_ids) <= evidence_ids
        assert profile.authoritative_fields == (ParcelFieldRole.APN,)
        assert profile.default_authority == ParcelEvidenceAuthority.OFFICIAL

    riverside = next(profile for profile in profiles if profile.county == "Riverside")
    assert ParcelFieldRole.OWNER not in riverside.available_fields
    assert "PRIMARY_OWNER" not in riverside.schema_fields


def test_profile_rejects_mapping_absent_from_schema_snapshot() -> None:
    profile = get_verified_parcel_source_profiles()[0]
    payload = profile.to_dict()
    payload["field_mappings"][0]["source_field"] = "NOT_IN_SCHEMA"
    identity_payload = {
        key: value for key, value in payload.items() if key != "profile_id"
    }
    payload["profile_id"] = parcel_source_verification_profile_id(identity_payload)

    with pytest.raises(ValidationError, match="must exist in the schema snapshot"):
        ParcelSourceVerificationProfile.model_validate(payload)


def test_profile_rejects_import_ready_without_bulk_and_countywide_proof() -> None:
    profile = get_verified_parcel_source_profiles()[0]
    payload = profile.to_dict()
    payload["coverage_status"] = "ready_for_import"
    identity_payload = {
        key: value for key, value in payload.items() if key != "profile_id"
    }
    payload["profile_id"] = parcel_source_verification_profile_id(identity_payload)

    with pytest.raises(ValidationError, match="import-ready coverage requires"):
        ParcelSourceVerificationProfile.model_validate(payload)


def test_profiles_convert_to_assurance_contexts_without_global_authority() -> None:
    contexts = assurance_contexts_from_verified_profiles()

    assert len(contexts) == 2
    assert all(
        context.default_authority == ParcelEvidenceAuthority.OFFICIAL
        for context in contexts
    )
    assert all(context.authoritative_fields == [ParcelFieldRole.APN] for context in contexts)
    assert all(context.limitations for context in contexts)


def test_county_coverage_report_exposes_every_unresolved_readiness_dimension() -> None:
    report = build_parcel_county_coverage_report(
        generated_at=datetime(2026, 7, 14, 12, 0, tzinfo=UTC)
    )

    assert report.status == ParcelCountyCoverageStatus.INCOMPLETE
    assert report.counties == ("Riverside", "San Bernardino")
    assert len(report.profile_ids) == 2
    by_county = {
        county: {gap.code for gap in report.gaps if gap.county == county}
        for county in report.counties
    }
    expected_codes = {
        ParcelCountyCoverageGapCode.MISSING_REQUIRED_FIELD,
        ParcelCountyCoverageGapCode.MISSING_AUTHORITATIVE_FIELD,
        ParcelCountyCoverageGapCode.COUNTYWIDE_RECORD_COVERAGE_UNVERIFIED,
        ParcelCountyCoverageGapCode.BULK_ACQUISITION_UNVERIFIED,
        ParcelCountyCoverageGapCode.INSUFFICIENT_INDEPENDENT_LINEAGES,
    }
    assert by_county == {
        "Riverside": expected_codes,
        "San Bernardino": expected_codes,
    }
    missing_by_county = {
        gap.county: set(gap.field_roles)
        for gap in report.gaps
        if gap.code == ParcelCountyCoverageGapCode.MISSING_REQUIRED_FIELD
    }
    assert missing_by_county["San Bernardino"] == {
        ParcelFieldRole.ADDRESS,
        ParcelFieldRole.LAND_USE,
    }
    assert missing_by_county["Riverside"] == {
        ParcelFieldRole.JURISDICTION,
        ParcelFieldRole.LAND_USE,
        ParcelFieldRole.OWNER,
        ParcelFieldRole.ZONING,
    }


def test_coverage_report_id_excludes_only_generation_time() -> None:
    first = build_parcel_county_coverage_report(
        generated_at=datetime(2026, 7, 14, 12, 0, tzinfo=UTC)
    )
    replay = build_parcel_county_coverage_report(
        generated_at=datetime(2026, 7, 14, 13, 0, tzinfo=UTC)
    )

    assert first.report_id == replay.report_id
    assert first.generated_at != replay.generated_at
    assert first.to_dict() | {"generated_at": None} == replay.to_dict() | {
        "generated_at": None
    }
