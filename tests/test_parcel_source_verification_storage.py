from datetime import UTC, datetime

import pytest
from sqlalchemy import func, inspect, select

from constructionsight.parcel_source_verification import (
    build_parcel_county_coverage_report,
    get_parcel_source_evidence,
    get_verified_parcel_source_profiles,
)
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.parcel_site_orm import (
    ParcelCountyCoverageReportRow,
    ParcelSourceEvidenceRow,
    ParcelSourceVerificationProfileRow,
)
from constructionsight.storage.parcel_source_verification_store import (
    load_parcel_county_coverage_report,
    load_parcel_source_evidence,
    load_parcel_source_verification_profiles,
    store_parcel_county_coverage_report,
    store_parcel_source_evidence,
    store_parcel_source_verification_profile,
)
from constructionsight.upstream_operator_models import UpstreamOperatorRecordKind
from constructionsight.upstream_operator_service import (
    get_upstream_operator_record,
    list_upstream_operator_records,
)


def _factory():
    engine = create_database_engine("sqlite:///:memory:")
    initialize_database(engine)
    return engine, session_factory(engine)


def test_database_initializes_verification_evidence_and_coverage_tables() -> None:
    engine, _ = _factory()

    assert {
        "parcel_source_evidence",
        "parcel_source_verification_profiles",
        "parcel_county_coverage_reports",
    } <= set(inspect(engine).get_table_names())


def test_storage_replays_exact_evidence_and_profiles_idempotently() -> None:
    _, factory = _factory()
    evidence = get_parcel_source_evidence()
    profiles = get_verified_parcel_source_profiles()

    with managed_session(factory) as session:
        for item in evidence:
            assert store_parcel_source_evidence(session, item) is store_parcel_source_evidence(
                session, item
            )
        for profile in profiles:
            assert store_parcel_source_verification_profile(
                session, profile
            ) is store_parcel_source_verification_profile(session, profile)
        assert session.scalar(select(func.count()).select_from(ParcelSourceEvidenceRow)) == 8
        assert (
            session.scalar(
                select(func.count()).select_from(ParcelSourceVerificationProfileRow)
            )
            == 2
        )

    with managed_session(factory) as session:
        loaded_evidence = load_parcel_source_evidence(session, evidence[0].evidence_id)
        loaded_profiles = load_parcel_source_verification_profiles(
            session,
            county="Riverside",
        )

    assert loaded_evidence == evidence[0]
    assert len(loaded_profiles) == 1
    assert loaded_profiles[0].county == "Riverside"


def test_profile_storage_requires_persisted_evidence() -> None:
    _, factory = _factory()
    profile = get_verified_parcel_source_profiles()[0]

    with (
        managed_session(factory) as session,
        pytest.raises(ValueError, match="requires persisted evidence"),
    ):
        store_parcel_source_verification_profile(session, profile)


def test_coverage_storage_requires_persisted_profiles() -> None:
    _, factory = _factory()
    report = build_parcel_county_coverage_report()

    with (
        managed_session(factory) as session,
        pytest.raises(ValueError, match="requires persisted profiles"),
    ):
        store_parcel_county_coverage_report(session, report)


def test_coverage_report_storage_is_semantically_idempotent() -> None:
    _, factory = _factory()
    evidence = get_parcel_source_evidence()
    profiles = get_verified_parcel_source_profiles()
    first = build_parcel_county_coverage_report(
        generated_at=datetime(2026, 7, 14, 12, 0, tzinfo=UTC)
    )
    replay = build_parcel_county_coverage_report(
        generated_at=datetime(2026, 7, 14, 13, 0, tzinfo=UTC)
    )

    with managed_session(factory) as session:
        for item in evidence:
            store_parcel_source_evidence(session, item)
        for profile in profiles:
            store_parcel_source_verification_profile(session, profile)
        first_row = store_parcel_county_coverage_report(session, first)
        replay_row = store_parcel_county_coverage_report(session, replay)
        count = session.scalar(
            select(func.count()).select_from(ParcelCountyCoverageReportRow)
        )

    assert first_row is replay_row
    assert count == 1
    with managed_session(factory) as session:
        loaded = load_parcel_county_coverage_report(session, first.report_id)
    assert loaded == first


def test_profile_loader_rejects_indexed_payload_drift() -> None:
    _, factory = _factory()
    profile = get_verified_parcel_source_profiles()[0]
    evidence_by_id = {
        item.evidence_id: item for item in get_parcel_source_evidence()
    }

    with managed_session(factory) as session:
        for evidence_id in profile.evidence_ids:
            store_parcel_source_evidence(session, evidence_by_id[evidence_id])
        row = store_parcel_source_verification_profile(session, profile)
        row.county = "Wrong County"

    with (
        managed_session(factory) as session,
        pytest.raises(ValueError, match="indexed fields disagree"),
    ):
        load_parcel_source_verification_profiles(session)


def test_operator_exposes_evidence_profiles_and_coverage_without_mutation() -> None:
    _, factory = _factory()
    evidence = get_parcel_source_evidence()
    profiles = get_verified_parcel_source_profiles()
    report = build_parcel_county_coverage_report(
        generated_at=datetime(2026, 7, 14, 12, 0, tzinfo=UTC)
    )

    with managed_session(factory) as session:
        for item in evidence:
            store_parcel_source_evidence(session, item)
        for profile in profiles:
            store_parcel_source_verification_profile(session, profile)
        store_parcel_county_coverage_report(session, report)

    with managed_session(factory) as session:
        evidence_records = list_upstream_operator_records(
            session,
            UpstreamOperatorRecordKind.PARCEL_SOURCE_EVIDENCE,
            county="Riverside",
        )
        profile_records = list_upstream_operator_records(
            session,
            UpstreamOperatorRecordKind.PARCEL_SOURCE_VERIFICATION,
            status="verified_preview",
            source_key="san-bernardino:county-gis-parcels",
        )
        coverage_record = get_upstream_operator_record(
            session,
            UpstreamOperatorRecordKind.PARCEL_COUNTY_COVERAGE,
            report.report_id,
        )

    assert len(evidence_records) == 4
    assert all(record.county == "Riverside" for record in evidence_records)
    assert len(profile_records) == 1
    assert profile_records[0].payload["authoritative_fields"] == ["apn"]
    assert coverage_record is not None
    assert coverage_record.status == "incomplete"
    assert len(coverage_record.payload["gaps"]) == 10
