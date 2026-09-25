"""Read-only operator projection of persisted public-source configuration."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from constructionsight.models import PublicSource
from constructionsight.operator_source_registry import (
    SOURCE_REGISTRY_RESULT_LIMIT,
    build_operator_source_registry,
)
from constructionsight.storage.database import create_database_engine, initialize_database
from constructionsight.storage.source_registry import SourceRegistryStore


def _source(
    name: str = "Synthetic San Bernardino portal",
    *,
    county: str = "San Bernardino",
    platform: str = "accela_aca",
    verification_status: str = "partial",
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
            "public_url": "https://example.invalid/public/",
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
                county="Riverside",
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
