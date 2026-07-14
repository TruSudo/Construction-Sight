import pytest
from pydantic import ValidationError

from constructionsight.parcel_source_models import (
    ParcelAccessBoundary,
    ParcelConstantFieldValue,
    ParcelCoverageStatus,
    ParcelFieldMapping,
    ParcelFieldRole,
    ParcelGeometrySupport,
    ParcelProviderKind,
    ParcelSource,
    ParcelSourceCoverage,
    ParcelSourceFormat,
)


def test_parcel_source_rejects_open_public_data_without_source_url() -> None:
    with pytest.raises(ValidationError):
        ParcelSource(
            source_key="test:open-source",
            source_name="Test open source",
            provider_kind=ParcelProviderKind.COUNTY_GIS,
            access_boundary=ParcelAccessBoundary.OPEN_PUBLIC_DATA,
            coverage_status=ParcelCoverageStatus.TARGET,
            source_format=ParcelSourceFormat.ARCGIS_FEATURE_SERVICE,
            coverage=ParcelSourceCoverage(
                county="San Bernardino",
                geometry_support=ParcelGeometrySupport.POLYGON,
            ),
            next_action="verify source",
        )


def test_parcel_source_rejects_duplicate_field_roles() -> None:
    with pytest.raises(ValidationError):
        ParcelSource(
            source_key="test:duplicate-fields",
            source_name="Test duplicate fields",
            provider_kind=ParcelProviderKind.USER_PROVIDED_FILE,
            access_boundary=ParcelAccessBoundary.USER_PROVIDED_FILE,
            coverage_status=ParcelCoverageStatus.DESIGNED,
            source_format=ParcelSourceFormat.CSV,
            coverage=ParcelSourceCoverage(county="User supplied"),
            field_mappings=[
                ParcelFieldMapping(source_field="apn", field_role=ParcelFieldRole.APN),
                ParcelFieldMapping(source_field="parcel", field_role=ParcelFieldRole.APN),
            ],
            next_action="map schema",
        )


def test_license_blocked_source_requires_license_boundary() -> None:
    with pytest.raises(ValidationError):
        ParcelSource(
            source_key="test:bad-license-block",
            source_name="Bad license blocked source",
            provider_kind=ParcelProviderKind.LICENSED_PROVIDER,
            access_boundary=ParcelAccessBoundary.PUBLIC_METADATA_ONLY,
            coverage_status=ParcelCoverageStatus.BLOCKED_BY_LICENSE,
            source_format=ParcelSourceFormat.API_JSON,
            coverage=ParcelSourceCoverage(county="Multi-county"),
            next_action="wait for license",
        )


def test_parcel_source_rejects_non_geographic_constant_roles() -> None:
    with pytest.raises(ValidationError, match="limited to county and state"):
        ParcelConstantFieldValue(
            field_role=ParcelFieldRole.APN,
            value="123456789",
            required=True,
            evidence_reference="test evidence",
        )


def test_parcel_source_rejects_role_as_both_mapping_and_constant() -> None:
    with pytest.raises(ValidationError, match="both source-mapped and constant"):
        ParcelSource(
            source_key="test:duplicate-role-kind",
            source_name="Test duplicate role kind",
            provider_kind=ParcelProviderKind.USER_PROVIDED_FILE,
            access_boundary=ParcelAccessBoundary.USER_PROVIDED_FILE,
            coverage_status=ParcelCoverageStatus.DESIGNED,
            source_format=ParcelSourceFormat.CSV,
            coverage=ParcelSourceCoverage(county="Riverside"),
            field_mappings=[
                ParcelFieldMapping(
                    source_field="county",
                    field_role=ParcelFieldRole.COUNTY,
                )
            ],
            constant_fields=[
                ParcelConstantFieldValue(
                    field_role=ParcelFieldRole.COUNTY,
                    value="Riverside",
                    evidence_reference="test evidence",
                )
            ],
            next_action="fix mapping",
        )
