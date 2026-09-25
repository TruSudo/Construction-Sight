"""Read-only operator projection of persisted public-source configuration."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from constructionsight.ceqa_models import CeqaRecord
from constructionsight.models import PlatformFamily, PublicSource, SourceVerificationResult
from constructionsight.operator_source_registry import (
    SOURCE_REGISTRY_RESULT_LIMIT,
    build_operator_source_registry,
)
from constructionsight.permit_models import PermitRecord
from constructionsight.provenance import Provenance
from constructionsight.storage.database import create_database_engine, initialize_database
from constructionsight.storage.domain_store import CeqaStore, PermitStore
from constructionsight.storage.source_registry import SourceRegistryStore
from constructionsight.storage.verification_store import VerificationStore


def _source(
    name: str = "Synthetic San Bernardino portal",
    *,
    county: str = "San Bernardino",
    platform: str = "accela_aca",
    verification_status: str = "partial",
    public_url: str = "https://example.invalid/public/",
) -> PublicSource:
    return PublicSource.model_validate(
        {
            "jurisdiction": {
                "name": county + " County",
                "county": county,
                "state": "CA",
                "jurisdiction_type": "county",
            },
            "source_name": name,
            "source_type": "county_portal",
            "platform_family": platform,
            "public_url": public_url,
            "record_categories": ["permit", "inspection"],
            "search_method": "Synthetic public search fixture.",
            "extraction_difficulty": "high",
            "update_frequency": "daily",
            "confidence_score": 72,
            "verification_status": verification_status,
            "provenance_notes": "Synthetic fixture only.",
            "last_checked_date": "2026-09-20",
        }
    )


def test_source_registry_projection_preserves_stored_scope_and_adapter_maturity(tmp_path):
    path = tmp_path / "registry.sqlite3"
    engine = create_database_engine(f"sqlite:///{path}")
    initialize_database(engine)
    with Session(engine) as session, session.begin():
        SourceRegistryStore(session).upsert_source(_source())

    with Session(engine) as session:
        result = build_operator_source_registry(session)

    assert result.read_only is True
    assert result.network_collection_enabled is False
    assert result.verification_metadata_is_authority is False
    assert result.total == result.returned == 1
    assert result.result_limit == SOURCE_REGISTRY_RESULT_LIMIT
    assert result.truncated is False
    entry = result.entries[0]
    assert entry.source_name == "Synthetic San Bernardino portal"
    assert entry.county == "San Bernardino"
    assert entry.platform_family == "accela_aca"
    assert entry.verification_status == "partial"
    assert entry.last_checked_date == date(2026, 9, 20)
    assert entry.adapter_status == "placeholder"
    assert entry.adapter_live is False
    assert entry.adapter_requires_javascript is True
    assert entry.record_categories == ["permit", "inspection"]
    assert entry.latest_verification_present is False
    assert entry.verification_metadata_consistent is None
    engine.dispose()


def test_source_registry_projection_fails_closed_on_corrupted_categories(tmp_path):
    path = tmp_path / "registry-corrupt.sqlite3"
    engine = create_database_engine(f"sqlite:///{path}")
    initialize_database(engine)
    with Session(engine) as session, session.begin():
        SourceRegistryStore(session).upsert_source(_source())
        session.execute(text("UPDATE sources SET record_categories_json = '{not-json}'"))

    with Session(engine) as session, pytest.raises(
        ValueError, match="categories are not valid JSON"
    ):
        build_operator_source_registry(session)

    engine.dispose()


def test_source_registry_projection_reports_bounded_truncation(tmp_path, monkeypatch):
    path = tmp_path / "registry-bounded.sqlite3"
    engine = create_database_engine(f"sqlite:///{path}")
    initialize_database(engine)
    with Session(engine) as session, session.begin():
        store = SourceRegistryStore(session)
        store.upsert_source(_source("First portal"))
        store.upsert_source(
            _source(
                "Second portal",
                platform="tyler_energov",
                verification_status="unverified",
            )
        )

    monkeypatch.setattr(
        "constructionsight.operator_source_registry.SOURCE_REGISTRY_RESULT_LIMIT", 1
    )
    with Session(engine) as session:
        result = build_operator_source_registry(session)

    assert result.total == 2
    assert result.returned == result.result_limit == 1
    assert result.truncated is True
    assert result.entries[0].source_name == "First portal"
    engine.dispose()



def _verification(
    *, checked_at: datetime, reachable: bool, confidence: int
) -> SourceVerificationResult:
    return SourceVerificationResult(
        source_name="Synthetic San Bernardino portal",
        public_url="https://example.invalid/public/",
        checked_at=checked_at,
        url_reachable=reachable,
        portal_type_detected=PlatformFamily.ACCELA_ACA,
        public_search_available=True,
        login_required=False,
        permit_details_visible=True,
        confidence_score=confidence,
        notes="Synthetic retained verification observation.",
        raw_observations={"fixture": True},
    )


def test_source_registry_projection_uses_latest_retained_verification(tmp_path):
    path = tmp_path / "registry-verification.sqlite3"
    engine = create_database_engine(f"sqlite:///{path}")
    initialize_database(engine)
    older = datetime(2026, 9, 19, 10, 0, tzinfo=UTC)
    newer = datetime(2026, 9, 21, 11, 30, tzinfo=UTC)
    with Session(engine) as session, session.begin():
        SourceRegistryStore(session).upsert_source(_source())
        store = VerificationStore(session)
        store.add_result(_verification(checked_at=older, reachable=True, confidence=55))
        store.add_result(_verification(checked_at=newer, reachable=True, confidence=88))

    with Session(engine) as session:
        entry = build_operator_source_registry(session).entries[0]

    assert entry.latest_verification_present is True
    assert entry.latest_verification_checked_at is not None
    assert entry.latest_verification_checked_at.date() == newer.date()
    assert entry.latest_verification_url_reachable is True
    assert entry.latest_detected_platform_family == "accela_aca"
    assert entry.latest_public_search_available is True
    assert entry.latest_login_required is False
    assert entry.latest_verification_confidence_score == 88
    assert entry.verification_status == "verified"
    assert entry.confidence_score == 88
    assert entry.last_checked_date == newer.date()
    assert entry.verification_metadata_consistent is True
    engine.dispose()


def test_source_registry_projection_discloses_stale_registry_metadata(tmp_path):
    path = tmp_path / "registry-verification-mismatch.sqlite3"
    engine = create_database_engine(f"sqlite:///{path}")
    initialize_database(engine)
    checked_at = datetime(2026, 9, 21, 11, 30, tzinfo=UTC)
    with Session(engine) as session, session.begin():
        SourceRegistryStore(session).upsert_source(_source())
        VerificationStore(session).add_result(
            _verification(checked_at=checked_at, reachable=True, confidence=88)
        )
        session.execute(
            text(
                "UPDATE sources SET confidence_score = 7, "
                "verification_status = 'unverified', last_checked_date = '2026-09-01'"
            )
        )

    with Session(engine) as session:
        entry = build_operator_source_registry(session).entries[0]

    assert entry.latest_verification_present is True
    assert entry.latest_verification_confidence_score == 88
    assert entry.confidence_score == 7
    assert entry.verification_status == "unverified"
    assert entry.verification_metadata_consistent is False
    engine.dispose()


def test_source_registry_projection_rejects_corrupted_latest_verification(tmp_path):
    path = tmp_path / "registry-verification-corrupt.sqlite3"
    engine = create_database_engine(f"sqlite:///{path}")
    initialize_database(engine)
    checked_at = datetime(2026, 9, 21, 11, 30, tzinfo=UTC)
    with Session(engine) as session, session.begin():
        SourceRegistryStore(session).upsert_source(_source())
        VerificationStore(session).add_result(
            _verification(checked_at=checked_at, reachable=True, confidence=88)
        )
        session.execute(
            text("UPDATE source_verifications SET raw_observations_json = '[]'")
        )

    with Session(engine) as session, pytest.raises(
        ValueError, match="observations are not an object"
    ):
        build_operator_source_registry(session)

    engine.dispose()



def test_source_registry_projection_attributes_exact_record_provenance(tmp_path):
    path = tmp_path / "registry-attribution.sqlite3"
    engine = create_database_engine(f"sqlite:///{path}")
    initialize_database(engine)
    registered = "Synthetic San Bernardino portal"
    unregistered = "Unregistered retained fixture source"
    with Session(engine) as session, session.begin():
        store = SourceRegistryStore(session)
        store.upsert_source(_source())
        store.upsert_source(
            _source(
                "Second configured portal",
                public_url="https://second.example.invalid/public/",
            )
        )
        CeqaStore(session).upsert(
            CeqaRecord(
                ceqa_key="fixture:ceqa:attributed",
                title="Attributed CEQA fixture",
                county="San Bernardino",
                provenance=[Provenance(source_name=registered)],
            )
        )
        permits = PermitStore(session)
        permits.upsert(
            PermitRecord(
                permit_key="fixture:permit:attributed",
                permit_number="P-ATTRIBUTED",
                jurisdiction="Fixture jurisdiction",
                county="San Bernardino",
                provenance=[
                    Provenance(source_name=registered),
                    Provenance(source_name=unregistered),
                ],
            )
        )
        permits.upsert(
            PermitRecord(
                permit_key="fixture:permit:unregistered",
                permit_number="P-UNREGISTERED",
                jurisdiction="Fixture jurisdiction",
                county="San Bernardino",
                provenance=[Provenance(source_name=unregistered)],
            )
        )

    with Session(engine) as session:
        result = build_operator_source_registry(session)

    by_name = {entry.source_name: entry for entry in result.entries}
    attributed = by_name[registered]
    assert attributed.attribution_name_unambiguous is True
    assert attributed.attributed_ceqa_records_in_scan == 1
    assert attributed.attributed_permit_records_in_scan == 1
    assert attributed.attributed_records_in_scan == 2
    assert by_name["Second configured portal"].attributed_records_in_scan == 0
    assert result.ceqa_records_total == result.ceqa_records_scanned == 1
    assert result.permit_records_total == result.permit_records_scanned == 2
    assert result.attribution_scan_truncated is False
    assert result.records_with_registered_source_in_scan == 2
    assert result.records_without_registered_source_in_scan == 1
    assert result.unregistered_source_names_in_scan == [unregistered]
    assert result.unregistered_source_names_truncated is False
    engine.dispose()


def test_source_registry_projection_withholds_ambiguous_name_attribution(tmp_path):
    path = tmp_path / "registry-attribution-ambiguous.sqlite3"
    engine = create_database_engine(f"sqlite:///{path}")
    initialize_database(engine)
    repeated_name = "Repeated configured portal"
    with Session(engine) as session, session.begin():
        store = SourceRegistryStore(session)
        store.upsert_source(
            _source(
                repeated_name,
                public_url="https://first.example.invalid/public/",
            )
        )
        store.upsert_source(
            _source(
                repeated_name,
                public_url="https://second.example.invalid/public/",
            )
        )
        CeqaStore(session).upsert(
            CeqaRecord(
                ceqa_key="fixture:ceqa:ambiguous",
                title="Ambiguous attribution fixture",
                county="San Bernardino",
                provenance=[Provenance(source_name=repeated_name)],
            )
        )

    with Session(engine) as session:
        result = build_operator_source_registry(session)

    assert result.ambiguous_registry_source_names == [repeated_name]
    assert result.records_with_registered_source_in_scan == 0
    assert result.records_without_registered_source_in_scan == 1
    assert len(result.entries) == 2
    assert all(not entry.attribution_name_unambiguous for entry in result.entries)
    assert all(entry.attributed_records_in_scan == 0 for entry in result.entries)
    engine.dispose()



def test_source_attribution_is_withheld_when_registry_identity_scan_is_incomplete(
    tmp_path, monkeypatch
):
    path = tmp_path / "registry-attribution-identity-cap.sqlite3"
    engine = create_database_engine(f"sqlite:///{path}")
    initialize_database(engine)
    with Session(engine) as session, session.begin():
        store = SourceRegistryStore(session)
        store.upsert_source(_source("First configured portal"))
        store.upsert_source(
            _source(
                "Second configured portal",
                public_url="https://second.example.invalid/public/",
            )
        )
        CeqaStore(session).upsert(
            CeqaRecord(
                ceqa_key="fixture:ceqa:identity-cap",
                title="Identity cap fixture",
                county="San Bernardino",
                provenance=[Provenance(source_name="First configured portal")],
            )
        )

    monkeypatch.setattr(
        "constructionsight.operator_source_registry.SOURCE_IDENTITY_SCAN_LIMIT", 1
    )
    with Session(engine) as session:
        result = build_operator_source_registry(session)

    assert result.source_identity_scan_limit == 1
    assert result.source_identity_rows_scanned == 1
    assert result.source_identity_scan_truncated is True
    assert result.source_attribution_available is False
    assert result.records_with_registered_source_in_scan == 0
    assert result.records_without_registered_source_in_scan == 0
    assert result.unregistered_source_names_in_scan == []
    assert all(not entry.attribution_name_unambiguous for entry in result.entries)
    assert all(entry.attributed_records_in_scan == 0 for entry in result.entries)
    engine.dispose()


def test_source_attribution_discloses_bounded_record_scan_truncation(
    tmp_path, monkeypatch
):
    path = tmp_path / "registry-attribution-record-cap.sqlite3"
    engine = create_database_engine(f"sqlite:///{path}")
    initialize_database(engine)
    source_name = "Synthetic San Bernardino portal"
    with Session(engine) as session, session.begin():
        SourceRegistryStore(session).upsert_source(_source())
        store = CeqaStore(session)
        for index in range(2):
            store.upsert(
                CeqaRecord(
                    ceqa_key=f"fixture:ceqa:record-cap:{index}",
                    title=f"Record cap fixture {index}",
                    county="San Bernardino",
                    provenance=[Provenance(source_name=source_name)],
                )
            )

    monkeypatch.setattr(
        "constructionsight.operator_source_registry.SOURCE_ATTRIBUTION_SCAN_LIMIT", 1
    )
    with Session(engine) as session:
        result = build_operator_source_registry(session)

    assert result.source_attribution_available is True
    assert result.ceqa_records_total == 2
    assert result.ceqa_records_scanned == 1
    assert result.attribution_scan_truncated is True
    assert result.records_with_registered_source_in_scan == 1
    assert result.records_without_registered_source_in_scan == 0
    assert result.entries[0].attributed_ceqa_records_in_scan == 1
    engine.dispose()
