"""Database-to-operator integration tests using explicitly synthetic records."""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from threading import Thread

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from constructionsight.ceqa_models import CeqaRecord
from constructionsight.ceqanet_persistence_preview import build_ceqanet_persistence_preview
from constructionsight.ceqanet_write_plan import build_ceqanet_write_plan
from constructionsight.entity_models import Entity
from constructionsight.lead_review_models import LeadReviewPackage, LeadReviewStatus
from constructionsight.lead_workflow_models import LeadWorkflowRecord, LeadWorkflowStatus
from constructionsight.operator_dashboard import build_dashboard_snapshot, build_workflow_snapshot
from constructionsight.operator_services.ceqanet_persistence_service import (
    execute_authorized_ceqanet_write_plan,
)
from constructionsight.operator_web import create_handler
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
