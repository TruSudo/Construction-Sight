from __future__ import annotations

import json

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from constructionsight.ceqa_models import CeqaRecord
from constructionsight.operator_watchlist import (
    add_source_watch,
    archive_source_watch,
    build_operator_watchlist_snapshot,
    create_operator_watchlist_engine,
)
from constructionsight.storage.database import create_database_engine, initialize_database
from constructionsight.storage.domain_store import CeqaStore
from constructionsight.storage.intelligence_orm import IntelligenceWatchlistRecord


def _database(tmp_path):
    path = tmp_path / "operator-watchlist.sqlite3"
    engine = create_database_engine(f"sqlite:///{path}")
    initialize_database(engine)
    with Session(engine) as session, session.begin():
        CeqaStore(session).upsert(
            CeqaRecord(
                ceqa_key="fixture:watch",
                title="Synthetic watched warehouse",
                county="San Bernardino",
            )
        )
    engine.dispose()
    return path


def test_persisted_watchlist_round_trip_and_archive(tmp_path) -> None:
    path = _database(tmp_path)
    engine = create_operator_watchlist_engine(path)
    try:
        with Session(engine, autoflush=False) as session, session.begin():
            first = add_source_watch(
                session, kind="ceqa", record_id="fixture:watch"
            )
            second = add_source_watch(
                session, kind="ceqa", record_id="fixture:watch"
            )
            assert first.watchlist_item_id == second.watchlist_item_id
            assert second.alert_enabled is False

        with Session(engine, autoflush=False) as session:
            snapshot = build_operator_watchlist_snapshot(session)
            assert snapshot["persisted_locally"] is True
            assert snapshot["source_records_read_only"] is True
            assert snapshot["source_monitoring_enabled"] is False
            assert snapshot["notification_delivery_enabled"] is False
            assert snapshot["commercial_actions_authorized"] is False
            assert snapshot["total"] == 1
            assert snapshot["items"] == [
                {
                    "watchlist_item_id": second.watchlist_item_id,
                    "record_kind": "ceqa",
                    "record_id": "fixture:watch",
                    "title": "Synthetic watched warehouse",
                    "county": "San Bernardino",
                    "status": "active",
                    "priority": 50,
                    "alert_enabled": False,
                    "target_available": True,
                    "created_at": second.created_at.isoformat(),
                    "updated_at": second.updated_at.isoformat(),
                }
            ]

        with Session(engine, autoflush=False) as session, session.begin():
            archived = archive_source_watch(
                session, kind="ceqa", record_id="fixture:watch"
            )
            assert archived.status.value == "archived"

        with Session(engine, autoflush=False) as session:
            assert build_operator_watchlist_snapshot(session)["total"] == 0
            row = session.scalar(select(IntelligenceWatchlistRecord))
            assert row is not None
            payload = json.loads(row.payload_json)
            assert row.status == payload["status"] == "archived"
    finally:
        engine.dispose()


def test_watchlist_rejects_missing_source_record(tmp_path) -> None:
    path = _database(tmp_path)
    engine = create_operator_watchlist_engine(path)
    try:
        with Session(engine, autoflush=False) as session, session.begin():
            with pytest.raises(LookupError, match="exact source record not found"):
                add_source_watch(session, kind="ceqa", record_id="fixture:missing")
    finally:
        engine.dispose()


def test_watchlist_write_engine_rejects_non_watchlist_mutation(tmp_path) -> None:
    path = _database(tmp_path)
    engine = create_operator_watchlist_engine(path)
    try:
        with Session(engine, autoflush=False) as session:
            with pytest.raises(
                RuntimeError,
                match="watchlist-table mutations only",
            ):
                session.execute(
                    text(
                        "UPDATE domain_ceqa_records "
                        "SET title = 'unauthorized mutation' "
                        "WHERE ceqa_key = 'fixture:watch'"
                    )
                )
            session.rollback()

        read_engine = create_database_engine(f"sqlite:///{path}")
        try:
            with Session(read_engine) as session:
                record = CeqaStore(session).get("fixture:watch")
                assert record is not None
                assert record.title == "Synthetic watched warehouse"
        finally:
            read_engine.dispose()
    finally:
        engine.dispose()
