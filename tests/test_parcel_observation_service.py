import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import inspect, select
from typer.testing import CliRunner

from constructionsight.parcel_assurance_models import (
    ParcelAssuranceSourceContext,
    ParcelAssuranceStatus,
)
from constructionsight.parcel_core_models import ParcelCoreRecord
from constructionsight.parcel_observation_models import (
    ParcelLongitudinalAssuranceStatus,
    ParcelObservationDispositionStatus,
    ParcelObservationTimeBasis,
    ParcelRecordObservation,
    ParcelSourceSelectionStatus,
)
from constructionsight.parcel_observation_service import (
    build_longitudinal_parcel_assurance,
    build_parcel_record_observation,
    select_current_parcel_observations,
)
from constructionsight.parcel_source_models import ParcelFieldRole
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.parcel_site_orm import (
    ParcelCurrentSelectionReportRow,
    ParcelRecordObservationRow,
)
from constructionsight.storage.parcel_site_store import (
    load_parcel_current_selection_report,
    load_parcel_record_observations,
    store_parcel_current_selection_report,
    store_parcel_record_observation,
)
from constructionsight.upstream_operator_cli import app as upstream_operator_app
from constructionsight.upstream_operator_models import UpstreamOperatorRecordKind
from constructionsight.upstream_operator_service import (
    get_upstream_operator_record,
    list_upstream_operator_records,
)

BASE_TIME = datetime(2026, 7, 14, 12, 0, tzinfo=UTC)


def _record(
    record_id: str,
    *,
    source_key: str = "parcel-source:a",
    source_record_id: str | None = None,
    created_at: datetime = BASE_TIME,
    source_updated_at: datetime | None = BASE_TIME - timedelta(days=1),
    zoning: str = "industrial",
    county: str = "San Bernardino",
    normalized_apn: str = "12345678",
) -> ParcelCoreRecord:
    return ParcelCoreRecord(
        parcel_record_id=record_id,
        source_key=source_key,
        source_record_id=source_record_id or f"row:{source_key}",
        apn="123-456-78",
        normalized_apn=normalized_apn,
        county=county,
        zoning=zoning,
        source_updated_at=source_updated_at,
        created_at=created_at,
    )


def _observation(record_id: str, **changes) -> ParcelRecordObservation:
    return build_parcel_record_observation(_record(record_id, **changes))


def _factory():
    engine = create_database_engine("sqlite:///:memory:")
    initialize_database(engine)
    return engine, session_factory(engine)


def test_observation_identity_is_complete_and_deterministic() -> None:
    record = _record("parcel:a:1")

    first = build_parcel_record_observation(record)
    second = build_parcel_record_observation(record)

    assert first == second
    assert first.observation_id == f"parcel-observation:{first.record_digest}"
    assert len(first.record_digest) == 64
    assert len(first.content_digest) == 64
    assert first.record.to_dict() == record.to_dict()


def test_observation_rejects_naive_evidence_times() -> None:
    record = _record(
        "parcel:a:naive",
        created_at=datetime(2026, 7, 14, 12, 0),
        source_updated_at=None,
    )

    with pytest.raises(ValueError, match="timezone-aware"):
        build_parcel_record_observation(record)


def test_observation_model_rejects_changed_record_digest() -> None:
    observation = _observation("parcel:a:1")

    with pytest.raises(ValueError, match="record digest mismatch"):
        ParcelRecordObservation(
            observation_id=observation.observation_id,
            record_digest="0" * 64,
            content_digest=observation.content_digest,
            record=observation.record,
        )


def test_newer_source_effective_time_wins_over_arrival_order() -> None:
    newer = _observation(
        "parcel:a:newer",
        created_at=BASE_TIME,
        source_updated_at=BASE_TIME - timedelta(days=1),
        zoning="industrial",
    )
    stale_late_arrival = _observation(
        "parcel:a:stale",
        created_at=BASE_TIME + timedelta(hours=1),
        source_updated_at=BASE_TIME - timedelta(days=2),
        zoning="residential",
    )

    report = select_current_parcel_observations([stale_late_arrival, newer])
    selection = report.source_selections[0]

    assert selection.time_basis is ParcelObservationTimeBasis.SOURCE_EFFECTIVE_AT
    assert selection.current_observation_id == newer.observation_id
    stale_disposition = next(
        item
        for item in selection.dispositions
        if item.observation_id == stale_late_arrival.observation_id
    )
    assert stale_disposition.status is ParcelObservationDispositionStatus.SUPERSEDED
    assert stale_disposition.superseded_by_observation_ids == [newer.observation_id]


def test_observation_time_is_used_only_when_all_effective_times_are_absent() -> None:
    earlier = _observation(
        "parcel:a:earlier",
        created_at=BASE_TIME,
        source_updated_at=None,
    )
    later = _observation(
        "parcel:a:later",
        created_at=BASE_TIME + timedelta(hours=1),
        source_updated_at=None,
    )

    report = select_current_parcel_observations([later, earlier])
    selection = report.source_selections[0]

    assert selection.time_basis is ParcelObservationTimeBasis.OBSERVED_AT
    assert selection.current_observation_id == later.observation_id


def test_mixed_time_bases_block_current_selection() -> None:
    effective = _observation("parcel:a:effective")
    undated = _observation(
        "parcel:a:undated",
        created_at=BASE_TIME + timedelta(hours=1),
        source_updated_at=None,
    )

    report = select_current_parcel_observations([effective, undated])
    selection = report.source_selections[0]

    assert report.requires_human_review is True
    assert selection.status is ParcelSourceSelectionStatus.AMBIGUOUS
    assert selection.time_basis is ParcelObservationTimeBasis.MIXED_UNCOMPARABLE
    assert selection.current_observation_id is None
    assert selection.candidate_observation_ids == sorted(
        [effective.observation_id, undated.observation_id]
    )


def test_same_time_content_conflict_preserves_candidates_and_supersession() -> None:
    older = _observation(
        "parcel:a:older",
        source_updated_at=BASE_TIME - timedelta(days=2),
        zoning="agricultural",
    )
    industrial = _observation(
        "parcel:a:industrial",
        source_updated_at=BASE_TIME - timedelta(days=1),
        zoning="industrial",
    )
    residential = _observation(
        "parcel:a:residential",
        created_at=BASE_TIME + timedelta(minutes=1),
        source_updated_at=BASE_TIME - timedelta(days=1),
        zoning="residential",
    )

    report = select_current_parcel_observations(
        [residential, older, industrial]
    )
    selection = report.source_selections[0]
    candidate_ids = sorted([industrial.observation_id, residential.observation_id])

    assert selection.status is ParcelSourceSelectionStatus.AMBIGUOUS
    assert selection.current_observation_id is None
    assert selection.candidate_observation_ids == candidate_ids
    older_disposition = next(
        item
        for item in selection.dispositions
        if item.observation_id == older.observation_id
    )
    assert older_disposition.status is ParcelObservationDispositionStatus.SUPERSEDED
    assert older_disposition.superseded_by_observation_ids == candidate_ids


def test_equivalent_same_time_observation_has_deterministic_current_record() -> None:
    earlier = _observation(
        "parcel:a:equivalent:1",
        created_at=BASE_TIME,
        source_record_id="row:a",
    )
    later = _observation(
        "parcel:a:equivalent:2",
        created_at=BASE_TIME + timedelta(minutes=1),
        source_record_id="row:a",
    )

    report = select_current_parcel_observations([later, earlier])
    selection = report.source_selections[0]

    assert earlier.content_digest == later.content_digest
    assert selection.current_observation_id == later.observation_id


def test_selection_rejects_multiple_parcel_subjects() -> None:
    first = _observation("parcel:a:1")
    second = _observation(
        "parcel:a:2",
        county="Riverside",
    )

    with pytest.raises(ValueError, match="same parcel"):
        select_current_parcel_observations([first, second])


def test_selection_identity_is_order_and_generation_time_independent() -> None:
    source_a = _observation("parcel:a:1")
    source_b = _observation(
        "parcel:b:1",
        source_key="parcel-source:b",
    )

    first = select_current_parcel_observations(
        [source_b, source_a],
        generated_at=BASE_TIME,
    )
    second = select_current_parcel_observations(
        [source_a, source_b],
        generated_at=BASE_TIME + timedelta(hours=1),
    )

    assert first.selection_report_id == second.selection_report_id
    assert first.source_selections == second.source_selections


def test_selection_model_rejects_changed_report_identity() -> None:
    report = select_current_parcel_observations([_observation("parcel:a:1")])
    payload = report.to_dict()
    payload["selection_report_id"] = f"parcel-current-selection:{'0' * 64}"

    with pytest.raises(ValueError, match="identity mismatch"):
        type(report).model_validate(payload)


def test_longitudinal_assurance_uses_only_current_records() -> None:
    old_a = _observation(
        "parcel:a:old",
        source_updated_at=BASE_TIME - timedelta(days=2),
        zoning="residential",
    )
    current_a = _observation(
        "parcel:a:current",
        source_updated_at=BASE_TIME - timedelta(days=1),
        zoning="industrial",
    )
    current_b = _observation(
        "parcel:b:current",
        source_key="parcel-source:b",
        source_updated_at=BASE_TIME - timedelta(hours=12),
        zoning="industrial",
    )
    contexts = [
        ParcelAssuranceSourceContext(
            source_key="parcel-source:a",
            lineage_key="lineage:a",
        ),
        ParcelAssuranceSourceContext(
            source_key="parcel-source:b",
            lineage_key="lineage:b",
        ),
    ]

    result = build_longitudinal_parcel_assurance(
        observations=[old_a, current_b, current_a],
        source_contexts=contexts,
        field_roles=[ParcelFieldRole.ZONING],
        generated_at=BASE_TIME + timedelta(hours=2),
    )

    assert result.status is ParcelLongitudinalAssuranceStatus.BUILT
    assert result.assurance_report is not None
    assurance = result.assurance_report.field_assurances[0]
    assert assurance.status is ParcelAssuranceStatus.INDEPENDENTLY_CORROBORATED
    assert {claim.parcel_record_id for claim in result.assurance_report.claims} == {
        "parcel:a:current",
        "parcel:b:current",
    }


def test_ambiguous_timeline_withholds_assurance() -> None:
    first = _observation("parcel:a:1", zoning="industrial")
    second = _observation(
        "parcel:a:2",
        created_at=BASE_TIME + timedelta(minutes=1),
        zoning="residential",
    )
    context = ParcelAssuranceSourceContext(
        source_key="parcel-source:a",
        lineage_key="lineage:a",
    )

    result = build_longitudinal_parcel_assurance(
        observations=[first, second],
        source_contexts=[context],
        field_roles=[ParcelFieldRole.ZONING],
    )

    assert result.status is ParcelLongitudinalAssuranceStatus.BLOCKED_REVIEW
    assert result.assurance_report is None
    assert result.selection.requires_human_review is True


def test_longitudinal_assurance_requires_exact_source_contexts() -> None:
    observation = _observation("parcel:a:1")

    with pytest.raises(ValueError, match="exactly match"):
        build_longitudinal_parcel_assurance(
            observations=[observation],
            source_contexts=[],
            field_roles=[ParcelFieldRole.ZONING],
        )


def test_observation_and_selection_tables_are_created() -> None:
    engine, _session_factory = _factory()

    table_names = set(inspect(engine).get_table_names())

    assert "parcel_record_observations" in table_names
    assert "parcel_current_selection_reports" in table_names


def test_observation_store_is_append_only_and_exactly_idempotent() -> None:
    _engine, factory = _factory()
    observation = _observation("parcel:a:1")

    with managed_session(factory) as session:
        first = store_parcel_record_observation(session, observation)
        replay = store_parcel_record_observation(session, observation)
        rows = session.execute(select(ParcelRecordObservationRow)).scalars().all()

        assert first.id == replay.id
        assert len(rows) == 1
        assert rows[0].record_digest == observation.record_digest


def test_observation_store_roundtrip_checks_indexed_integrity() -> None:
    _engine, factory = _factory()
    observation = _observation("parcel:a:1")

    with managed_session(factory) as session:
        store_parcel_record_observation(session, observation)
        loaded = load_parcel_record_observations(
            session,
            normalized_apn="12345678",
            county="San Bernardino",
            source_key="parcel-source:a",
        )

        assert loaded == [observation]
        row = session.execute(select(ParcelRecordObservationRow)).scalar_one()
        row.content_digest = "0" * 64
        session.flush()
        with pytest.raises(ValueError, match="indexed fields disagree"):
            load_parcel_record_observations(
                session,
                normalized_apn="12345678",
                county="San Bernardino",
            )


def test_observation_store_rejects_identity_collision() -> None:
    _engine, factory = _factory()
    first = _observation("parcel:a:1")
    different = _observation("parcel:a:2", zoning="residential").model_copy(
        update={"observation_id": first.observation_id}
    )

    with managed_session(factory) as session:
        store_parcel_record_observation(session, first)
        with pytest.raises(ValueError, match="identity collision"):
            store_parcel_record_observation(session, different)


def test_selection_store_is_immutable_and_semantically_idempotent() -> None:
    _engine, factory = _factory()
    observation = _observation("parcel:a:1")
    report = select_current_parcel_observations(
        [observation],
        generated_at=BASE_TIME,
    )
    replay = report.model_copy(
        update={"generated_at": BASE_TIME + timedelta(minutes=1)}
    )

    with managed_session(factory) as session:
        first = store_parcel_current_selection_report(session, report)
        second = store_parcel_current_selection_report(session, replay)
        rows = session.execute(
            select(ParcelCurrentSelectionReportRow)
        ).scalars().all()

        assert first.id == second.id
        assert len(rows) == 1
        assert rows[0].observed_generated_at == BASE_TIME.isoformat()
        loaded = load_parcel_current_selection_report(
            session,
            report.selection_report_id,
        )
        assert loaded == report


def test_selection_store_rejects_identity_collision() -> None:
    _engine, factory = _factory()
    report = select_current_parcel_observations(
        [_observation("parcel:a:1")],
        generated_at=BASE_TIME,
    )
    different = report.model_copy(
        update={"limitations": ["changed without changing identity"]}
    )

    with managed_session(factory) as session:
        store_parcel_current_selection_report(session, report)
        with pytest.raises(ValueError, match="identity collision"):
            store_parcel_current_selection_report(session, different)


def test_operator_exposes_observation_and_current_selection_payloads() -> None:
    _engine, factory = _factory()
    observation = _observation("parcel:a:1")
    report = select_current_parcel_observations(
        [observation],
        generated_at=BASE_TIME,
    )

    with managed_session(factory) as session:
        store_parcel_record_observation(session, observation)
        store_parcel_current_selection_report(session, report)
        observations = list_upstream_operator_records(
            session,
            UpstreamOperatorRecordKind.PARCEL_OBSERVATION,
            source_key="parcel-source:a",
            apn="12345678",
            county="San Bernardino",
        )
        selection = get_upstream_operator_record(
            session,
            UpstreamOperatorRecordKind.PARCEL_CURRENT_SELECTION,
            report.selection_report_id,
        )

    assert observations[0].record_id == observation.observation_id
    assert observations[0].payload["record"]["zoning"] == "industrial"
    assert selection is not None
    assert selection.status == "complete"
    assert selection.payload["current_observation_ids"] == [observation.observation_id]


def test_operator_cli_exposes_longitudinal_parcel_records(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'parcel-longitudinal.sqlite3'}"
    engine = create_database_engine(database_url)
    factory = session_factory(engine)
    initialize_database(engine)
    observation = _observation("parcel:a:1")
    report = select_current_parcel_observations(
        [observation],
        generated_at=BASE_TIME,
    )
    with managed_session(factory) as session:
        store_parcel_record_observation(session, observation)
        store_parcel_current_selection_report(session, report)

    runner = CliRunner()
    observations = runner.invoke(
        upstream_operator_app,
        [
            "list",
            "parcel_observation",
            "--database-url",
            database_url,
            "--source-key",
            "parcel-source:a",
            "--json-output",
        ],
    )
    selections = runner.invoke(
        upstream_operator_app,
        [
            "list",
            "parcel_current_selection",
            "--database-url",
            database_url,
            "--status",
            "complete",
            "--json-output",
        ],
    )

    assert observations.exit_code == 0
    assert selections.exit_code == 0
    observation_payload = json.loads(observations.stdout)
    selection_payload = json.loads(selections.stdout)
    assert observation_payload[0]["record_id"] == observation.observation_id
    assert selection_payload[0]["record_id"] == report.selection_report_id
