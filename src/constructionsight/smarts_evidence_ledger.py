"""Opt-in, SQLite-atomic SMARTS source evidence journal, not a project database.

The original bounded CKAN response stays private in an owner-only sidecar store.
Only observations and source-scoped versions are recorded; no site, lead, status,
or contact is promoted into ConstructionSight's governed application database.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import stat
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from constructionsight.smarts_api import MAX_RESPONSE_BYTES, RESOURCE_IDS, SmartsPage
from constructionsight.smarts_intake_bridge import (
    SmartsIntakePreview,
    build_smarts_intake_preview,
)

_APPLICATION_ID = 0x43534D54  # CSMT
_SCHEMA_VERSION = 1


class SmartsEvidenceError(ValueError):
    """Evidence is missing, ambiguous, altered, or unsafe to persist."""


@dataclass(frozen=True)
class SmartsEvidenceReceipt:
    source_record_key: str
    row_sha256: str
    response_sha256: str
    observation_id: int
    version: int
    outcome: str  # first_observation | changed | unchanged


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_row(record: dict[str, Any]) -> bytes:
    try:
        return json.dumps(
            {key: value for key, value in record.items() if key != "_id"},
            sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise SmartsEvidenceError("Unserializable SMARTS record") from exc


def _raw_record(page: SmartsPage, preview: SmartsIntakePreview) -> tuple[bytes, dict[str, Any]]:
    raw = page.raw_response_bytes
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_RESPONSE_BYTES:
        raise SmartsEvidenceError("Bounded original HTTP response bytes are required")
    if not page.request_url.startswith(
        "https://publish.data.ca.gov/api/3/action/datastore_search?"
    ):
        raise SmartsEvidenceError("Unapproved SMARTS evidence endpoint")
    if _sha(raw) != page.response_sha256 or page.response_sha256 != preview.source_response_sha256:
        raise SmartsEvidenceError("SMARTS raw response digest mismatch")
    try:
        payload = json.loads(raw)
        result = payload["result"]
        records = result["records"]
    except (ValueError, TypeError, KeyError) as exc:
        raise SmartsEvidenceError("Invalid original SMARTS response") from exc
    if (
        payload.get("success") is not True
        or not isinstance(result, dict)
        or result.get("resource_id", RESOURCE_IDS["facilities"]) != RESOURCE_IDS["facilities"]
        or result.get("total") != 1
        or page.resource != "facilities"
        or page.total != 1
        or page.county not in ("San Bernardino", "Riverside")
        or len(page.records) != 1
        or not isinstance(records, list)
        or len(records) != 1
        or not isinstance(records[0], dict)
        or records[0] != page.records[0]
    ):
        raise SmartsEvidenceError("Original response and exact facility page disagree")
    row = records[0]
    if row.get("SITE_COUNTY") != page.county:
        raise SmartsEvidenceError("Original response county mismatch")
    if _sha(_canonical_row(row)) != preview.record_sha256:
        raise SmartsEvidenceError("Canonical row digest mismatch")
    expected = build_smarts_intake_preview(page, row)
    if (
        preview.source_record_key != expected.source_record_key
        or preview.intake.record_hints != expected.intake.record_hints
        or preview.site_resolution.resolution_id != expected.site_resolution.resolution_id
    ):
        raise SmartsEvidenceError("Preview identity or source hints are not bound to raw row")
    if preview.identity_status != "source_scoped_candidate" or preview.source_record_key is None:
        raise SmartsEvidenceError("A source-scoped identity is required for versioning")
    return raw, row


def _aliases(preview: SmartsIntakePreview) -> list[tuple[str, str]]:
    hints = preview.intake.record_hints
    result: list[tuple[str, str]] = []
    app_id = hints.get("smarts_app_id")
    wdid = hints.get("smarts_wdid")
    if isinstance(app_id, str) and re.fullmatch(r"[0-9]{1,15}", app_id):
        result.append(("app_id", app_id))
    if isinstance(wdid, str) and re.fullmatch(r"[A-Za-z0-9 ]{2,32}", wdid):
        result.append(("wdid", wdid))
    if not result:
        raise SmartsEvidenceError("No usable source identity")
    return result


def _safe_database_path(path: Path) -> Path:
    """Require an existing private directory and a private, regular DB file."""
    path = Path(path).absolute()
    if path.suffix != ".sqlite3" or path.name in {".", ".."}:
        raise SmartsEvidenceError("Journal must be a named .sqlite3 file")
    parent = path.parent
    try:
        parent_info = parent.lstat()
    except FileNotFoundError as exc:
        raise SmartsEvidenceError("Create an owner-only journal directory first") from exc
    if (
        not stat.S_ISDIR(parent_info.st_mode)
        or parent_info.st_uid != os.geteuid()
        or stat.S_IMODE(parent_info.st_mode) & 0o077
    ):
        raise SmartsEvidenceError("Journal directory must be owned and mode 0700 or stricter")
    try:
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        pass
    except OSError as exc:
        raise SmartsEvidenceError("Unable to securely create SMARTS journal") from exc
    else:
        os.close(fd)
    info = path.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.geteuid()
        or info.st_nlink != 1
        or stat.S_IMODE(info.st_mode) != 0o600
    ):
        raise SmartsEvidenceError("Journal file must be owned, regular, and mode 0600")
    return path


def _open(path: Path) -> sqlite3.Connection:
    db = _safe_database_path(path)
    connection = sqlite3.connect(str(db), timeout=10, isolation_level=None)
    try:
        connection.execute("PRAGMA busy_timeout=10000")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("BEGIN IMMEDIATE")
        application_id = connection.execute("PRAGMA application_id").fetchone()[0]
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        existing = {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        if not existing and application_id == 0 and version == 0:
            schemas = (
                "CREATE TABLE smarts_observations ("
                "id INTEGER PRIMARY KEY, source_key TEXT NOT NULL, "
                "recorded_at TEXT NOT NULL, request_url TEXT NOT NULL, "
                "response_sha256 TEXT NOT NULL, row_sha256 TEXT NOT NULL, "
                "raw_response BLOB NOT NULL)",
                "CREATE TABLE smarts_versions ("
                "source_key TEXT NOT NULL, version INTEGER NOT NULL CHECK(version > 0), "
                "row_sha256 TEXT NOT NULL, previous_event_sha256 TEXT, "
                "event_sha256 TEXT NOT NULL, "
                "observation_id INTEGER NOT NULL REFERENCES smarts_observations(id), "
                "PRIMARY KEY(source_key, version))",
                "CREATE TABLE smarts_aliases ("
                "county TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('app_id', 'wdid')), "
                "value TEXT NOT NULL, source_key TEXT NOT NULL, "
                "PRIMARY KEY(county, kind, value))",
            )
            for schema in schemas:
                connection.execute(schema)
            for table in ("smarts_observations", "smarts_versions", "smarts_aliases"):
                for action in ("UPDATE", "DELETE"):
                    connection.execute(
                        f"CREATE TRIGGER {table}_no_{action.lower()} "
                        f"BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'immutable'); END"
                    )
            connection.execute(f"PRAGMA application_id={_APPLICATION_ID}")
            connection.execute(f"PRAGMA user_version={_SCHEMA_VERSION}")

        elif (
            application_id != _APPLICATION_ID or version != _SCHEMA_VERSION
            or existing != {"smarts_observations", "smarts_versions", "smarts_aliases"}
        ):
            raise SmartsEvidenceError("Incompatible or ungoverned evidence journal")
        if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise SmartsEvidenceError("Evidence journal SQLite integrity check failed")
        expected_columns = {
            "smarts_observations": (
                "id", "source_key", "recorded_at", "request_url", "response_sha256",
                "row_sha256", "raw_response",
            ),
            "smarts_versions": (
                "source_key", "version", "row_sha256", "previous_event_sha256",
                "event_sha256", "observation_id",
            ),
            "smarts_aliases": ("county", "kind", "value", "source_key"),
        }
        for table, names in expected_columns.items():
            observed = tuple(
                row[1] for row in connection.execute(f"PRAGMA table_info({table})")
            )
            if observed != names:
                raise SmartsEvidenceError("Evidence journal schema columns differ")
        expected_triggers = {
            f"{table}_no_{action}"
            for table in expected_columns
            for action in ("update", "delete")
        }
        actual_triggers = {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger'"
            )
        }
        if actual_triggers != expected_triggers:
            raise SmartsEvidenceError("Evidence journal immutability triggers are missing")
        return connection
    except Exception:
        connection.close()
        raise


def _event_digest(source_key: str, version: int, row_sha: str, previous: str | None) -> str:
    data = json.dumps([source_key, version, row_sha, previous], separators=(",", ":"))
    return _sha(data.encode("utf-8"))


def record_smarts_observation(
    path: Path, page: SmartsPage, preview: SmartsIntakePreview
) -> SmartsEvidenceReceipt:
    """Durably capture original bytes and an append-only semantic version atomically."""
    raw, row = _raw_record(page, preview)
    assert preview.source_record_key is not None
    source_key = preview.source_record_key
    county = str(row["SITE_COUNTY"])
    aliases = _aliases(preview)
    connection = _open(path)
    try:
        bindings = [
            connection.execute(
                "SELECT source_key FROM smarts_aliases WHERE county=? AND kind=? AND value=?",
                (county, kind, value),
            ).fetchone()
            for kind, value in aliases
        ]
        mapped = {binding[0] for binding in bindings if binding is not None}
        if len(mapped) > 1:
            raise SmartsEvidenceError("Conflicting WDID/APP_ID aliases require human review")
        canonical = next(iter(mapped)) if mapped else source_key
        if mapped and any(binding is None for binding in bindings):
            raise SmartsEvidenceError("Previously unseen alias on existing source requires review")
        if not mapped:
            for kind, value in aliases:
                connection.execute(
                    "INSERT INTO smarts_aliases(county,kind,value,source_key) VALUES (?,?,?,?)",
                    (county, kind, value, canonical),
                )
        now = datetime.now(UTC).isoformat()
        cursor = connection.execute(
            "INSERT INTO smarts_observations "
            "(source_key,recorded_at,request_url,response_sha256,row_sha256,raw_response) "
            "VALUES (?,?,?,?,?,?)",
            (canonical, now, page.request_url, page.response_sha256, preview.record_sha256, raw),
        )
        observation_id = cursor.lastrowid
        if not isinstance(observation_id, int):
            raise SmartsEvidenceError("Source observation ID was not assigned")
        latest = connection.execute(
            "SELECT version, row_sha256, event_sha256 FROM smarts_versions "
            "WHERE source_key=? ORDER BY version DESC LIMIT 1", (canonical,),
        ).fetchone()
        if latest is None:
            version, outcome, previous = 1, "first_observation", None
        elif latest[1] == preview.record_sha256:
            version, outcome, previous = latest[0], "unchanged", latest[2]
        else:
            version, outcome, previous = latest[0] + 1, "changed", latest[2]
        if outcome != "unchanged":
            connection.execute(
                "INSERT INTO smarts_versions "
                "(source_key,version,row_sha256,previous_event_sha256,event_sha256,observation_id) "
                "VALUES (?,?,?,?,?,?)",
                (canonical, version, preview.record_sha256, previous,
                 _event_digest(canonical, version, preview.record_sha256, previous),
                observation_id),
            )
        connection.commit()
        return SmartsEvidenceReceipt(
            canonical, preview.record_sha256, page.response_sha256, observation_id, version, outcome
        )
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def verify_smarts_journal(path: Path) -> dict[str, int]:
    """Check retained bytes, source row digests and each source's version chain."""
    connection = _open(path)
    try:
        source_rows: dict[str, set[str]] = {}
        observation_history: dict[str, list[tuple[int, str]]] = {}
        observations = 0
        for observation_id, source_key, raw_sha, row_sha, raw in connection.execute(
            "SELECT id,source_key,response_sha256,row_sha256,raw_response "
            "FROM smarts_observations ORDER BY id"
        ):
            observations += 1
            body = bytes(raw)
            try:
                source_row = json.loads(body)["result"]["records"][0]
            except (ValueError, TypeError, KeyError, IndexError) as exc:
                raise SmartsEvidenceError("Corrupt retained original SMARTS body") from exc
            if _sha(body) != raw_sha or _sha(_canonical_row(source_row)) != row_sha:
                raise SmartsEvidenceError("Retained SMARTS response or row digest mismatch")
            source_rows.setdefault(source_key, set()).add(row_sha)
            observation_history.setdefault(source_key, []).append((observation_id, row_sha))
        latest: dict[str, tuple[int, str]] = {}
        version_observations: dict[str, list[tuple[int, str]]] = {}
        versions = 0
        for (
            source_key, number, row_sha, prev, event_sha, observation_id,
            observed_row_sha, observed_source,
        ) in (
            connection.execute(
                "SELECT v.source_key,v.version,v.row_sha256,v.previous_event_sha256,"
                "v.event_sha256,v.observation_id,o.row_sha256,o.source_key FROM smarts_versions v "
                "JOIN smarts_observations o ON v.observation_id=o.id "
                "ORDER BY v.source_key,v.version"
            )
        ):
            versions += 1
            prior = latest.get(source_key)
            if (
                number != (prior[0] + 1 if prior else 1)
                or prev != (prior[1] if prior else None)
                or row_sha not in source_rows.get(source_key, set())
                or row_sha != observed_row_sha
                or source_key != observed_source
                or event_sha != _event_digest(source_key, number, row_sha, prev)
            ):
                raise SmartsEvidenceError("SMARTS version-chain integrity failure")
            latest[source_key] = (number, event_sha)
            version_observations.setdefault(source_key, []).append((observation_id, row_sha))
        for source_key, observations_for_source in observation_history.items():
            expected_events: list[tuple[int, str]] = []
            last_row_sha: str | None = None
            for observation_id, row_sha in observations_for_source:
                if row_sha != last_row_sha:
                    expected_events.append((observation_id, row_sha))
                last_row_sha = row_sha
            if expected_events != version_observations.get(source_key, []):
                raise SmartsEvidenceError("Observation/version transition history mismatch")
        if any(source not in latest for source in source_rows):
            raise SmartsEvidenceError("Source observations missing version history")
        if any(row[0] not in latest for row in connection.execute(
            "SELECT source_key FROM smarts_aliases"
        )):
            raise SmartsEvidenceError("Orphaned source alias")
        connection.commit()
        return {"observations": observations, "versions": versions, "sources": len(latest)}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main(argv: list[str] | None = None) -> int:
    """Offline, no-network journal integrity check with redacted summary output."""
    import argparse

    parser = argparse.ArgumentParser(description="Verify private SMARTS evidence journal")
    parser.add_argument("--verify", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = verify_smarts_journal(args.verify)
    except (SmartsEvidenceError, sqlite3.Error) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    print(json.dumps({"ok": True, "integrity": result}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
