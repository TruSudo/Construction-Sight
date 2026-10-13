"""SMARTS private-source -> retained parcel candidate review, never a project join."""

from __future__ import annotations

import csv
import io
import json
import sqlite3
from contextlib import contextmanager
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest
from sqlalchemy.orm import Session

from constructionsight.operator_web import create_handler
from constructionsight.parcel_core_models import ParcelCoreRecord
from constructionsight.smarts_parcel_review import inspect_smarts_parcel_candidates
from constructionsight.smarts_snapshot_history import (
    SmartsHistoryError,
    append_snapshot,
)
from constructionsight.storage.database import create_database_engine, initialize_database
from constructionsight.storage.parcel_site_store import store_parcel_core_record

_FIELDS = ("_id", "APP_ID", "WDID", "SITE_COUNTY", "STATUS", "SITE_APN", "APN", "EMAIL")
_KEY = "smarts:facility:Riverside:wdid:8 33C101"


def _csv(path: Path, rows: list[tuple[str, ...]]) -> Path:
    out = io.StringIO(newline="")
    writer = csv.writer(out)
    writer.writerow(_FIELDS)
    writer.writerows(rows)
    path.write_text(out.getvalue(), encoding="utf-8")
    path.chmod(0o600)
    return path


def _row(
    app: str, *, status: str = "Active", apn: str = "", other_apn: str = "",
    county: str = "Riverside",
) -> tuple[str, ...]:
    return ("1", app, "8 33C" + app, county, status, apn, other_apn, "secret@example.test")


def _environment(tmp_path: Path) -> tuple[Path, Path, Path]:
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    db = tmp_path / "operator.sqlite3"
    engine = create_database_engine(f"sqlite:///{db}")
    initialize_database(engine)
    engine.dispose()
    return private, private / "smarts-history.sqlite3", db


def _change(
    private: Path, journal: Path, *, apn: str = "123-456-789",
    other_apn: str = "", status: str = "Terminated",
) -> int:
    base = _csv(private / "old.csv", [_row("999")])
    current = _csv(
        private / "current.csv",
        [_row("101", apn=apn, other_apn=other_apn, status=status)],
    )
    append_snapshot(ledger_path=journal, csv_path=base, county="Riverside")
    result = append_snapshot(ledger_path=journal, csv_path=current, county="Riverside")
    assert result.new == 1
    return result.snapshot_id


def _parcel(db: Path, record_id: str, *, county: str = "Riverside", apn: str = "123-456-789") -> None:
    engine = create_database_engine(f"sqlite:///{db}")
    try:
        with Session(engine) as session, session.begin():
            store_parcel_core_record(
                session,
                ParcelCoreRecord(
                    parcel_record_id=record_id, source_key="county_assessor",
                    source_record_id=record_id, apn=apn,
                    normalized_apn="".join(ch for ch in apn if ch.isdigit()),
                    county=county, state="CA",
                ),
            )
    finally:
        engine.dispose()


def _inspect(db: Path, journal: Path, snapshot_id: int) -> dict[str, object]:
    engine = create_database_engine(f"sqlite:///{db}")
    try:
        with Session(engine) as session:
            return inspect_smarts_parcel_candidates(
                session, history_path=journal,
                snapshot_id=snapshot_id, source_key=_KEY,
            )
    finally:
        engine.dispose()


def test_same_county_exact_apn_remains_review_only(tmp_path: Path) -> None:
    root, journal, db = _environment(tmp_path)
    snapshot_id = _change(root, journal)
    _parcel(db, "parcel:riverside:one")
    _parcel(db, "parcel:sanbernardino:other", county="San Bernardino")
    found = _inspect(db, journal, snapshot_id)
    assert found["status"] == "parcel_candidate_requires_review"
    assert found["source_claimed_normalized_apn"] == "123456789"
    assert found["candidate_total"] == 1
    assert found["candidates"] == [{
        "parcel_record_id": "parcel:riverside:one",
        "parcel_source_key": "county_assessor",
        "parcel_source_record_id": "parcel:riverside:one",
        "candidate_basis": "same_county_exact_normalized_apn",
    }]
    for field in (
        "parcel_identity_verified", "project_identity_verified",
        "construction_activity_verified", "lead_created",
        "outreach_authorized", "bid_authorized",
    ):
        assert found[field] is False
    assert "secret@example.test" not in json.dumps(found)


def test_missing_conflicting_and_invalid_source_apn_fail_closed(tmp_path: Path) -> None:
    for index, (apn, extra, expected) in enumerate((
        ("", "", "source_apn_missing"),
        ("123-456-789", "999-888-777", "conflicting_source_apns"),
        ("12345;678", "", "unusable_source_apn"),
        ("000-000-000", "", "unusable_source_apn"),
    )):
        root, journal, db = _environment(tmp_path / f"example{index}")
        snapshot_id = _change(root, journal, apn=apn, other_apn=extra)
        _parcel(db, "parcel:matched")
        result = _inspect(db, journal, snapshot_id)
        assert result["status"] == expected
        assert result["candidate_total"] == 0
        assert result["candidates"] == []
        assert result["parcel_identity_verified"] is False


def test_ambiguous_parcel_sources_never_choose_a_winner(tmp_path: Path) -> None:
    root, journal, db = _environment(tmp_path)
    snapshot_id = _change(root, journal)
    _parcel(db, "parcel:assessor:a")
    _parcel(db, "parcel:gis:b")
    result = _inspect(db, journal, snapshot_id)
    assert result["status"] == "parcel_candidate_ambiguous"
    assert result["candidate_total"] == 2
    assert result["returned"] == 2
    assert result["project_identity_verified"] is False


def test_stale_snapshots_and_missing_source_rows_cannot_be_promoted(tmp_path: Path) -> None:
    root, journal, db = _environment(tmp_path)
    snapshot_id = _change(root, journal)
    _parcel(db, "parcel:assessor:a")
    missing = _csv(root / "missing.csv", [_row("999", status="Not Active")])
    next_receipt = append_snapshot(
        ledger_path=journal, csv_path=missing, county="Riverside"
    )
    assert _inspect(db, journal, snapshot_id)["status"] == (
        "historical_snapshot_requires_current_review"
    )
    absent = inspect_smarts_parcel_candidates
    engine = create_database_engine(f"sqlite:///{db}")
    try:
        with Session(engine) as session:
            result = absent(
                session, history_path=journal,
                snapshot_id=next_receipt.snapshot_id, source_key=_KEY,
            )
    finally:
        engine.dispose()
    assert result["status"] == "missing_from_new_is_not_deletion"
    assert result["candidate_total"] == 0


def test_tampered_parcel_index_does_not_claim_apn_candidate(tmp_path: Path) -> None:
    root, journal, db = _environment(tmp_path)
    snapshot_id = _change(root, journal)
    _parcel(db, "parcel:assessor:a")
    with sqlite3.connect(db) as con:
        con.execute(
            "UPDATE parcel_core_records SET apn=? WHERE parcel_record_id=?",
            ("999-888-777", "parcel:assessor:a"),
        )
    with pytest.raises(ValueError, match="index"):
        _inspect(db, journal, snapshot_id)


def test_missing_source_evidence_and_invalid_selection_fail_closed(tmp_path: Path) -> None:
    root, journal, db = _environment(tmp_path)
    snapshot_id = _change(root, journal)
    with pytest.raises(SmartsHistoryError):
        _inspect(db, root / "absent.sqlite3", snapshot_id)
    engine = create_database_engine(f"sqlite:///{db}")
    try:
        with Session(engine) as session:
            for bad in (0, -1, True, 2147483648):
                with pytest.raises(ValueError):
                    inspect_smarts_parcel_candidates(
                        session, history_path=journal,
                        snapshot_id=bad, source_key=_KEY,
                    )
            with pytest.raises(ValueError):
                inspect_smarts_parcel_candidates(
                    session, history_path=journal, snapshot_id=snapshot_id,
                    source_key="not a SMARTS source",
                )
    finally:
        engine.dispose()


@contextmanager
def _http(database: Path, history_path: Path):
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        create_handler(database, smarts_snapshot_history_path=history_path),
    )
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _get(port: int, query: str) -> tuple[int, dict[str, object]]:
    connection = HTTPConnection("127.0.0.1", port, timeout=3)
    try:
        connection.request(
            "GET", "/api/smarts-parcel-candidates?" + query,
            headers={"Host": f"127.0.0.1:{port}"},
        )
        response = connection.getresponse()
        return response.status, json.loads(response.read())
    finally:
        connection.close()


def test_real_local_http_endpoint_is_bounded_and_read_only(tmp_path: Path) -> None:
    root, journal, db = _environment(tmp_path)
    snapshot_id = _change(root, journal)
    _parcel(db, "parcel:assessor:a")
    with _http(db, journal) as port:
        status, data = _get(
            port, f"snapshot_id={snapshot_id}&source_key=smarts%3Afacility%3A"
            "Riverside%3Awdid%3A8+33C101",
        )
        assert status == 200
        assert data["candidate_total"] == 1
        assert data["read_only"] is True
        assert data["outreach_authorized"] is False
        assert "secret@example.test" not in json.dumps(data)
        for query in ("", "snapshot_id=2", "source_key=hello",
                      "snapshot_id=1&source_key=x&county=Riverside",
                      "snapshot_id=1&snapshot_id=1&source_key=x"):
            assert _get(port, query)[0] == 400
