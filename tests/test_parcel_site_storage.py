import json
from datetime import timedelta

from sqlalchemy import inspect, select

from constructionsight.domain_types import confidence_band
from constructionsight.parcel_assurance import build_parcel_assurance_report
from constructionsight.parcel_assurance_models import (
    ParcelAssuranceSourceContext,
    ParcelEvidenceAuthority,
)
from constructionsight.parcel_core_models import (
    ParcelCoreRecord,
    ParcelGeometry,
    ParcelGeometryKind,
)
from constructionsight.parcel_source_models import ParcelFieldRole
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
    ParcelAssuranceReportRow,
    ParcelCoreRecordRow,
    SiteResolutionResultRow,
)
from constructionsight.storage.parcel_site_store import (
    store_parcel_assurance_report,
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
        source_name="parcel test",
        evidence_id="evidence:test",
        status=SiteResolutionStatus.RESOLVED,
        primary_site_key="site:test",
        candidates=[candidate],
        limitations=["parcel geometry is not survey-grade"],
    )


def _assurance_report():
    parcel = _parcel()
    context = ParcelAssuranceSourceContext(
        source_key=parcel.source_key,
        lineage_key="county-assessor-roll",
        default_authority=ParcelEvidenceAuthority.OFFICIAL,
        authoritative_fields=[ParcelFieldRole.APN],
        limitations=["currency must be checked"],
    )
    return build_parcel_assurance_report(
        records=[parcel],
        source_contexts=[context],
        field_roles=[ParcelFieldRole.APN, ParcelFieldRole.OWNER],
        generated_at=parcel.created_at,
    )


def test_parcel_site_tables_are_created() -> None:
    engine, _factory = _session_factory()

    table_names = set(inspect(engine).get_table_names())

    assert "parcel_core_records" in table_names
    assert "parcel_assurance_reports" in table_names
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


def test_store_parcel_assurance_report_roundtrip_and_exact_replay() -> None:
    _engine, factory = _session_factory()
    report = _assurance_report()
    regenerated = report.model_copy(
        update={"generated_at": report.generated_at + timedelta(minutes=5)}
    )

    with managed_session(factory) as session:
        store_parcel_assurance_report(session, report)
        store_parcel_assurance_report(session, regenerated)
        session.flush()
        row = session.execute(select(ParcelAssuranceReportRow)).scalar_one()

        assert row.report_id == report.report_id
        assert row.normalized_apn == "12345678"
        assert row.review_status == "incomplete"
        assert row.requires_human_review is False
        assert row.source_count == 1
        assert row.independent_lineage_count == 1
        assert row.claim_count == 1
        assert row.conflict_count == 0
        assert row.missing_count == 1
        assert row.observed_created_at == report.generated_at.isoformat()
        payload = json.loads(row.payload_json)
        assert payload["claims"][0]["lineage_key"] == "county-assessor-roll"
        assert payload["field_assurances"][1]["status"] == "missing"


def test_store_site_resolution_result_roundtrip() -> None:
    _engine, factory = _session_factory()

    with managed_session(factory) as session:
        store_site_resolution_result(session, _site_resolution())
        session.flush()
        row = session.execute(select(SiteResolutionResultRow)).scalar_one()

        assert row.resolution_id == _site_resolution().resolution_id
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


def test_derived_result_stores_reject_forged_identity_reuse() -> None:
    _engine, factory = _session_factory()
    site = _site_resolution()
    assurance = _assurance_report()

    with managed_session(factory) as session:
        store_site_resolution_result(session, site)
        forged_site = site.model_copy(update={"status": SiteResolutionStatus.PARTIAL})
        with pytest.raises(ValueError, match="identity"):
            store_site_resolution_result(session, forged_site)

        store_parcel_assurance_report(session, assurance)
        forged_assurance = assurance.model_copy(update={"county": "Riverside"})
        with pytest.raises(ValueError, match="identity"):
            store_parcel_assurance_report(session, forged_assurance)
