"""Read-only SMARTS-to-retained-parcel candidate inspection.

Only a selected, integrity-verified, current SMARTS CSV change observation
can suggest an exact county+APN candidate. This never joins on names, address,
or geolocation, never creates a site/project, and never authorizes outreach.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from constructionsight.parcel_core_models import ParcelCoreRecord
from constructionsight.site_resolution_service import normalize_apn
from constructionsight.smarts_snapshot_diff import COUNTIES, _source_id
from constructionsight.smarts_snapshot_history import SmartsHistoryError, _audit, _database
from constructionsight.storage.parcel_site_orm import ParcelCoreRecordRow

_APN_FIELDS = ("SITE_APN", "APN", "ASSESSOR_PARCEL_NUMBER")
_APN_PATTERN = re.compile(r"[0-9][0-9 -]{4,23}")
_SOURCE_KEY = re.compile(
    r"smarts:facility:(San Bernardino|Riverside):(wdid|app_id):[A-Za-z0-9 ]{1,32}"
)
_LIMIT = 20


def _candidate_apn(record: dict[str, str]) -> tuple[str | None, str]:
    """Return a single strictly recognizable parcel number or a review hold."""
    candidates: set[str] = set()
    seen = False
    for field in _APN_FIELDS:
        value = record.get(field, "").strip()
        if not value or value.upper() in {"NA", "N/A", "NONE", "NULL", "UNKNOWN"}:
            continue
        seen = True
        if not _APN_PATTERN.fullmatch(value):
            return None, "unusable_source_apn"
        normalized = normalize_apn(value)
        if not 5 <= len(normalized) <= 16 or not any(c != "0" for c in normalized):
            return None, "unusable_source_apn"
        candidates.add(normalized)
    if len(candidates) > 1:
        return None, "conflicting_source_apns"
    if not seen or not candidates:
        return None, "source_apn_missing"
    return next(iter(candidates)), "source_apn_claim_only"


def _read_source_apn(
    raw_csv: bytes, *, county: str, source_key: str, row_sha256: str,
) -> tuple[str | None, str]:
    """Inspect only fields explicitly bound to a verified source-row digest."""
    try:
        reader = csv.DictReader(io.StringIO(raw_csv.decode("utf-8-sig"), newline=""), strict=True)
        if reader.fieldnames is None:
            raise SmartsHistoryError("SMARTS snapshot header missing")
        found: dict[str, str] | None = None
        for record in reader:
            if record["SITE_COUNTY"] != county:
                continue
            wdid = _source_id(record["WDID"], kind="wdid")
            app_id = _source_id(record["APP_ID"], kind="app_id")
            key = (
                f"smarts:facility:{county}:wdid:{wdid}"
                if wdid is not None else f"smarts:facility:{county}:app_id:{app_id}"
            )
            if key != source_key:
                continue
            if found is not None:
                raise SmartsHistoryError("SMARTS source key duplicates within original snapshot")
            digest = hashlib.sha256(
                json.dumps(
                    {k: v for k, v in record.items() if k != "_id"},
                    sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                ).encode("utf-8")
            ).hexdigest()
            if digest != row_sha256:
                raise SmartsHistoryError("SMARTS record no longer matches verified source digest")
            found = record
    except (ValueError, KeyError, TypeError) as exc:
        raise SmartsHistoryError("SMARTS retained source row could not be validated") from exc
    if found is None:
        raise SmartsHistoryError("SMARTS source row is missing from selected snapshot")
    return _candidate_apn(found)


def _county(value: str) -> str:
    return value.strip().lower().removesuffix(" county")


def inspect_smarts_parcel_candidates(
    session: Session, *, history_path: Path | None, snapshot_id: int, source_key: str,
) -> dict[str, object]:
    """Inspect an exact change event against retained county+APN parcel records.

    Matching does not establish that a stormwater permit, parcel and physical
    construction site refer to the same development project.
    """
    if type(snapshot_id) is not int or snapshot_id <= 0 or snapshot_id > 2_147_483_647:
        raise ValueError("Invalid SMARTS snapshot identity")
    if (
        not isinstance(source_key, str) or len(source_key) > 100
        or not _SOURCE_KEY.fullmatch(source_key)
    ):
        raise ValueError("Invalid SMARTS source identity")
    if history_path is None:
        raise SmartsHistoryError("SMARTS history is not configured")
    connection = _database(history_path, read_only=True)
    try:
        history, _ = _audit(connection)
        selected = connection.execute(
            "SELECT s.county,s.file_sha256,e.outcome,e.current_sha256,b.raw_csv "
            "FROM snapshot_captures s "
            "JOIN snapshot_events e ON e.snapshot_id=s.id "
            "JOIN snapshot_blobs b ON b.sha256=s.file_sha256 "
            "WHERE s.id=? AND e.source_key=?", (snapshot_id, source_key),
        ).fetchone()
        if selected is None:
            raise SmartsHistoryError("SMARTS change event not present in retained evidence")
        county, file_sha, outcome, row_sha256, raw_csv = selected
        if county not in COUNTIES or not source_key.startswith(f"smarts:facility:{county}:"):
            raise SmartsHistoryError("SMARTS source county does not agree with source identity")
        latest = history.get(county)
        if latest is None or latest[0] != snapshot_id:
            return _result(
                source_key, snapshot_id, county, file_sha,
                None, None, "historical_snapshot_requires_current_review", [], 0,
            )
        if outcome == "missing_from_new":
            return _result(
                source_key, snapshot_id, county, file_sha,
                None, None, "missing_from_new_is_not_deletion", [], 0,
            )
        if outcome not in {"new", "changed"} or not isinstance(row_sha256, str):
            raise SmartsHistoryError("Unsupported SMARTS source change event")
        snapshot = latest[1]
        evidence = snapshot.source_rows.get(source_key)
        if evidence is None or evidence.row_sha256 != row_sha256:
            raise SmartsHistoryError("SMARTS current source row differs from history")
        apn, state = _read_source_apn(
            raw_csv, county=county, source_key=source_key, row_sha256=row_sha256
        )
        connection.rollback()
    finally:
        connection.close()
    if apn is None:
        return _result(source_key, snapshot_id, county, file_sha, row_sha256, None, state, [], 0)
    conditions = (
        ParcelCoreRecordRow.normalized_apn == apn,
        func.lower(func.trim(ParcelCoreRecordRow.county)).in_(
            [_county(county), f"{_county(county)} county"]
        ),
        ParcelCoreRecordRow.state == "CA",
    )
    total = session.scalar(
        select(func.count()).select_from(ParcelCoreRecordRow).where(*conditions)
    ) or 0
    if type(total) is not int or total < 0:
        raise ValueError("Retained parcel candidate count is inconsistent")
    rows = session.scalars(
        select(ParcelCoreRecordRow)
        .where(*conditions)
        .order_by(ParcelCoreRecordRow.id)
        .limit(_LIMIT)
    ).all()
    candidates: list[dict[str, str]] = []
    for row in rows:
        try:
            parcel = ParcelCoreRecord.model_validate(json.loads(row.payload_json))
        except (ValueError, TypeError) as exc:
            raise ValueError("Retained parcel candidate payload invalid") from exc
        if (
            row.parcel_record_id != parcel.parcel_record_id
            or row.source_key != parcel.source_key
            or row.source_record_id != parcel.source_record_id
            or row.normalized_apn != parcel.normalized_apn
            or row.apn != parcel.apn
            or row.county != parcel.county or row.state != parcel.state
            or row.address != parcel.address
            or row.normalized_address != parcel.normalized_address
            or _county(parcel.county) != _county(county)
            or parcel.normalized_apn != apn or parcel.state != "CA"
        ):
            raise ValueError("Retained parcel index does not agree with source payload")
        candidates.append({
            "parcel_record_id": parcel.parcel_record_id,
            "parcel_source_key": parcel.source_key,
            "parcel_source_record_id": parcel.source_record_id or "",
            "candidate_basis": "same_county_exact_normalized_apn",
        })
    if len(candidates) != min(_LIMIT, total):
        raise ValueError("Retained parcel candidate query is inconsistent")
    state = (
        "parcel_candidate_ambiguous" if total > 1
        else "parcel_candidate_requires_review" if total == 1
        else "parcel_not_retained"
    )
    return _result(source_key, snapshot_id, county, file_sha, row_sha256, apn, state,
                   candidates, total)


def _result(
    source_key: str, snapshot_id: int, county: str, file_sha: str,
    row_sha256: str | None, apn: str | None, status: str,
    candidates: list[dict[str, str]], total: int,
) -> dict[str, object]:
    return {
        "schema_version": "constructionsight.smarts_parcel_review.v1",
        "source_key": source_key, "snapshot_id": snapshot_id, "county": county,
        "original_file_sha256": file_sha, "source_row_sha256": row_sha256,
        "source_claimed_normalized_apn": apn,
        "status": status, "candidate_total": total, "returned": len(candidates),
        "truncated": total > len(candidates), "candidates": candidates,
        "read_only": True, "network_executed": False,
        "source_history_integrity_verified": True,
        "parcel_identity_verified": False, "project_identity_verified": False,
        "construction_activity_verified": False, "lead_created": False,
        "outreach_authorized": False, "bid_authorized": False,
    }
