from constructionsight.parcel_source_models import (
    ParcelCoverageStatus,
    ParcelGeometrySupport,
    ParcelProviderKind,
)
from constructionsight.parcel_source_registry import (
    build_parcel_source_report,
    get_parcel_sources,
    parcel_source_matrix_rows,
)


def test_default_registry_includes_phase_one_counties() -> None:
    sources = get_parcel_sources()
    counties = {source.coverage.county for source in sources}

    assert "San Bernardino" in counties
    assert "Riverside" in counties


def test_county_filter_matches_county_with_or_without_suffix() -> None:
    sources = get_parcel_sources(county="San Bernardino County")

    assert sources
    assert {source.coverage.county for source in sources} == {"San Bernardino"}


def test_provider_filter_returns_county_gis_targets() -> None:
    sources = get_parcel_sources(provider_kind=ParcelProviderKind.COUNTY_GIS)

    assert sources
    assert all(source.provider_kind == ParcelProviderKind.COUNTY_GIS for source in sources)
    assert all(
        source.coverage.geometry_support == ParcelGeometrySupport.POLYGON
        for source in sources
    )


def test_parcel_source_report_separates_targets_and_license_blockers() -> None:
    report = build_parcel_source_report()

    assert report.sources_reviewed >= 4
    assert "San Bernardino" in report.counties
    assert "Riverside" in report.counties
    assert report.target_sources
    assert {
        gap.source_key for gap in report.ready_sources
    } >= {
        "san-bernardino:county-gis-parcels",
        "riverside:county-gis-parcels",
    }
    assert report.blocked_sources
    assert all(
        gap.coverage_status in {ParcelCoverageStatus.TARGET, ParcelCoverageStatus.DESIGNED}
        for gap in report.target_sources
    )
    assert all(
        gap.coverage_status == ParcelCoverageStatus.BLOCKED_BY_LICENSE
        for gap in report.blocked_sources
    )


def test_parcel_source_matrix_rows_are_machine_readable() -> None:
    rows = parcel_source_matrix_rows(get_parcel_sources(county="Riverside"))

    assert rows
    assert rows[0]["county"] == "Riverside"
    assert rows[0]["source_key"]
    assert rows[0]["next_action"]
