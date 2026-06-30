import json

from sqlalchemy import inspect, select

from constructionsight.domain_types import confidence_band
from constructionsight.parcel_core_models import (
    ParcelCoreRecord,
    ParcelGeometry,
    ParcelGeometryKind,
)
from constructionsight.site_resolution_models import (
    SiteIdentifier,
    SiteIdentifierKind,
    SiteMatchStrength,
    SiteResolutionCandidate,
    SiteResolutionResult,
    SiteResolutionStatus,
)
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.parcel_site_orm import (
    ParcelCoreRecordRow,
    SiteResolutionResultRow,
)
from constructionsight.storage.parcel_site_store import (
    store_parcel_core_record,
    store_site_resolution_result,
)


def _session_factory():
    engine = create_database_engine("sqlite:///:memory:")
    initialize_database(engine)
    return engine, session_factory(engine)


def _parcel(*, zoning: str | None = "industrial") -> ParcelCoreRecord:
    geometry = ParcelGeometry(
        geometry_kind=ParcelGeometryKind.POINT,
        raw_geometry="POINT(-117.0001 34.0001)",
        geometry_hash="geometry:test",
        centroid_latitude=34.0001,
        centroid_longitude=-117.0001,
        envelope_min_latitude=34.0001,
        envelope_min_longitude=-117.0001,
        envelope_max_latitude=34.0001,
        envelope_max_longitude=-117.0001,
        spatial_reference="EPSG:4326",
        limitations=["point geometry only"],
    )
    return ParcelCoreRecord(
        parcel_record_id="parcel:test",
        source_key="parcel-source:test",
        source_record_id="row:1",
        apn="123-456-78",
        normalized_apn="12345678",
        county="San Bernardino",
        address="1 Main St",
        normalized_address="1 MAIN ST",
        jurisdiction="Redlands",
        zoning=zoning,
        land_use="warehouse",
        acreage=2.5,
        geometry=geometry,
        limitations=["owner not enriched"],
    )


def _site_resolution() -> SiteResolutionResult:
    identifier = SiteIdentifier(
        identifier_kind=SiteIdentifierKind.APN,
        value="123-456-78",
        normalized_value="12345678",
        evidence_id="evidence:test",
        confidence_score=90,
    )
    candidate = SiteResolutionCandidate(
        site_key="site:test",
        match_strength=SiteMatchStrength.EXACT,
        confidence_score=90,
        confidence_band=confidence_band(90),
        county="San Bernardino",
        apn="12345678",
        address="1 MAIN ST",
        latitude=34.0001,
        longitude=-117.0001,
        supporting_identifiers=[identifier],
        reasons=["APN matched parcel core record"],
        limitations=["point geometry only"],
    )
    return SiteResolutionResult(
        resolution_id="site-resolution:test",
        source_name="parcel test",
        evidence_id="evidence:test",
        status=SiteResolutionStatus.RESOLVED,
        primary_site_key="site:test",
        candidates=[candidate],
        limitations=["parcel geometry is not survey-grade"],
    )


def test_parcel_site_tables_are_created() -> None:
    engine, _factory = _session_factory()

    table_names = set(inspect(engine).get_table_names())

    assert "parcel_core_records" in table_names
    assert "site_resolution_results" in table_names


def test_store_parcel_core_record_roundtrip() -> None:
    _engine, factory = _session_factory()

    with managed_session(factory) as session:
        store_parcel_core_record(session, _parcel())
        session.flush()
        row = session.execute(select(ParcelCoreRecordRow)).scalar_one()

        assert row.parcel_record_id == "parcel:test"
        assert row.normalized_apn == "12345678"
        assert row.geometry_kind == "point"
        assert row.centroid_latitude == 34.0001
        payload = json.loads(row.payload_json)
        assert payload["geometry"]["limitations"] == ["point geometry only"]
        assert payload["limitations"] == ["owner not enriched"]


def test_store_site_resolution_result_roundtrip() -> None:
    _engine, factory = _session_factory()

    with managed_session(factory) as session:
        store_site_resolution_result(session, _site_resolution())
        session.flush()
        row = session.execute(select(SiteResolutionResultRow)).scalar_one()

        assert row.resolution_id == "site-resolution:test"
        assert row.status == "resolved"
        assert row.primary_site_key == "site:test"
        assert row.candidate_count == 1
        payload = json.loads(row.payload_json)
        assert payload["candidates"][0]["reasons"] == ["APN matched parcel core record"]
        assert payload["limitations"] == ["parcel geometry is not survey-grade"]


def test_store_parcel_core_record_updates_existing_row() -> None:
    _engine, factory = _session_factory()

    with managed_session(factory) as session:
        store_parcel_core_record(session, _parcel(zoning="industrial"))
        store_parcel_core_record(session, _parcel(zoning="commercial"))
        session.flush()
        rows = session.execute(select(ParcelCoreRecordRow)).scalars().all()

        assert len(rows) == 1
        assert rows[0].zoning == "commercial"
