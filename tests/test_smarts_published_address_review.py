"""Real published SMARTS facility-schema address discovery is review-only."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from constructionsight.parcel_core_models import ParcelCoreRecord
from constructionsight.site_resolution_service import normalize_address
from constructionsight.smarts_parcel_review import inspect_smarts_parcel_candidates
from constructionsight.smarts_snapshot_history import append_snapshot
from constructionsight.storage.database import create_database_engine, initialize_database
from constructionsight.storage.parcel_site_store import store_parcel_core_record

_FIELDS = (
    "_id", "APP_ID", "WDID", "SITE_COUNTY", "SITE_STATE", "SITE_CITY",
    "SITE_ADDRESS", "SITE_ADDRESS_2", "STATUS", "DEVELOPER_EMAIL",
)
_KEY = "smarts:facility:Riverside:wdid:8 33C101"


def _csv(path: Path, rows: list[tuple[str, ...]]) -> Path:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(_FIELDS)
    writer.writerows(rows)
    path.write_text(buffer.getvalue(), encoding="utf-8")
    path.chmod(0o600)
    return path


def _row(
    app: str, *, city: str = "Riverside", address: str = "123 Main Street",
    state: str = "CA", address_2: str = "", status: str = "Active",
) -> tuple[str, ...]:
    return (
        "1", app, "8 33C" + app, "Riverside", state, city,
        address, address_2, status, "private@example.test",
    )


def _setup(tmp_path: Path, **kwargs: str) -> tuple[Path, Path, int]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    folder = tmp_path / "private"
    folder.mkdir(mode=0o700)
    journal = folder / "history.sqlite3"
    previous = _csv(folder / "old.csv", [_row("999")])
    latest = _csv(folder / "new.csv", [_row("101", status="Terminated", **kwargs)])
    append_snapshot(ledger_path=journal, csv_path=previous, county="Riverside")
    event = append_snapshot(ledger_path=journal, csv_path=latest, county="Riverside")
    db = tmp_path / "operator.sqlite3"
    engine = create_database_engine(f"sqlite:///{db}")
    initialize_database(engine)
    engine.dispose()
    return db, journal, event.snapshot_id


def _parcel(
    db: Path, *, record_id: str, county: str = "Riverside",
    address: str = "123 Main Street", city: str | None = "Riverside",
) -> None:
    engine = create_database_engine(f"sqlite:///{db}")
    try:
        with Session(engine) as session, session.begin():
            store_parcel_core_record(
                session,
                ParcelCoreRecord(
                    parcel_record_id=record_id, source_key="county_gis",
                    source_record_id=record_id, apn="123-456-789",
                    normalized_apn="123456789", county=county,
                    state="CA", address=address,
                    normalized_address=normalize_address(address),
                    jurisdiction=city,
                ),
            )
    finally:
        engine.dispose()


def _review(db: Path, journal: Path, snapshot_id: int) -> dict[str, object]:
    engine = create_database_engine(f"sqlite:///{db}")
    try:
        with Session(engine) as session:
            return inspect_smarts_parcel_candidates(
                session, history_path=journal, snapshot_id=snapshot_id, source_key=_KEY
            )
    finally:
        engine.dispose()


def test_published_fields_without_apn_produce_unverified_address_candidate(
    tmp_path: Path,
) -> None:
    db, journal, event = _setup(tmp_path)
    _parcel(db, record_id="riverside:parcel:one")
    result = _review(db, journal, event)
    assert result["status"] == "address_candidate_requires_review"
    assert result["source_claimed_normalized_apn"] is None
    assert result["source_claimed_normalized_address"] == "123 MAIN STREET"
    assert result["candidate_total"] == 1
    assert result["candidates"] == [
        {
            "parcel_record_id": "riverside:parcel:one",
            "parcel_source_key": "county_gis",
            "parcel_source_record_id": "riverside:parcel:one",
            "candidate_basis": "same_county_city_exact_source_claimed_site_address",
        }
    ]
    for key in (
        "parcel_identity_verified", "project_identity_verified",
        "construction_activity_verified", "lead_created",
        "outreach_authorized", "bid_authorized",
    ):
        assert result[key] is False
    assert "private@example.test" not in json.dumps(result)


def test_identical_addresses_in_other_counties_do_not_link(tmp_path: Path) -> None:
    db, journal, event = _setup(tmp_path)
    _parcel(db, record_id="san:parcel:one", county="San Bernardino")
    assert _review(db, journal, event)["status"] == "address_not_retained"


def test_wrong_city_or_missing_city_on_parcel_is_a_hold(tmp_path: Path) -> None:
    db, journal, event = _setup(tmp_path)
    _parcel(db, record_id="parcel:one", city="Corona")
    result = _review(db, journal, event)
    assert result["status"] == "address_city_conflict_requires_review"
    assert result["candidate_total"] == 0
    assert result["candidates"] == []


def test_same_address_multiple_retained_sources_remain_ambiguous(tmp_path: Path) -> None:
    db, journal, event = _setup(tmp_path)
    _parcel(db, record_id="gis:one")
    _parcel(db, record_id="assessor:two")
    result = _review(db, journal, event)
    assert result["status"] == "address_candidate_ambiguous"
    assert result["candidate_total"] == 2
    assert result["project_identity_verified"] is False


@pytest.mark.parametrize("kwargs", [
    {"address": "PO BOX 123"}, {"address": "MAIN AND 2ND"},
    {"address": ""}, {"city": ""}, {"state": "NV"},
    {"address_2": "Lot 12"}, {"address": "12"},
])
def test_inexact_or_unusable_published_location_is_not_linked(
    tmp_path: Path, kwargs: dict[str, str],
) -> None:
    db, journal, event = _setup(tmp_path, **kwargs)
    _parcel(db, record_id="parcel:one")
    assert _review(db, journal, event)["candidate_total"] == 0


def test_address_fallback_must_not_override_malformed_source_apn(tmp_path: Path) -> None:
    db, journal, event = _setup(tmp_path)
    _parcel(db, record_id="parcel:one")
    # This helper is independently tested; source APN inputs cause stricter
    # holds and must never be downgraded to a weaker address match.
    from constructionsight.smarts_parcel_review import _candidate_apn

    assert _candidate_apn({"APN": "123;invalid"}) == (None, "unusable_source_apn")
    assert _candidate_apn({"APN": "123456789", "SITE_APN": "987654321"}) == (
        None, "conflicting_source_apns"
    )
    assert _review(db, journal, event)["parcel_identity_verified"] is False
