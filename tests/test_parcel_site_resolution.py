from constructionsight.parcel_core_models import (
    ParcelCoreRecord,
    ParcelGeometry,
    ParcelGeometryKind,
)
from constructionsight.parcel_site_resolution import resolve_site_with_parcels
from constructionsight.site_resolution_models import (
    GeometryHint,
    GeometryHintKind,
    SiteIdentifier,
    SiteIdentifierKind,
    SiteResolutionInput,
    SiteResolutionStatus,
)

_APPROXIMATE_CENTROID_LIMITATION = (
    "polygon centroid is a coordinate-average approximation, not an area-weighted centroid"
)
_ENVELOPE_CONTAINMENT_LIMITATION = (
    "coordinate containment uses parcel envelope only, not polygon topology"
)


def _identifier(kind: SiteIdentifierKind, value: str) -> SiteIdentifier:
    return SiteIdentifier(
        identifier_kind=kind,
        value=value,
        normalized_value=value,
    )


def _parcel(
    parcel_record_id: str,
    apn: str,
    address: str | None = None,
    *,
    geometry_kind: ParcelGeometryKind = ParcelGeometryKind.POINT,
    geometry_limitations: list[str] | None = None,
) -> ParcelCoreRecord:
    return ParcelCoreRecord(
        parcel_record_id=parcel_record_id,
        source_key="test:source",
        source_record_id=parcel_record_id.removeprefix("parcel:"),
        apn=apn,
        normalized_apn=apn,
        county="Riverside",
        address=address,
        normalized_address=address,
        geometry=ParcelGeometry(
            geometry_kind=geometry_kind,
            centroid_latitude=34.1,
            centroid_longitude=-117.2,
            envelope_min_latitude=34.0,
            envelope_min_longitude=-117.3,
            envelope_max_latitude=34.2,
            envelope_max_longitude=-117.1,
            spatial_reference="EPSG:4326",
            limitations=geometry_limitations or [],
        ),
    )


def _point_hint() -> GeometryHint:
    return GeometryHint(
        geometry_kind=GeometryHintKind.POINT,
        latitude=34.1,
        longitude=-117.2,
        source_name="test source",
    )


def test_resolve_site_with_parcels_prefers_exact_apn_match() -> None:
    site_input = SiteResolutionInput(
        source_name="test source",
        identifiers=[_identifier(SiteIdentifierKind.APN, "12345678")],
    )

    result = resolve_site_with_parcels(
        site_input,
        [_parcel("parcel:one", "12345678"), _parcel("parcel:two", "99988877")],
    )
    candidate = result.candidates[0]

    assert result.status == SiteResolutionStatus.RESOLVED
    assert candidate.apn == "12345678"
    assert candidate.match_strength == "strong"
    assert "APN matched parcel core record" in candidate.reasons


def test_resolve_site_with_parcels_combines_apn_address_and_point() -> None:
    site_input = SiteResolutionInput(
        source_name="test source",
        identifiers=[
            _identifier(SiteIdentifierKind.APN, "12345678"),
            _identifier(SiteIdentifierKind.ADDRESS, "123 MAIN ST"),
        ],
        geometry_hints=[_point_hint()],
    )

    result = resolve_site_with_parcels(
        site_input,
        [_parcel("parcel:one", "12345678", "123 MAIN ST")],
    )
    candidate = result.candidates[0]

    assert result.status == SiteResolutionStatus.RESOLVED
    assert candidate.confidence_score == 100
    assert candidate.match_strength == "exact"
    assert "coordinate hint falls within parcel envelope" in candidate.reasons


def test_resolve_site_with_parcels_preserves_geometry_limitations() -> None:
    site_input = SiteResolutionInput(
        source_name="test source",
        identifiers=[_identifier(SiteIdentifierKind.APN, "12345678")],
        geometry_hints=[_point_hint()],
    )

    result = resolve_site_with_parcels(
        site_input,
        [
            _parcel(
                "parcel:one",
                "12345678",
                geometry_kind=ParcelGeometryKind.POLYGON,
                geometry_limitations=[_APPROXIMATE_CENTROID_LIMITATION],
            )
        ],
    )
    candidate = result.candidates[0]

    assert _APPROXIMATE_CENTROID_LIMITATION in candidate.limitations
    assert _ENVELOPE_CONTAINMENT_LIMITATION in candidate.limitations


def test_resolve_site_with_parcels_preserves_ambiguity() -> None:
    site_input = SiteResolutionInput(
        source_name="test source",
        identifiers=[_identifier(SiteIdentifierKind.APN, "12345678")],
    )

    result = resolve_site_with_parcels(
        site_input,
        [_parcel("parcel:one", "12345678"), _parcel("parcel:two", "12345678")],
    )

    assert result.status == SiteResolutionStatus.AMBIGUOUS
    assert result.primary_site_key is None
    assert len(result.candidates) == 2
    assert result.limitations == ["multiple parcel records matched equally"]


def test_resolve_site_with_parcels_falls_back_when_no_parcel_matches() -> None:
    site_input = SiteResolutionInput(
        source_name="test source",
        identifiers=[_identifier(SiteIdentifierKind.APN, "12345678")],
    )

    result = resolve_site_with_parcels(site_input, [_parcel("parcel:one", "99988877")])

    assert result.status == SiteResolutionStatus.PARTIAL
    assert "no parcel core record matched site signals" in result.limitations
