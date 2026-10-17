"""Local operator feedback, run history, and outcome reporting. No external writes."""

from __future__ import annotations

import csv
import fcntl
import io
import json
import re
import sqlite3
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from constructionsight.security_fit import parse_date
from constructionsight.storage.database import prepare_private_database

STATUSES = (
    "New",
    "Reviewing",
    "Outreach queued",
    "Contacted",
    "Quoted",
    "Won",
    "Lost",
    "Not a fit",
)
REASONS = (
    "Project too small",
    "Wrong project type",
    "Timing",
    "Already secured",
    "Price",
    "No decision-maker",
    "Outside service area",
    "Other",
)


def now() -> str:
    return datetime.now(UTC).isoformat()


def connect(directory: Path) -> sqlite3.Connection:
    path = prepare_private_database(directory / "workflow.sqlite3")
    before = path.stat()
    db = sqlite3.connect(path, timeout=15)
    try:
        prepare_private_database(path, create=False)
        after = path.stat()
        if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
            raise ValueError("workflow database identity changed while opening")
        db.execute("PRAGMA foreign_keys=ON")
        if db.execute("PRAGMA foreign_keys").fetchone() != (1,):
            raise ValueError("workflow database foreign keys could not be enabled")
    except BaseException:
        db.close()
        raise
    db.row_factory = sqlite3.Row
    db.executescript("""
      CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT,
        outcome TEXT NOT NULL, rows INTEGER, new_count INTEGER, removed_count INTEGER,
        requests INTEGER, error TEXT, snapshot TEXT);
      CREATE TABLE IF NOT EXISTS feedback (
        source_key TEXT PRIMARY KEY, status TEXT NOT NULL, notes TEXT NOT NULL,
        last_contacted TEXT, reason_code TEXT, reason_text TEXT, updated_at TEXT NOT NULL,
        score_at_update INTEGER, project_type_at_update TEXT);
      CREATE TABLE IF NOT EXISTS feedback_events (
        id INTEGER PRIMARY KEY, source_key TEXT NOT NULL, changed_at TEXT NOT NULL,
        status TEXT NOT NULL, score INTEGER, project_type TEXT);
    """)
    return db


@contextmanager
def capture_lock(directory: Path) -> Iterator[None]:
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (directory / "capture.lock").open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def begin_run(directory: Path) -> int:
    with connect(directory) as db:
        db.execute(
            "UPDATE runs SET outcome='error',finished_at=?,error='Interrupted capture' "
            "WHERE outcome='running'",
            (now(),),
        )
        cursor = db.execute("INSERT INTO runs(started_at,outcome) VALUES (?, 'running')", (now(),))
        return int(cursor.lastrowid or 0)


def finish_run(
    directory: Path, run_id: int, snapshot: dict[str, Any] | None, error: str | None = None
) -> None:
    with connect(directory) as db:
        db.execute(
            "UPDATE runs SET finished_at=?,outcome=?,rows=?,new_count=?,removed_count=?,"
            "requests=?,error=?,snapshot=? WHERE id=?",
            (
                now(),
                "error" if error else "success",
                len(snapshot["rows"]) if snapshot else None,
                snapshot.get("new_count") if snapshot else None,
                snapshot.get("missing_count") if snapshot else None,
                snapshot.get("requests") if snapshot else None,
                error,
                json.dumps(snapshot) if snapshot else None,
                run_id,
            ),
        )


def run_history(directory: Path) -> list[dict[str, Any]]:
    with connect(directory) as db:
        return [
            dict(r)
            for r in db.execute(
                "SELECT id,started_at,finished_at,outcome,rows,new_count,"
                "removed_count,requests,error FROM runs ORDER BY id DESC LIMIT 100"
            )
        ]


def get_feedback(directory: Path) -> dict[str, dict[str, Any]]:
    with connect(directory) as db:
        return {str(r["source_key"]): dict(r) for r in db.execute("SELECT * FROM feedback")}


def save_feedback(
    directory: Path, source_key: str, payload: dict[str, Any], lead: dict[str, Any]
) -> dict[str, Any]:
    if set(payload) - {"status", "notes", "last_contacted", "reason_code", "reason_text"}:
        raise ValueError("Unexpected feedback fields")
    status = payload.get("status")
    if status not in STATUSES:
        raise ValueError("Invalid lead status")
    notes, reason_text = payload.get("notes", ""), payload.get("reason_text", "")
    if not isinstance(notes, str) or len(notes) > 10000:
        raise ValueError("Notes must be text of at most 10,000 characters")
    if not isinstance(reason_text, str) or len(reason_text) > 2000:
        raise ValueError("Reason must be text of at most 2,000 characters")
    reason = payload.get("reason_code") or None
    if status in ("Lost", "Not a fit") and reason not in REASONS:
        raise ValueError("Choose a reason for Lost or Not a fit")
    if reason is not None and reason not in REASONS:
        raise ValueError("Invalid reason")
    contacted = payload.get("last_contacted") or None
    if contacted is not None and (
        not isinstance(contacted, str)
        or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", contacted)
        or parse_date(contacted) is None
    ):
        raise ValueError("Last-contacted date must be a valid YYYY-MM-DD date")
    with connect(directory) as db:
        prior = db.execute(
            "SELECT status,score_at_update,project_type_at_update FROM feedback WHERE source_key=?",
            (source_key,),
        ).fetchone()
        same_status = prior is not None and prior["status"] == status
        saved_score = prior["score_at_update"] if same_status else lead["security_fit"]
        saved_type = prior["project_type_at_update"] if same_status else lead["project_type"]
        db.execute(
            "INSERT INTO feedback VALUES (?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(source_key) DO UPDATE SET status=excluded.status,notes=excluded.notes,"
            "last_contacted=excluded.last_contacted,reason_code=excluded.reason_code,"
            "reason_text=excluded.reason_text,updated_at=excluded.updated_at,"
            "score_at_update=excluded.score_at_update,project_type_at_update=excluded.project_type_at_update",
            (
                source_key,
                status,
                notes,
                contacted,
                reason,
                reason_text,
                now(),
                saved_score,
                saved_type,
            ),
        )
        db.execute(
            "INSERT INTO feedback_events(source_key,changed_at,status,score,project_type) "
            "VALUES (?,?,?,?,?)",
            (source_key, now(), status, lead["security_fit"], lead["project_type"]),
        )
    return get_feedback(directory)[source_key]


def csv_export(rows: list[dict[str, Any]]) -> bytes:
    fields = (
        "SITE_NAME",
        "SITE_CITY",
        "SITE_COUNTY",
        "WDID",
        "APP_ID",
        "DEVELOPER_NAME",
        "security_fit",
        "project_type",
        "reason",
        "status",
        "notes",
        "last_contacted",
        "reason_code",
        "reason_text",
    )
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        values = {**row, **row.get("feedback", {})}
        values.setdefault("status", "New")
        record = {}
        for key in fields:
            value = str(values[key]) if values.get(key) is not None else ""
            # Spreadsheet cells must remain text even when source names resemble formulas.
            if value.lstrip().startswith(("=", "+", "-", "@")):
                value = "'" + value
            record[key] = value
        writer.writerow(record)
    return out.getvalue().encode("utf-8-sig")


def normalize_party(value: Any) -> str:
    value = str(value or "").casefold().strip()
    if value in {"", "na", "n/a", "none", "unknown", "null"}:
        return ""
    return " ".join(re.sub(r"[^\w\s]", " ", value).split())


def developer_accounts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = normalize_party(row.get("DEVELOPER_NAME"))
        if not key:
            key = normalize_party(row.get("OWNER_NAME"))
        if not key:
            continue
        if key not in groups:
            groups[key] = {
                "key": key,
                "name": row.get("DEVELOPER_NAME")
                if normalize_party(row.get("DEVELOPER_NAME"))
                else row.get("OWNER_NAME"),
                "sites": [],
                "counties": set(),
                "start_dates": [],
            }
        account = groups[key]
        account["sites"].append(row)
        account["counties"].add(row["SITE_COUNTY"])
        start = parse_date(row.get("CONSTRUCTION_COMMENCEMENT_DATE"))
        if start:
            account["start_dates"].append(start.isoformat())
    results = []
    for account in groups.values():
        dates = account.pop("start_dates")
        account["earliest_start"] = min(dates) if dates else None
        account["counties"] = sorted(account["counties"])
        account["active_sites"] = len(account["sites"])
        results.append(account)
    return sorted(results, key=lambda a: (-a["active_sites"], a["key"]))


def outcome_report(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        feedback = row.get("feedback", {})
        status = feedback.get("status", "New")
        score = feedback.get("score_at_update", row["security_fit"])
        band = "60–100" if score >= 60 else "30–59" if score >= 30 else "0–29"
        groups[(feedback.get("project_type_at_update") or row["project_type"], band)].append(
            {"status": status, "score": score}
        )
    report = []
    for (kind, band), items in sorted(groups.items()):
        won = sum(x["status"] == "Won" for x in items)
        lost = sum(x["status"] == "Lost" for x in items)
        report.append(
            {
                "project_type": kind,
                "score_band": band,
                "leads": len(items),
                "won": won,
                "lost": lost,
                "not_a_fit": sum(x["status"] == "Not a fit" for x in items),
                "closed": won + lost,
                "win_rate": won / (won + lost) if won + lost else None,
                "average_score": sum(x["score"] for x in items) / len(items),
            }
        )
    return report
