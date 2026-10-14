"""Immutable revisions of reusable operator scope and price-book entries."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from constructionsight import command_center_commercial as commercial
from constructionsight.command_center_state import fingerprint
from constructionsight.lead_workflow import connect, now


def initialize(directory: Path) -> None:
    commercial.initialize(directory)
    with connect(directory) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS cc_catalog_versions(
            kind TEXT,id TEXT,version INTEGER,at TEXT,data TEXT,digest TEXT,
            PRIMARY KEY(kind,id,version));
        CREATE TRIGGER IF NOT EXISTS cc_catalog_no_update BEFORE UPDATE ON cc_catalog_versions
          BEGIN SELECT RAISE(ABORT,'Catalog versions are immutable'); END;
        CREATE TRIGGER IF NOT EXISTS cc_catalog_no_delete BEFORE DELETE ON cc_catalog_versions
          BEGIN SELECT RAISE(ABORT,'Catalog versions are immutable'); END;
        """)
        for name, body in commercial.SCOPES.items():
            data = {
                "id": name,
                "name": name,
                "service": name,
                "body": body,
                "version": 1,
                "source": "Editable starter scope; review for each project",
                "at": now(),
            }
            db.execute(
                "INSERT OR IGNORE INTO cc_catalog_versions VALUES (?,?,?,?,?,?)",
                ("scope", name, 1, data["at"], json.dumps(data), fingerprint(data)),
            )
        for row in db.execute("SELECT id,data FROM cc_prices").fetchall():
            data = json.loads(row["data"])
            if db.execute(
                "SELECT 1 FROM cc_catalog_versions WHERE kind=? AND id=?", ("price", row["id"])
            ).fetchone():
                continue
            data.update(version=1)
            data.setdefault("service", None)
            db.execute(
                "INSERT INTO cc_catalog_versions VALUES (?,?,?,?,?,?)",
                ("price", row["id"], 1, data["at"], json.dumps(data), fingerprint(data)),
            )


def history(directory: Path, kind: str, key: str | None = None) -> list[dict[str, Any]]:
    if kind not in ("scope", "price"):
        raise ValueError("Unknown catalog kind")
    initialize(directory)
    with connect(directory) as db:
        rows = db.execute(
            "SELECT data,digest FROM cc_catalog_versions WHERE kind=? "
            "AND (? IS NULL OR id=?) ORDER BY id,version DESC",
            (kind, key, key),
        ).fetchall()
    result = []
    for row in rows:
        data = json.loads(row["data"])
        if fingerprint(data) != row["digest"]:
            raise ValueError("Catalog version integrity mismatch")
        result.append(data)
    return result


def current(directory: Path, kind: str) -> list[dict[str, Any]]:
    seen = set()
    result = []
    for data in history(directory, kind):
        if data["id"] not in seen:
            seen.add(data["id"])
            result.append(data)
    return result


def store(directory: Path, kind: str, data: dict[str, Any], expected: Any) -> dict[str, Any]:
    initialize(directory)
    with connect(directory) as db:
        db.execute("BEGIN IMMEDIATE")
        prior = (
            db.execute(
                "SELECT MAX(version) AS version FROM cc_catalog_versions WHERE kind=? AND id=?",
                (kind, data["id"]),
            ).fetchone()["version"]
            or 0
        )
        if type(expected) is not int or expected != prior:
            raise ValueError("Catalog changed since edit; reload before saving")
        if kind == "scope":
            duplicate = db.execute(
                "SELECT 1 FROM cc_catalog_versions AS v WHERE kind=? AND id!=? "
                "AND LOWER(json_extract(data,'$.name'))=LOWER(?) AND version=(SELECT MAX(version) "
                "FROM cc_catalog_versions WHERE kind=v.kind AND id=v.id)",
                ("scope", data["id"], data["name"]),
            ).fetchone()
            if duplicate:
                raise ValueError("A scope template already uses that name")
        data = {**data, "version": prior + 1, "at": now()}
        db.execute(
            "INSERT INTO cc_catalog_versions VALUES (?,?,?,?,?,?)",
            (kind, data["id"], data["version"], data["at"], json.dumps(data), fingerprint(data)),
        )
        if kind == "price":
            db.execute(
                "INSERT OR REPLACE INTO cc_prices VALUES (?,?)", (data["id"], json.dumps(data))
            )
    return data


def save_scope(directory: Path, payload: dict[str, Any]) -> dict[str, Any]:
    if set(payload) - {"id", "expected_version", "name", "service", "body"}:
        raise ValueError("Unknown scope template fields")
    if payload.get("service") not in commercial.SCOPES:
        raise ValueError("Choose CCTV, access control, intrusion or structured cabling")
    data = {
        "id": commercial.required(payload.get("id") or str(uuid.uuid4())),
        "name": commercial.required(payload.get("name"), limit=200),
        "service": payload["service"],
        "body": commercial.required(payload.get("body"), limit=20000),
        "source": "Entered by user; review for each project",
    }
    return store(directory, "scope", data, payload.get("expected_version", 0))


def scopes(directory: Path) -> dict[str, str]:
    return {data["name"]: data["body"] for data in current(directory, "scope")}
