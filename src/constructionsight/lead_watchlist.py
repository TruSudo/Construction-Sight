"""Persistent local watch reminders; source changes never establish project readiness."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from constructionsight.lead_workflow import connect, now
from constructionsight.security_fit import parse_date
from constructionsight.smarts_active import PUBLIC_FIELDS


def retained(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: row.get("source_fields", row).get(key) if key in PUBLIC_FIELDS else row.get(key)
        for key in (
            *PUBLIC_FIELDS,
            "source_key",
            "row_sha256",
            "conflicting_fields",
            "source_variants",
        )
    }


def digest(row: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(retained(row), sort_keys=True).encode()).hexdigest()


def entries(directory: Path) -> dict[str, dict[str, Any]]:
    with connect(directory) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS watches (
            source_key TEXT PRIMARY KEY, note TEXT NOT NULL, remind_on TEXT,
            acknowledged_digest TEXT NOT NULL, acknowledged_present INTEGER NOT NULL,
            retained_row TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        return {r["source_key"]: dict(r) for r in db.execute("SELECT * FROM watches")}


def update_watch(
    directory: Path, key: str, payload: dict[str, Any], row: dict[str, Any] | None
) -> dict[str, Any]:
    if set(payload) - {"action", "note", "remind_on"}:
        raise ValueError("Unexpected watch fields")
    action = payload.get("action")
    prior = entries(directory).get(key)
    if action == "remove":
        with connect(directory) as db:
            db.execute("DELETE FROM watches WHERE source_key=?", (key,))
        return {"removed": True}
    if action not in ("save", "acknowledge") or (row is None and prior is None):
        raise ValueError("Unknown action or source record")
    note = payload.get("note", prior["note"] if prior else "")
    date = payload.get("remind_on", prior["remind_on"] if prior else None) or None
    if not isinstance(note, str) or len(note) > 2000:
        raise ValueError("Reminder note must be text of at most 2,000 characters")
    if date is not None and (
        not isinstance(date, str)
        or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date)
        or parse_date(date) is None
    ):
        raise ValueError("Reminder date must be a valid YYYY-MM-DD date")
    # Editing a reminder must not silently dismiss a source-change alert.
    acknowledge = prior is None or action == "acknowledge"
    if prior is None:
        assert row is not None
        baseline, present, saved_row = digest(row), 1, json.dumps(retained(row))
    else:
        baseline = digest(row) if acknowledge and row is not None else prior["acknowledged_digest"]
        present = int(row is not None) if acknowledge else prior["acknowledged_present"]
        saved_row = json.dumps(retained(row)) if row is not None else prior["retained_row"]
    with connect(directory) as db:
        db.execute(
            "INSERT INTO watches VALUES (?,?,?,?,?,?,?) ON CONFLICT(source_key) DO UPDATE SET "
            "note=excluded.note,remind_on=excluded.remind_on,"
            "acknowledged_digest=excluded.acknowledged_digest,"
            "acknowledged_present=excluded.acknowledged_present,"
            "retained_row=excluded.retained_row,updated_at=excluded.updated_at",
            (key, note, date, baseline, present, saved_row, now()),
        )
    return {"saved": True, "source_key": key}


def watchlist(directory: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    current = {r["source_key"]: r for r in rows}
    today = datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()
    result = []
    for key, item in entries(directory).items():
        row = current.get(key)
        present = row is not None
        changed = present != bool(item["acknowledged_present"]) or (
            row is not None and digest(row) != item["acknowledged_digest"]
        )
        result.append(
            {
                "source_key": key,
                "note": item["note"],
                "remind_on": item["remind_on"],
                "due": bool(item["remind_on"] and item["remind_on"] <= today),
                "changed": changed,
                "present": present,
                "source_state": "Source record changed"
                if changed and present
                else "Missing from latest Active filter; not a deletion"
                if not present
                else "No unreviewed source change",
                "row": retained(row) if row else json.loads(item["retained_row"]),
                "updated_at": item["updated_at"],
            }
        )
    return sorted(
        result,
        key=lambda r: (not r["changed"], not r["due"], r["remind_on"] or "9999", r["source_key"]),
    )
