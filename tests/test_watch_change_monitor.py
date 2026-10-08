from constructionsight.intelligence import RuntimeEventType, WatchlistStatus
from constructionsight.operator_watchlist import add_source_watch
from constructionsight.permit_models import PermitRecord
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.domain_store import PermitStore
from constructionsight.storage.intelligence_store import IntelligenceStore
from constructionsight.watch_change_monitor import scan_watched_source_changes


def _permit(status: str) -> PermitRecord:
    return PermitRecord(
        permit_key="permit:watch:001",
        permit_number="WATCH-001",
        jurisdiction="Test City",
        county="San Bernardino",
        status=status,
    )


def test_retained_source_change_automatically_triggers_exact_watch_once() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    factory = session_factory(engine)

    with managed_session(factory) as session:
        PermitStore(session).upsert(_permit("Applied"))
        watch = add_source_watch(
            session,
            kind="permit",
            record_id="permit:watch:001",
        )
        PermitStore(session).upsert(_permit("Issued"))

        persisted = IntelligenceStore(session).list_watchlist_items(
            workspace_id="operator-local",
            limit=10,
        )
        attention = [
            event
            for event in IntelligenceStore(session).list_runtime_events(limit=20)
            if event.source_service == "watchlist_change_monitor"
        ]
        recovery = scan_watched_source_changes(session)

    assert len(persisted) == 1
    assert persisted[0].watchlist_item_id == watch.watchlist_item_id
    assert persisted[0].status is WatchlistStatus.TRIGGERED
    assert len(attention) == 1
    assert attention[0].event_type is RuntimeEventType.SOURCE_RECORD_CHANGED
    assert attention[0].requires_user_attention is True
    assert attention[0].causation_id is not None
    assert attention[0].source_record_refs == ["permit:permit:watch:001"]
    assert recovery.triggered_watch_ids == ()
    assert recovery.trigger_event_ids == ()


def test_unchanged_source_replay_does_not_trigger_watch() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    factory = session_factory(engine)

    with managed_session(factory) as session:
        permit = _permit("Applied")
        PermitStore(session).upsert(permit)
        add_source_watch(
            session,
            kind="permit",
            record_id="permit:watch:001",
        )
        PermitStore(session).upsert(permit)

        persisted = IntelligenceStore(session).list_watchlist_items(
            workspace_id="operator-local",
            limit=10,
        )
        attention = [
            event
            for event in IntelligenceStore(session).list_runtime_events(limit=20)
            if event.source_service == "watchlist_change_monitor"
        ]

    assert persisted[0].status is WatchlistStatus.ACTIVE
    assert attention == []


def test_reactivating_watch_acknowledges_prior_change() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    factory = session_factory(engine)

    with managed_session(factory) as session:
        PermitStore(session).upsert(_permit("Applied"))
        add_source_watch(
            session,
            kind="permit",
            record_id="permit:watch:001",
        )
        PermitStore(session).upsert(_permit("Issued"))

        triggered = IntelligenceStore(session).list_watchlist_items(
            workspace_id="operator-local",
            limit=10,
        )[0]
        assert triggered.status is WatchlistStatus.TRIGGERED

        reactivated = add_source_watch(
            session,
            kind="permit",
            record_id="permit:watch:001",
        )
        recovery = scan_watched_source_changes(session)

    assert reactivated.status is WatchlistStatus.ACTIVE
    assert recovery.triggered_watch_ids == ()
