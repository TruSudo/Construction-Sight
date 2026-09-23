"""Database-to-operator integration tests using explicitly synthetic records."""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from datetime import date
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from constructionsight import operator_web
from constructionsight.ceqa_models import CeqaRecord
from constructionsight.ceqanet_persistence_preview import build_ceqanet_persistence_preview
from constructionsight.ceqanet_write_plan import build_ceqanet_write_plan
from constructionsight.entity_models import Entity
from constructionsight.lead_review_models import LeadReviewPackage, LeadReviewStatus
from constructionsight.lead_workflow_models import LeadWorkflowRecord, LeadWorkflowStatus
from constructionsight.operator_dashboard import (
    ENTITY_RESULT_LIMIT,
    ENTITY_SCAN_LIMIT,
    FOOTPRINT_SCAN_LIMIT,
    build_dashboard_snapshot,
    build_entity_neighborhood,
    build_geographic_footprint,
    build_historical_timeline,
    build_workflow_snapshot,
    build_workflow_status_summary,
)
from constructionsight.operator_services.ceqanet_persistence_service import (
    execute_authorized_ceqanet_write_plan,
)
from constructionsight.operator_source_candidate import (
    SourceRecordNotFound,
    build_source_candidate_preview,
)
from constructionsight.operator_web import _parameters, create_handler
from constructionsight.parcel_core_models import (
    ParcelCoreRecord,
    ParcelGeometry,
    ParcelGeometryKind,
)
from constructionsight.permit_models import PermitRecord
from constructionsight.provenance import Provenance
from constructionsight.site_models import Site
from constructionsight.storage.database import create_database_engine, initialize_database
from constructionsight.storage.domain_orm import CeqaDomainRecord, SiteRecord
from constructionsight.storage.domain_store import CeqaStore, PermitStore, SiteStore
from constructionsight.storage.lead_workflow_orm import LeadReviewPackageRecord
from constructionsight.storage.lead_workflow_store import (
    store_lead_review_package,
    store_lead_workflow_record,
)
from constructionsight.storage.operator_read_store import create_operator_read_engine
from constructionsight.storage.parcel_site_orm import ParcelCoreRecordRow
from constructionsight.storage.parcel_site_store import store_parcel_core_record


def _provenance():
    return [Provenance(source_name="Synthetic integration fixture", evidence_text="Fixture only")]


def _record(key="fixture:one", **updates):
    values = dict(
        ceqa_key=key,
        title="Synthetic warehouse record",
        county="San Bernardino",
        lead_agency="Fixture planning agency",
        state_clearinghouse_number="2099012345",
        site=Site(
            site_key="fixture:site",
            county="San Bernardino",
            latitude=34.05,
            longitude=-117.6,
            apn="fixture:123",
            provenance=_provenance(),
        ),
        entities=[
            Entity(
                entity_key="fixture:party",
                name="Fixture Builder",
                role="contractor",
                provenance=_provenance(),
            )
        ],
        provenance=_provenance(),
    )
    values.update(updates)
    return CeqaRecord(**values)


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "operator.sqlite3"
    engine = create_database_engine(f"sqlite:///{path}")
    initialize_database(engine)
    yield path, engine
    engine.dispose()


@contextmanager
def _server(path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(path))
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def _get(port, path="/api/snapshot", *, headers=None, method="GET"):
    connection = HTTPConnection("127.0.0.1", port, timeout=3)
    try:
        connection.request(method, path, headers=headers or {})
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


def test_authorized_ceqanet_preview_to_database_to_http(tmp_path):
    path = tmp_path / "from-chain.sqlite3"
    preview = build_ceqanet_persistence_preview(
        {
            "enrichment": {
                "records": [
                    {
                        "sch_number": "2099012345",
                        "title": "Synthetic chain fixture — not a live opportunity",
                        "county": "San Bernardino",
                        "city": "Fontana",
                        "lead_agency": "Fixture City",
                        "detail_url": "https://example.org/fixture",
                        "raw_result_text": "Synthetic evidence",
                    }
                ]
            }
        }
    )
    plan = build_ceqanet_write_plan(preview.to_dict())
    result = execute_authorized_ceqanet_write_plan(
        write_plan_payload=plan.to_dict(),
        database_url=f"sqlite:///{path}",
        caller_confirmation=True,
        authorization_reason="Apply synthetic local integration fixture",
        operator_id="operator:integration-test",
    )
    assert result.execution.applied_count == 3
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    with _server(path) as port:
        status, headers, body = _get(port)
        assert status == 200
        data = json.loads(body)
        record = data["projects"][0]
        assert record["title"] == "Synthetic chain fixture — not a live opportunity"
        assert record["entities"][0]["name"] == "Fixture City"
        assert record["provenance"][0]["evidence_text"] == "Synthetic evidence"
        assert record["point"] is None
        assert data["mapped_on_page"] == 0
        assert data["live_collection_enabled"] is False
        assert data["crime_overlay_enabled"] is False
        assert "unsafe-inline" not in headers["Content-Security-Policy"]
        for asset in ["/", "/operator_ui.js", "/operator_ui.css"]:
            assert _get(port, asset)[0] == 200
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_search_filters_before_pagination_and_escapes_wildcards(database):
    _, engine = database
    with Session(engine) as session, session.begin():
        for i in range(4):
            CeqaStore(session).upsert(_record(f"fixture:{i}"))
        CeqaStore(session).upsert(
            _record("fixture:match", title="100%_match", county="Riverside County")
        )
    with Session(engine) as session:
        result = build_dashboard_snapshot(session, query="%_", county="Riverside", limit=1)
        assert result.total == result.returned == 1
        assert result.projects[0].record_id == "fixture:match"
        first = build_dashboard_snapshot(session, query="Fixture Builder", limit=2)
        second = build_dashboard_snapshot(session, query="Fixture Builder", limit=2, offset=2)
        assert first.total == second.total == 5
        assert first.has_more and second.has_more
        assert set(p.record_id for p in first.projects).isdisjoint(
            p.record_id for p in second.projects
        )
        assert build_dashboard_snapshot(session, query="2099012345").total == 5
        assert build_dashboard_snapshot(session, query="fixture:123").total == 5
        assert build_dashboard_snapshot(session, query="Fixture planning agency").total == 5


@pytest.mark.parametrize(
    "updates,reason",
    [
        ({"latitude": None}, "complete geographic"),
        ({"latitude": float("nan")}, "non-finite"),
        ({"longitude": float("inf")}, "non-finite"),
        ({"latitude": 91}, "outside geographic"),
        ({"latitude": 89}, "Mercator"),
        ({"provenance": []}, "no source provenance"),
        ({"county": "Riverside"}, "counties disagree"),
    ],
)
def test_unsupported_coordinates_remain_visible_but_unmapped(database, updates, reason):
    _, engine = database
    record = _record()
    for key, value in updates.items():
        setattr(record.site, key, value)
    with Session(engine) as session, session.begin():
        CeqaStore(session).upsert(record)
    with Session(engine) as session:
        result = build_dashboard_snapshot(session)
        assert result.total == 1
        assert result.mapped_on_page == 0
        assert result.projects[0].point is None
        # JSON serialization normalizes NaN/Infinity to null in embedded source models.
        expected = (
            "complete geographic"
            if any(
                isinstance(v, float) and (v != v or abs(v) == float("inf"))
                for v in updates.values()
            )
            else reason
        )
        assert expected in result.projects[0].map_reason


def test_permit_coordinates_evidence_and_roles_are_preserved(database):
    _, engine = database
    source = _record()
    with Session(engine) as session, session.begin():
        PermitStore(session).upsert(
            PermitRecord(
                permit_key="fixture:permit",
                permit_number="FIX-42",
                jurisdiction="Fontana",
                county="San Bernardino",
                status="Issued",
                site=source.site,
                entities=source.entities,
                provenance=source.provenance,
            )
        )
    with Session(engine) as session:
        result = build_dashboard_snapshot(session, kind="permit", query="FIX-42")
        record = result.projects[0]
        assert result.mapped_on_page == 1
        assert record.point.latitude == 34.05
        assert record.point.classification == "source_claimed"
        assert record.entities[0].role == "contractor"
        assert record.point.provenance == source.site.provenance
        assert record.source_status == "Issued"


def test_does_not_join_unrelated_site_or_replace_embedded_evidence(database):
    _, engine = database
    with Session(engine) as session, session.begin():
        CeqaStore(session).upsert(_record(site=None))
        SiteStore(session).upsert(_record().site)
        SiteStore(session).upsert(
            Site(
                site_key="other",
                county="San Bernardino",
                latitude=0,
                longitude=0,
                provenance=_provenance(),
            )
        )
    with Session(engine) as session:
        record = build_dashboard_snapshot(session).projects[0]
        assert record.point is None and record.site_key is None
        assert session.scalar(select(SiteRecord).limit(1)) is not None


def test_workflow_uses_exact_review_not_newest_for_candidate(database):
    _, engine = database
    with Session(engine) as session, session.begin():
        for package, note in [
            ("review:exact", "Exact evidence"),
            ("review:newer", "Wrong evidence"),
        ]:
            store_lead_review_package(
                session,
                LeadReviewPackage(
                    package_id=package,
                    base_candidate_id="fixture:candidate",
                    lead_score=50,
                    status=LeadReviewStatus.MONITOR,
                    summary=package,
                    evidence_notes=[note],
                ),
            )
        store_lead_workflow_record(
            session,
            LeadWorkflowRecord(
                workflow_id="workflow:fixture",
                package_id="review:exact",
                base_candidate_id="fixture:candidate",
                status=LeadWorkflowStatus.MONITOR,
                lead_score=50,
            ),
        )
    with Session(engine) as session:
        result = build_workflow_snapshot(session, limit=1)
        assert result["leads"][0]["evidence_notes"] == ["Exact evidence"]
        assert result["leads"][0]["summary"] == "review:exact"
        assert build_workflow_snapshot(session, offset=1)["returned"] == 0
    with Session(engine) as session, session.begin():
        row = session.scalar(
            select(LeadReviewPackageRecord).where(
                LeadReviewPackageRecord.package_id == "review:exact"
            )
        )
        payload = json.loads(row.payload_json)
        payload["base_candidate_id"] = "different"
        row.payload_json = json.dumps(payload)
    with Session(engine) as session, pytest.raises(ValueError, match="identity disagree"):
        build_workflow_snapshot(session)


def test_combined_source_pagination_search_and_identity(database):
    path, engine = database
    with Session(engine) as session, session.begin():
        CeqaStore(session).upsert(_record("shared", title="Cross-family project"))
        CeqaStore(session).upsert(_record("ceqa:second", title="Second CEQA project"))
        PermitStore(session).upsert(
            PermitRecord(
                permit_key="shared",
                permit_number="Cross-family permit",
                jurisdiction="Fontana",
                county="San Bernardino",
                provenance=_provenance(),
            )
        )
        PermitStore(session).upsert(
            PermitRecord(
                permit_key="permit:second",
                permit_number="OTHER-2",
                jurisdiction="Riverside",
                county="Riverside",
                provenance=_provenance(),
            )
        )
    with Session(engine) as session:
        first = build_dashboard_snapshot(session, kind="all", limit=2)
        crossing = build_dashboard_snapshot(session, kind="all", limit=2, offset=1)
        last = build_dashboard_snapshot(session, kind="all", limit=2, offset=3)
        assert first.selection == "all"
        assert (first.total, first.returned, first.has_more) == (4, 2, True)
        assert [(p.record_kind, p.record_id) for p in crossing.projects] == [
            ("ceqa", "ceqa:second"),
            ("permit", "shared"),
        ]
        assert (last.total, last.returned, last.has_more) == (4, 1, False)
        assert last.projects[0].record_id == "permit:second"
        assert build_dashboard_snapshot(session, kind="permit").total == 2
        matching = build_dashboard_snapshot(session, kind="all", query="Cross-family")
        assert matching.total == 2
        assert {p.record_kind for p in matching.projects} == {"ceqa", "permit"}
        county = build_dashboard_snapshot(session, kind="all", county="Riverside")
        assert [(p.record_kind, p.record_id) for p in county.projects] == [
            ("permit", "permit:second")
        ]
        assert first.mapped_on_page == 2
        assert crossing.mapped_on_page == 1
    with _server(path) as port:
        status, _, body = _get(port, "/api/snapshot?kind=all&limit=2&offset=1")
        assert status == 200
        payload = json.loads(body)
        assert (payload["selection"], payload["total"], payload["returned"]) == (
            "all", 4, 2
        )
        assert [p["record_kind"] for p in payload["projects"]] == ["ceqa", "permit"]
        assert json.loads(_get(port, "/api/snapshot")[2])["selection"] == "all"
        footprint = json.loads(
            _get(port, "/api/footprint?kind=all&q=Cross-family&county=San+Bernardino")[2]
        )
        assert footprint["matching_total"] == footprint["records_scanned"] == 2
        assert footprint["mapped_in_scan"] == 1
        assert footprint["truncated"] is False
        assert [(p["ordinal"], p["record_kind"], p["record_id"]) for p in footprint["points"]] == [
            (0, "ceqa", "shared")
        ]


def test_geographic_footprint_discloses_scan_truncation(database, monkeypatch):
    _, engine = database
    monkeypatch.setattr("constructionsight.operator_dashboard.FOOTPRINT_SCAN_LIMIT", 2)
    with Session(engine) as session, session.begin():
        for i in range(3):
            CeqaStore(session).upsert(_record(f"fixture:{i}"))
    with Session(engine) as session:
        footprint = build_geographic_footprint(session)
        assert footprint.matching_total == 3
        assert footprint.records_scanned == 2
        assert footprint.mapped_in_scan == 2
        assert footprint.scan_limit == 2
        assert footprint.truncated is True
        assert [point.ordinal for point in footprint.points] == [0, 1]
    assert FOOTPRINT_SCAN_LIMIT == 5_000


def test_read_only_database_cannot_write_and_missing_path_is_not_created(tmp_path):
    path = tmp_path / "space # ? café.sqlite3"
    original = tmp_path / "original.sqlite3"
    engine = create_database_engine(f"sqlite:///{original}")
    initialize_database(engine)
    engine.dispose()
    original.rename(path)
    readonly = create_operator_read_engine(path)
    with readonly.connect() as connection:
        assert connection.scalar(select(1)) == 1
        with pytest.raises(OperationalError, match="readonly"):
            connection.execute(text("CREATE TABLE should_never_exist (value TEXT)"))
    readonly.dispose()
    missing = tmp_path / "missing.sqlite3"
    with pytest.raises(FileNotFoundError):
        create_handler(missing)
    assert not missing.exists()


def test_operator_rejects_empty_sqlite_before_serving(tmp_path):
    path = tmp_path / "empty.sqlite3"
    engine = create_database_engine(f"sqlite:///{path}")
    with engine.connect() as connection:
        connection.execute(text("CREATE TABLE unrelated (id INTEGER)"))
        connection.commit()
    engine.dispose()
    before = path.read_bytes()
    with pytest.raises(OperationalError, match="no such table"):
        create_handler(path)
    assert path.read_bytes() == before


def test_operator_rejects_legacy_column_shape_before_serving(database):
    path, engine = database
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE domain_ceqa_records RENAME COLUMN title TO old_title"))
    before = path.read_bytes()
    with pytest.raises(OperationalError, match="no such column"):
        create_handler(path)
    assert path.read_bytes() == before


def test_health_rechecks_schema_after_startup(database):
    path, engine = database
    with _server(path) as port:
        assert _get(port, "/api/health")[0] == 200
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE lead_review_packages"))
        status, _, body = _get(port, "/api/health")
        assert status == 503
        assert b"database_readable" not in body
        assert str(path).encode() not in body


@pytest.mark.parametrize(
    "query",
    [
        "kind=bad",
        "limit=501",
        "offset=-1",
        "q=x&q=y",
        "county=Orange",
        "unknown=1",
        "limit=nan",
        "q=" + "x" * 201,
    ],
)
def test_http_rejects_invalid_requests(database, query):
    path, _ = database
    with _server(path) as port:
        assert _get(port, "/api/snapshot?" + query)[0] == 400


@pytest.mark.parametrize(
    "headers",
    [
        {"Host": "attacker.example"},
        {"Origin": "https://attacker.example"},
        {"Sec-Fetch-Site": "cross-site"},
    ],
)
def test_http_rejects_foreign_origins(database, headers):
    path, _ = database
    with _server(path) as port:
        assert _get(port, headers=headers)[0] == 403


def test_http_errors_do_not_expose_database_paths_or_repair_data(database):
    path, engine = database
    with Session(engine) as session, session.begin():
        CeqaStore(session).upsert(_record())
        row = session.scalar(select(CeqaDomainRecord))
        row.site_json = "corrupted"
    before = path.read_bytes()
    with _server(path) as port:
        status, _, body = _get(port)
        assert status == 503
        assert str(path).encode() not in body
        assert b"corrupted" not in body
        assert _get(port, "/api/snapshot", method="POST")[0] == 501
    assert path.read_bytes() == before


@pytest.mark.parametrize("query", ["limit=5", "offset=1", "unknown=1", "county=Orange"])
def test_footprint_rejects_paging_and_invalid_filters(database, query):
    path, _ = database
    with _server(path) as port:
        assert _get(port, "/api/footprint?" + query)[0] == 400


def test_http_parameter_dispatch_is_typed_and_scoped() -> None:
    records = _parameters("kind=permit&q=fixture&county=Riverside&limit=7&offset=2")
    assert (records.kind, records.query, records.county) == ("permit", "fixture", "Riverside")
    assert (records.limit, records.offset, records.entity_key) == (7, 2, None)
    workflow = _parameters("limit=2&offset=1", workflow=True)
    assert (workflow.kind, workflow.query, workflow.limit, workflow.offset) == (
        "all", "", 2, 1
    )
    assert workflow.entity_key is None
    entity = _parameters("kind=ceqa&entity_key=fixture%3Aparty", entity=True)
    assert (entity.kind, entity.entity_key) == ("ceqa", "fixture:party")
    with pytest.raises(ValueError, match="unsupported"):
        _parameters("kind=ceqa&limit=1&entity_key=fixture%3Aparty", entity=True)


def test_exact_entity_key_neighborhood_preserves_family_identity_and_source_claims(database):
    path, engine = database
    with Session(engine) as session, session.begin():
        original = _record("shared")
        CeqaStore(session).upsert(original)
        CeqaStore(session).upsert(
            _record(
                "fixture:unrelated",
                entities=[
                    Entity(
                        entity_key="fixture:party-other",
                        name="Fixture Builder",
                        role="contractor",
                        provenance=_provenance(),
                    )
                ],
            )
        )
        PermitStore(session).upsert(
            PermitRecord(
                permit_key="shared",
                permit_number="TEST-ENTITY",
                county="San Bernardino",
                jurisdiction="Fontana",
                site=original.site,
                entities=original.entities,
                provenance=original.provenance,
            )
        )
    with Session(engine) as session:
        result = build_entity_neighborhood(session, entity_key="fixture:party")
        assert result.total_source_records == result.scanned_source_records == 3
        assert result.matching_records_in_scan == result.returned == 2
        assert not result.source_scan_truncated and not result.matching_records_truncated
        assert {(row.record_kind, row.record_id) for row in result.records} == {
            ("ceqa", "shared"), ("permit", "shared")
        }
        assert all(row.entities[0].provenance == _provenance() for row in result.records)
        assert all(row.point is not None for row in result.records)
        assert build_entity_neighborhood(
            session, entity_key="fixture:party", kind="permit"
        ).returned == 1
        assert build_entity_neighborhood(
            session, entity_key="fixture:party", county="Riverside"
        ).returned == 0
        assert build_entity_neighborhood(
            session, entity_key="fixture:party-other"
        ).returned == 1
    with _server(path) as port:
        status, _, body = _get(
            port, "/api/entity-neighborhood?entity_key=fixture%3Aparty&county=San+Bernardino"
        )
        assert status == 200
        payload = json.loads(body)
        assert payload["entity_key"] == "fixture:party"
        assert payload["returned"] == payload["matching_records_in_scan"] == 2
        assert {row["record_kind"] for row in payload["records"]} == {"ceqa", "permit"}
        assert payload["read_only"] is True


def test_entity_neighborhood_discloses_source_scan_and_result_caps(database, monkeypatch):
    _, engine = database
    with Session(engine) as session, session.begin():
        for index in range(3):
            CeqaStore(session).upsert(_record(f"fixture:{index}"))
    with Session(engine) as session:
        monkeypatch.setattr("constructionsight.operator_dashboard.ENTITY_SCAN_LIMIT", 1)
        first = build_entity_neighborhood(session, entity_key="fixture:party")
        assert (first.total_source_records, first.scanned_source_records) == (3, 1)
        assert first.source_scan_truncated is True
        assert first.matching_records_truncated is False
        monkeypatch.setattr("constructionsight.operator_dashboard.ENTITY_SCAN_LIMIT", 3)
        monkeypatch.setattr("constructionsight.operator_dashboard.ENTITY_RESULT_LIMIT", 1)
        second = build_entity_neighborhood(session, entity_key="fixture:party")
        assert second.matching_records_in_scan == 3
        assert second.returned == 1
        assert second.source_scan_truncated is False
        assert second.matching_records_truncated is True
    assert ENTITY_SCAN_LIMIT == 5_000 and ENTITY_RESULT_LIMIT == 100


@pytest.mark.parametrize(
    "query",
    [
        "",
        "entity_key=",
        "entity_key=%20name",
        "entity_key=x&entity_key=x",
        "entity_key=x&q=unrelated",
        "entity_key=x&limit=1",
        "entity_key=x&offset=1",
        "entity_key=" + "x" * 256,
    ],
)
def test_entity_neighborhood_denies_missing_repeated_and_broad_parameters(database, query):
    path, _ = database
    with _server(path) as port:
        assert _get(port, "/api/entity-neighborhood?" + query)[0] == 400



def test_record_milestones_are_source_claims_and_preserve_family_and_dates(database):
    path, engine = database
    with Session(engine) as session, session.begin():
        CeqaStore(session).upsert(
            _record(
                "fixture:dated-ceqa",
                received_date=date(2025, 1, 3),
                posted_date=date(2025, 1, 4),
            )
        )
        PermitStore(session).upsert(
            PermitRecord(
                permit_key="fixture:dated-permit",
                permit_number="TEST-HISTORY",
                jurisdiction="Fontana",
                county="San Bernardino",
                applied_date=date(2025, 2, 1),
                issued_date=date(2025, 2, 8),
                status="Issued",
                provenance=_provenance(),
            )
        )
    with Session(engine) as session:
        records = {
            project.record_kind: project
            for project in build_dashboard_snapshot(session).projects
        }
        ceqa, permit = records["ceqa"], records["permit"]
        assert [(m.event_kind, m.recorded_date.isoformat()) for m in ceqa.milestones] == [
            ("ceqa_received", "2025-01-03"), ("ceqa_posted", "2025-01-04")
        ]
        assert [m.classification for m in ceqa.milestones] == [
            "source_claimed", "source_claimed"
        ]
        assert [(m.event_kind, m.recorded_date.isoformat()) for m in permit.milestones] == [
            ("permit_applied", "2025-02-01"), ("permit_issued", "2025-02-08")
        ]
        assert permit.source_status == "Issued" and permit.provenance == _provenance()
    with _server(path) as port:
        payload = json.loads(_get(port, "/api/snapshot?kind=permit")[2])
        assert payload["projects"][0]["milestones"] == [
            {
                "event_kind": "permit_applied",
                "recorded_date": "2025-02-01",
                "classification": "source_claimed",
            },
            {
                "event_kind": "permit_issued",
                "recorded_date": "2025-02-08",
                "classification": "source_claimed",
            },
        ]


def test_source_date_conflicts_are_not_silently_normalized(database):
    _, engine = database
    with Session(engine) as session, session.begin():
        CeqaStore(session).upsert(
            _record(
                "fixture:bad-ceqa-dates",
                received_date=date(2025, 5, 4),
                posted_date=date(2025, 5, 2),
            )
        )
        PermitStore(session).upsert(
            PermitRecord(
                permit_key="fixture:bad-permit-dates",
                permit_number="TEST-CONFLICT",
                jurisdiction="Fontana",
                county="San Bernardino",
                applied_date=date(2025, 5, 1),
                issued_date=date(2025, 5, 6),
                finaled_date=date(2025, 5, 3),
                provenance=_provenance(),
            )
        )
    with Session(engine) as session:
        records = build_dashboard_snapshot(session).projects
        assert len(records) == 2
        for row in records:
            assert any("dates conflict" in note for note in row.limitations)
            assert len(row.milestones) >= 2
            assert [m.recorded_date for m in row.milestones] == sorted(
                m.recorded_date for m in row.milestones
            )
            assert all(m.classification == "source_claimed" for m in row.milestones)



def test_exact_source_candidate_preview_is_read_only_and_family_scoped(database):
    path, engine = database
    with Session(engine) as session, session.begin():
        CeqaStore(session).upsert(_record("shared"))
        PermitStore(session).upsert(PermitRecord(
            permit_key="shared", permit_number="TEST-COLLISION",
            county="San Bernardino", jurisdiction="Fontana", provenance=_provenance(),
        ))
    with Session(engine) as session:
        first = build_source_candidate_preview(session, kind="ceqa", record_id="shared")
        repeated = build_source_candidate_preview(session, kind="ceqa", record_id="shared")
        other = build_source_candidate_preview(session, kind="permit", record_id="shared")
        assert first == repeated
        assert first.state == "review_required"
        assert first.candidate_key != other.candidate_key
        assert first.preview_id != other.preview_id
        assert first.source_record.record_kind == "ceqa"
        assert other.source_record.record_kind == "permit"
        assert first.source_record.provenance == _provenance()
        assert first.source_snapshot == _record("shared")
        assert first.read_only and not first.persisted and not first.commercial_lead_created
        assert not first.outreach_authorized and not first.bid_authorized
        assert len(first.normalized_source_sha256) == 64
        with pytest.raises(SourceRecordNotFound):
            build_source_candidate_preview(session, kind="ceqa", record_id="missing")
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    with _server(path) as port:
        status, _, body = _get(
            port, "/api/candidate-preview?kind=ceqa&record_id=shared"
        )
        assert status == 200
        payload = json.loads(body)
        assert payload["preview_id"] == first.preview_id
        assert payload["source_record"]["record_kind"] == "ceqa"
        assert payload["source_snapshot"]["ceqa_key"] == "shared"
        assert payload["source_snapshot"]["site"]["provenance"][0]["source_name"] == (
            "Synthetic integration fixture"
        )
        assert _get(port, "/api/candidate-preview?kind=permit&record_id=shared")[0] == 200
        assert _get(port, "/api/candidate-preview?kind=ceqa&record_id=missing")[0] == 404
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_candidate_review_holds_missing_provenance_scope_and_conflicting_county(database):
    _, engine = database
    with Session(engine) as session, session.begin():
        CeqaStore(session).upsert(_record("no-evidence", provenance=[]))
        CeqaStore(session).upsert(_record("out-of-scope", county="Orange", site=None))
        CeqaStore(session).upsert(_record(
            "county-conflict", county="Riverside",
            site=Site(site_key="conflict-site", county="San Bernardino",
                      provenance=_provenance()),
        ))
    with Session(engine) as session:
        for key, check_name in [
            ("no-evidence", "provenance"),
            ("out-of-scope", "county"),
            ("county-conflict", "county"),
        ]:
            item = build_source_candidate_preview(
                session, kind="ceqa", record_id=key
            )
            assert item.state == "hold"
            assert any(
                check.key == check_name
                and check.state in {"missing", "conflict", "out_of_scope"}
                for check in item.checks
            )


def test_candidate_preview_content_digest_changes_without_renaming_source(database):
    _, engine = database
    with Session(engine) as session, session.begin():
        CeqaStore(session).upsert(_record("amended"))
    with Session(engine) as session:
        original = build_source_candidate_preview(
            session, kind="ceqa", record_id="amended"
        )
    with Session(engine) as session, session.begin():
        CeqaStore(session).upsert(_record("amended", description="Updated source text"))
    with Session(engine) as session:
        revised = build_source_candidate_preview(
            session, kind="ceqa", record_id="amended"
        )
    assert original.candidate_key == revised.candidate_key
    assert original.preview_id != revised.preview_id
    assert original.normalized_source_sha256 != revised.normalized_source_sha256


@pytest.mark.parametrize("query", [
    "", "kind=all&record_id=x", "kind=ceqa", "kind=ceqa&record_id=",
    "kind=ceqa&record_id=x&q=broad", "kind=ceqa&record_id=x&limit=2",
    "kind=ceqa&record_id=x&record_id=x", "kind=ceqa&record_id=%20x",
    "kind=ceqa&record_id=x%0A", "kind=ceqa&record_id=" + "x" * 256,
])
def test_candidate_preview_rejects_broad_or_ambiguous_http_parameters(database, query):
    path, _ = database
    with _server(path) as port:
        assert _get(port, "/api/candidate-preview?" + query)[0] == 400



def test_candidate_preview_reinspect_after_projected_source_evidence_change(database):
    path, engine = database
    with Session(engine) as session, session.begin():
        CeqaStore(session).upsert(_record("fixture:stale-display"))
    with _server(path) as port:
        first = json.loads(
            _get(port, "/api/snapshot?kind=ceqa")[2]
        )["projects"][0]
    with Session(engine) as session, session.begin():
        CeqaStore(session).upsert(
            _record(
                "fixture:stale-display",
                description="Newly amended source evidence after snapshot render.",
            )
        )
    with _server(path) as port:
        current = json.loads(
            _get(
                port,
                "/api/candidate-preview?kind=ceqa&record_id=fixture%3Astale-display",
            )[2]
        )["source_record"]
    assert current["record_id"] == first["record_id"]
    assert current["description"] != first["description"]
    assert current != first


def test_retained_source_pulse_ui_binds_to_bounded_read_models(database):
    """The UI must identify scan coverage instead of inventing live project totals."""

    path, engine = database
    with Session(engine) as session, session.begin():
        CeqaStore(session).upsert(_record("pulse:synthetic"))
    with _server(path) as port:
        html_status, _, html_body = _get(port, "/")
        script_status, _, script_body = _get(port, "/operator_ui.js")
        page = json.loads(_get(port, "/api/snapshot?kind=all")[2])
        footprint = json.loads(_get(port, "/api/footprint?kind=all")[2])
    assert html_status == script_status == 200
    html = html_body.decode("utf-8")
    script = script_body.decode("utf-8")
    for element_id in (
        "pulse", "pulse-matching", "pulse-mapped", "pulse-unmapped",
        "pulse-scan", "pulse-scan-note",
    ):
        assert f'id="{element_id}"' in html
    assert "Source records, not deduplicated projects or qualified leads" in html
    assert "Source-claimed coordinates only" in html
    assert "not an absence of activity" in html
    assert "No street or county boundary layer" in html
    assert "mapData.mapped_in_scan" in script
    assert "mapData.records_scanned - mapData.mapped_in_scan" in script
    assert "data.total !== mapData.matching_total" in script
    assert "mapData.truncated" in script
    assert "const shouldFit = scope !== lastLoadedScope;" in script
    assert "if (shouldFit) fitMap(); else renderMap();" in script
    assert page["total"] == footprint["matching_total"] == 1
    assert footprint["records_scanned"] == footprint["mapped_in_scan"] == 1
    assert footprint["truncated"] is False


def test_historical_timeline_preserves_family_dates_scope_and_unmapped_sources(database):
    """An undated record or missing coordinate never becomes a fabricated milestone."""

    path, engine = database
    with Session(engine) as session, session.begin():
        CeqaStore(session).upsert(
            _record(
                "timeline:ceqa",
                received_date=date(2025, 1, 3),
                posted_date=date(2025, 1, 5),
            )
        )
        CeqaStore(session).upsert(_record("timeline:undated", county="Riverside"))
        PermitStore(session).upsert(
            PermitRecord(
                permit_key="timeline:permit",
                permit_number="TEST-TIMELINE",
                jurisdiction="Fontana",
                county="San Bernardino",
                applied_date=date(2025, 2, 1),
                issued_date=date(2025, 2, 8),
                status="Issued",
                provenance=_provenance(),
            )
        )
    with Session(engine) as session:
        result = build_historical_timeline(session, county="San Bernardino")
        assert result.matching_total == result.records_scanned == 2
        assert result.dated_records_in_scan == 2
        assert result.milestones_in_scan == result.returned_events == 4
        assert [event.event_kind for event in result.events] == [
            "permit_issued", "permit_applied", "ceqa_posted", "ceqa_received"
        ]
        assert [(event.record_kind, event.record_id) for event in result.events] == [
            ("permit", "timeline:permit"), ("permit", "timeline:permit"),
            ("ceqa", "timeline:ceqa"), ("ceqa", "timeline:ceqa")
        ]
        assert [event.classification for event in result.events] == [
            "source_claimed"
        ] * 4
        assert result.source_scan_truncated is False
        assert result.event_result_truncated is False
        assert build_historical_timeline(session, kind="permit", county="Riverside").events == []
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    with _server(path) as port:
        response = _get(port, "/api/timeline?kind=all&county=San+Bernardino")
        html = _get(port, "/")[2].decode("utf-8")
        script = _get(port, "/operator_ui.js")[2].decode("utf-8")
    assert response[0] == 200
    data = json.loads(response[2])
    assert data["matching_total"] == 2
    assert data["events"][0]["recorded_date"] == "2025-02-08"
    assert data["events"][0]["classification"] == "source_claimed"
    assert data["read_only"] is True and data["live_collection_enabled"] is False
    assert 'id="timeline-card"' in html
    assert 'id="timeline-warning"' in html
    assert "/api/timeline?" in script and "data-timeline-index" in script
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_historical_timeline_explicitly_discloses_scan_and_event_caps(database, monkeypatch):
    monkeypatch.setattr("constructionsight.operator_dashboard.TIMELINE_SCAN_LIMIT", 2)
    monkeypatch.setattr("constructionsight.operator_dashboard.TIMELINE_RESULT_LIMIT", 1)
    _, engine = database
    with Session(engine) as session, session.begin():
        for index in range(3):
            CeqaStore(session).upsert(
                _record(
                    f"timeline:cap:{index}",
                    received_date=date(2025, 1, index + 1),
                    posted_date=date(2025, 2, index + 1),
                )
            )
    with Session(engine) as session:
        result = build_historical_timeline(session)
    assert result.matching_total == 3 and result.records_scanned == 2
    assert result.dated_records_in_scan == 2
    assert result.milestones_in_scan == 4
    assert result.returned_events == 1
    assert result.source_scan_truncated is True
    assert result.event_result_truncated is True
    assert result.events[0].recorded_date == date(2025, 2, 2)
    assert result.events[0].record_id == "timeline:cap:1"


@pytest.mark.parametrize("query", [
    "kind=unknown", "limit=1", "offset=2", "county=Orange",
    "q=" + "x" * 201, "kind=permit&kind=permit",
])
def test_historical_timeline_rejects_extra_or_invalid_parameters(database, query):
    path, _ = database
    with _server(path) as port:
        assert _get(port, "/api/timeline?" + query)[0] == 400


def test_exact_entity_key_history_across_source_families_preserves_distinct_identity(database):
    """Same names are not a join; dated history attaches to exact stored keys only."""

    path, engine = database
    same_name_different_key = Entity(
        entity_key="fixture:other-key",
        name="Fixture Builder",
        role="contractor",
        provenance=_provenance(),
    )
    with Session(engine) as session, session.begin():
        CeqaStore(session).upsert(
            _record(
                "entity-history:ceqa",
                received_date=date(2025, 1, 1),
                posted_date=date(2025, 1, 3),
            )
        )
        CeqaStore(session).upsert(
            _record(
                "entity-history:false-name",
                entities=[same_name_different_key],
                received_date=date(2025, 1, 5),
            )
        )
        PermitStore(session).upsert(
            PermitRecord(
                permit_key="entity-history:permit",
                permit_number="HISTORY",
                jurisdiction="Fontana",
                county="San Bernardino",
                status="Issued",
                applied_date=date(2025, 2, 1),
                issued_date=date(2025, 2, 2),
                entities=[
                    Entity(
                        entity_key="fixture:party",
                        name="Fixture Builder",
                        role="contractor",
                        provenance=_provenance(),
                    )
                ],
                provenance=_provenance(),
            )
        )
    with Session(engine) as session:
        result = build_historical_timeline(session, entity_key="fixture:party")
        assert result.entity_key == "fixture:party"
        assert result.matching_total == result.records_scanned == 3
        assert result.matching_entity_records_in_scan == 2
        assert result.milestones_in_scan == 4
        assert {event.record_id for event in result.events} == {
            "entity-history:ceqa", "entity-history:permit"
        }
        assert [event.event_kind for event in result.events] == [
            "permit_issued", "permit_applied", "ceqa_posted", "ceqa_received"
        ]
        other = build_historical_timeline(session, entity_key="fixture:other-key")
        assert [event.record_id for event in other.events] == [
            "entity-history:false-name"
        ]
        assert other.matching_entity_records_in_scan == 1
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    with _server(path) as port:
        response = _get(
            port,
            "/api/timeline?kind=all&entity_key=fixture%3Aparty&county=San+Bernardino",
        )
        script = _get(port, "/operator_ui.js")[2].decode("utf-8")
    assert response[0] == 200
    payload = json.loads(response[2])
    assert payload["entity_key"] == "fixture:party"
    assert payload["matching_entity_records_in_scan"] == 2
    assert len(payload["events"]) == 4
    assert "history.matching_total !== data.total_source_records" in script
    assert "Historical source events for this exact key" in script
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_exact_entity_history_retains_global_source_scan_cap(database, monkeypatch):
    monkeypatch.setattr("constructionsight.operator_dashboard.TIMELINE_SCAN_LIMIT", 1)
    _, engine = database
    with Session(engine) as session, session.begin():
        CeqaStore(session).upsert(
            _record(
                "entity-history:first",
                entities=[Entity(
                    entity_key="fixture:other",
                    name="Fixture Builder",
                    role="contractor",
                    provenance=_provenance(),
                )],
                received_date=date(2025, 1, 1),
            )
        )
        CeqaStore(session).upsert(
            _record("entity-history:second", received_date=date(2025, 2, 2))
        )
    with Session(engine) as session:
        result = build_historical_timeline(session, entity_key="fixture:party")
    assert result.matching_total == 2 and result.records_scanned == 1
    assert result.matching_entity_records_in_scan == 0
    assert result.events == []
    assert result.source_scan_truncated is True


@pytest.mark.parametrize("query", [
    "kind=ceqa&entity_key=",
    "kind=ceqa&entity_key=%20fixture",
    "kind=ceqa&entity_key=fixture%0A",
    "kind=ceqa&entity_key=a&entity_key=b",
    "kind=ceqa&entity_key=" + "x" * 256,
])
def test_exact_entity_history_denies_invalid_or_repeated_identity(database, query):
    path, _ = database
    with _server(path) as port:
        assert _get(port, "/api/timeline?" + query)[0] == 400


def _parcel_claim(
    record_id: str,
    *,
    county: str = "San Bernardino",
    apn: str = "123-456-789",
    crs: str = "EPSG:4326",
) -> ParcelCoreRecord:
    return ParcelCoreRecord(
        parcel_record_id=record_id,
        source_key="fixture:assessor",
        source_record_id=record_id,
        apn=apn,
        normalized_apn="".join(char for char in apn if char.isdigit()),
        county=county,
        state="CA",
        address="123 Synthetic Ave",
        normalized_address="123 SYNTHETIC AVE",
        geometry=ParcelGeometry(
            geometry_kind=ParcelGeometryKind.POINT,
            centroid_latitude=34.05,
            centroid_longitude=-117.6,
            spatial_reference=crs,
        ),
        limitations=["Synthetic fixture; not a surveyed or verified location."],
    )


def test_on_demand_parcel_claims_exact_source_apn_county_and_crs(database):
    path, engine = database
    source = _record(
        "parcel-source:ceqa",
        site=Site(
            site_key="parcel-source:site",
            county="San Bernardino",
            apn="123-456-789",
            latitude=34.05,
            longitude=-117.6,
            provenance=_provenance(),
        ),
    )
    with Session(engine) as session, session.begin():
        CeqaStore(session).upsert(source)
        for parcel in [
            _parcel_claim("parcel:matched:geodetic"),
            _parcel_claim("parcel:matched:projected", crs="EPSG:3857"),
            _parcel_claim("parcel:different-county", county="Riverside"),
            _parcel_claim("parcel:different-apn", apn="987-654-321"),
        ]:
            store_parcel_core_record(session, parcel)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    with _server(path) as port:
        status, _, body = _get(
            port, "/api/parcel-candidates?kind=ceqa&record_id=parcel-source%3Aceqa"
        )
        html = _get(port, "/")[2].decode("utf-8")
        script = _get(port, "/operator_ui.js")[2].decode("utf-8")
    assert status == 200
    payload = json.loads(body)
    assert payload["source_kind"] == "ceqa"
    assert payload["source_record_id"] == "parcel-source:ceqa"
    assert payload["source_apn"] == "123-456-789"
    assert payload["normalized_apn"] == "123456789"
    assert payload["matching_total"] == payload["returned"] == 2
    assert payload["truncated"] is False
    assert payload["read_only"] is True
    assert payload["linked_site_verified"] is False
    assert payload["parcel_boundaries_rendered"] is False
    assert [p["parcel_record_id"] for p in payload["matches"]] == [
        "parcel:matched:geodetic", "parcel:matched:projected"
    ]
    assert payload["matches"][0]["point"] == {
        "latitude": 34.05,
        "longitude": -117.6,
        "classification": "source_claimed_centroid",
    }
    assert payload["matches"][1]["point"] is None
    assert "projected CRS" in payload["matches"][1]["map_reason"]
    assert all("raw_geometry" not in match for match in payload["matches"])
    assert 'id="inspect-parcels"' in script
    assert "/api/parcel-candidates?" in script
    assert "parcelOverlay = []" in script
    assert "legend-parcel" in html
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_parcel_lookup_requires_record_apn_and_consistent_target_county(database):
    path, engine = database
    with Session(engine) as session, session.begin():
        CeqaStore(session).upsert(_record("parcel:no-site", site=None))
        CeqaStore(session).upsert(
            _record(
                "parcel:county-mismatch",
                site=Site(
                    site_key="parcel:county-site",
                    county="Riverside",
                    apn="123-456-789",
                    provenance=_provenance(),
                ),
            )
        )
        store_parcel_core_record(session, _parcel_claim("parcel:stored"))
    with _server(path) as port:
        for record_id in ("parcel:no-site", "parcel:county-mismatch"):
            status, _, body = _get(
                port, "/api/parcel-candidates?kind=ceqa&record_id=" + record_id
            )
            assert status == 200
            response = json.loads(body)
            assert response["matches"] == [] and response["matching_total"] == 0
            assert response["limitations"]
        assert _get(
            port, "/api/parcel-candidates?kind=permit&record_id=missing"
        )[0] == 404


@pytest.mark.parametrize("query", [
    "", "kind=all&record_id=x", "kind=ceqa",
    "kind=ceqa&record_id=", "kind=ceqa&record_id=x&county=Riverside",
    "kind=ceqa&record_id=x&entity_key=e", "kind=ceqa&record_id=x&limit=2",
    "kind=ceqa&record_id=x&record_id=y",
    "kind=ceqa&record_id=%20x", "kind=ceqa&record_id=x%0A",
    "kind=ceqa&record_id=" + "x" * 256,
])
def test_parcel_http_inspection_rejects_nonexact_requests(database, query):
    path, _ = database
    with _server(path) as port:
        assert _get(port, "/api/parcel-candidates?" + query)[0] == 400


def test_parcel_lookup_fails_closed_on_index_payload_geometry_drift(database):
    path, engine = database
    with Session(engine) as session, session.begin():
        CeqaStore(session).upsert(
            _record(
                "parcel:drift-source",
                site=Site(
                    site_key="parcel:drift-site",
                    county="San Bernardino",
                    apn="123-456-789",
                    provenance=_provenance(),
                ),
            )
        )
        store_parcel_core_record(session, _parcel_claim("parcel:drift"))
    with Session(engine) as session, session.begin():
        row = session.scalar(
            select(ParcelCoreRecordRow).where(
                ParcelCoreRecordRow.parcel_record_id == "parcel:drift"
            )
        )
        assert row is not None
        row.centroid_longitude = -118.8
    with _server(path) as port:
        status, _, body = _get(
            port, "/api/parcel-candidates?kind=ceqa&record_id=parcel%3Adrift-source"
        )
    assert status == 503
    assert "parcel:drift" not in body.decode("utf-8")


def test_parcel_lookup_reports_bounded_candidate_results(database, monkeypatch):
    monkeypatch.setattr(
        "constructionsight.operator_parcel_candidates.PARCEL_CANDIDATE_LIMIT", 2
    )
    path, engine = database
    with Session(engine) as session, session.begin():
        CeqaStore(session).upsert(
            _record(
                "parcel:cap-source",
                site=Site(
                    site_key="parcel:cap-site",
                    county="San Bernardino",
                    apn="123-456-789",
                    provenance=_provenance(),
                ),
            )
        )
        for index in range(3):
            store_parcel_core_record(
                session, _parcel_claim(f"parcel:cap:{index}")
            )
    with _server(path) as port:
        status, _, body = _get(
            port, "/api/parcel-candidates?kind=ceqa&record_id=parcel%3Acap-source"
        )
    assert status == 200
    payload = json.loads(body)
    assert payload["matching_total"] == 3 and payload["returned"] == 2
    assert payload["result_limit"] == 2 and payload["truncated"] is True


def test_explicit_desktop_launch_opens_only_bound_loopback_url(monkeypatch, tmp_path):
    import sys

    observed = []
    class StubServer:
        server_address = ("127.0.0.1", 9927)

        def __init__(self, address, handler):
            observed.append(("bind", address))
            assert handler is not None

        def __enter__(self):
            return self

        def __exit__(self, *arguments):
            return False

        def serve_forever(self):
            observed.append(("serve", None))

    class StubTimer:
        daemon = False

        def __init__(self, seconds, callback, *, args):
            assert seconds >= 0
            self.callback = callback
            self.arguments = args

        def start(self):
            observed.append(("timer_daemon", self.daemon))
            self.callback(*self.arguments)

    monkeypatch.setattr(operator_web, "create_handler", lambda path: object())
    monkeypatch.setattr(operator_web, "ThreadingHTTPServer", StubServer)
    monkeypatch.setattr(operator_web, "Timer", StubTimer)
    monkeypatch.setattr(
        operator_web.webbrowser, "open",
        lambda url: observed.append(("open", url)),
    )
    database = tmp_path / "synthetic.sqlite3"
    monkeypatch.setattr(
        sys, "argv",
        ["constructionsight-desktop", "--database", str(database), "--port", "9927"],
    )
    operator_web.desktop_main()
    assert observed == [
        ("bind", ("127.0.0.1", 9927)),
        ("timer_daemon", True),
        ("open", "http://127.0.0.1:9927"),
        ("serve", None),
    ]
    observed.clear()
    monkeypatch.setattr(
        sys, "argv",
        ["constructionsight-operator", "--database", str(database), "--port", "9927"],
    )
    operator_web.main()
    assert observed == [
        ("bind", ("127.0.0.1", 9927)),
        ("serve", None),
    ]
    project = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    assert (
        'constructionsight-desktop = "constructionsight.operator_web:desktop_main"'
        in project
    )


def test_command_center_off_page_map_to_exact_evidence_and_entity_http(database):
    """A mapped source beyond page one resolves to the same exact read-only evidence."""
    path, engine = database
    with Session(engine) as session, session.begin():
        for index in range(57):
            CeqaStore(session).upsert(_record(f"mapped:{index:03d}"))
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    with _server(path) as port:
        status, _, raw = _get(port, "/api/footprint?kind=all")
        assert status == 200
        footprint = json.loads(raw)
        assert footprint["matching_total"] == 57
        assert footprint["mapped_in_scan"] == 57
        target = next(point for point in footprint["points"] if point["ordinal"] == 52)
        offset = (target["ordinal"] // 50) * 50
        status, _, raw = _get(
            port, f"/api/snapshot?kind=all&limit=50&offset={offset}"
        )
        assert status == 200
        page = json.loads(raw)
        assert page["total"] == footprint["matching_total"]
        source = page["projects"][target["ordinal"] - page["offset"]]
        assert (source["record_kind"], source["record_id"]) == (
            target["record_kind"], target["record_id"]
        )
        selection = f"kind=ceqa&record_id={source['record_id']}"
        status, _, raw = _get(port, "/api/candidate-preview?" + selection)
        assert status == 200
        preview = json.loads(raw)
        assert preview["source_record"] == source
        assert preview["read_only"] and not preview["persisted"]
        assert not preview["commercial_lead_created"]
        assert not preview["outreach_authorized"] and not preview["bid_authorized"]
        assert preview["source_snapshot"]["provenance"]
        status, _, raw = _get(port, "/api/parcel-candidates?" + selection)
        assert status == 200
        parcel_candidates = json.loads(raw)
        assert parcel_candidates["source_kind"] == source["record_kind"]
        assert parcel_candidates["source_record_id"] == source["record_id"]
        assert parcel_candidates["read_only"]
        assert not parcel_candidates["linked_site_verified"]
        assert not parcel_candidates["parcel_boundaries_rendered"]
        status, _, raw = _get(
            port, "/api/entity-neighborhood?kind=all&entity_key=fixture%3Aparty"
        )
        assert status == 200
        neighbors = json.loads(raw)
        assert neighbors["entity_key"] == "fixture:party"
        assert neighbors["matching_records_in_scan"] == 57
        assert any(
            (item["record_kind"], item["record_id"]) ==
            (target["record_kind"], target["record_id"])
            for item in neighbors["records"]
        )
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_command_center_status_kpis_count_only_persisted_workflows(database):
    """Source records remain unassessed even when distinct persisted workflows exist."""
    path, engine = database
    with Session(engine) as session, session.begin():
        CeqaStore(session).upsert(_record("unreviewed-source"))
        store_lead_review_package(
            session,
            LeadReviewPackage(
                package_id="review:status-counters",
                base_candidate_id="candidate:status-counters",
                lead_score=50,
                status=LeadReviewStatus.MONITOR,
                summary="Synthetic workflow aggregation fixture",
                evidence_notes=["Synthetic, not authorized outreach"],
            ),
        )
        for index, status in enumerate(
            (
                LeadWorkflowStatus.READY,
                LeadWorkflowStatus.REVIEW,
                LeadWorkflowStatus.HOLD,
                LeadWorkflowStatus.MONITOR,
            )
        ):
            store_lead_workflow_record(
                session,
                LeadWorkflowRecord(
                    workflow_id=f"workflow:status-{index}",
                    package_id="review:status-counters",
                    base_candidate_id="candidate:status-counters",
                    status=status,
                    lead_score=50,
                ),
            )
    with Session(engine) as session:
        summary = build_workflow_status_summary(session)
        assert summary["total"] == 4
        assert summary["statuses"]["ready"] == 1
        assert summary["statuses"]["review"] == 1
        assert summary["statuses"]["hold"] == 1
        assert summary["statuses"]["monitor"] == 1
        assert summary["unclassified"] == 0
        assert summary["read_only"] and summary["outreach_authorized"] is False
        assert build_dashboard_snapshot(session).total == 1
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    with _server(path) as port:
        status, _, raw = _get(port, "/api/workflow-summary")
        assert status == 200
        payload = json.loads(raw)
        assert payload == summary
        assert _get(port, "/api/workflow-summary?kind=all")[0] == 400
        assert _get(port, "/api/workflow-summary?limit=1")[0] == 400
        assert _get(port, "/api/snapshot?kind=all")[0] == 200
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
