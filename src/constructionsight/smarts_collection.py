"""Explicit, bounded SMARTS roster collection with at-least-once restart recovery.

Only exact facility lookups are supported. The checkpoint is separate from the
immutable evidence journal and may lag a committed observation after a crash;
replay then creates another observation but never a false semantic version.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import httpx

from constructionsight.smarts_api import (
    COUNTIES,
    USER_AGENT,
    SmartsApiError,
    SmartsPage,
    fetch_exact_facility,
)
from constructionsight.smarts_evidence_ledger import (
    SmartsEvidenceError,
    _safe_database_path,
    record_smarts_observation,
    verify_smarts_journal,
)
from constructionsight.smarts_intake_bridge import build_smarts_intake_preview

MAX_ROSTER = 25
_CHECKPOINT_APP_ID = 0x43534350  # CSCP


class SmartsCollectionError(ValueError):
    """The roster, checkpoint, or collection result cannot safely advance."""


@dataclass(frozen=True)
class FacilityTarget:
    county: str
    app_id: str | None = None
    wdid: str | None = None


@dataclass(frozen=True)
class CollectionResult:
    run_id: str
    completed: int
    total: int
    requests: int
    first_observations: int
    changed: int
    unchanged: int


def parse_roster(data: bytes) -> tuple[FacilityTarget, ...]:
    """Accept only a small, explicit list of exact, county-scoped identities."""
    if len(data) > 8192:
        raise SmartsCollectionError("Roster exceeds byte limit")
    try:
        raw = json.loads(data)
    except (ValueError, UnicodeDecodeError) as exc:
        raise SmartsCollectionError("Invalid roster JSON") from exc
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_ROSTER:
        raise SmartsCollectionError("Roster must contain 1..25 exact facilities")
    targets: list[FacilityTarget] = []
    seen: set[tuple[str, str, str]] = set()
    for item in raw:
        if type(item) is not dict or item.get("county") not in COUNTIES:
            raise SmartsCollectionError("Invalid roster county or target")
        if set(item) not in ({"county", "app_id"}, {"county", "wdid"}):
            raise SmartsCollectionError("Choose exactly one source identifier per target")
        county = item["county"]
        if "app_id" in item:
            value = item["app_id"]
            if (
                type(value) is not str
                or not re.fullmatch(r"[0-9]{1,15}", value)
                or not any(digit != "0" for digit in value)
            ):
                raise SmartsCollectionError("Invalid SMARTS APP_ID")
            kind = "app_id"
        else:
            value = item["wdid"]
            if (
                type(value) is not str
                or not re.fullmatch(r"[A-Za-z0-9 ]{2,32}", value)
                or not value.strip()
            ):
                raise SmartsCollectionError("Invalid SMARTS WDID")
            kind = "wdid"
        identity = (county, kind, value)
        if identity in seen:
            raise SmartsCollectionError("Duplicate roster target")
        seen.add(identity)
        targets.append(
            FacilityTarget(
                county, value if kind == "app_id" else None, value if kind == "wdid" else None
            )
        )
    return tuple(targets)


def _roster_digest(targets: Sequence[FacilityTarget]) -> str:
    entries = [
        [target.county, "app_id" if target.app_id else "wdid", target.app_id or target.wdid]
        for target in targets
    ]
    return hashlib.sha256(json.dumps(entries, separators=(",", ":")).encode()).hexdigest()


def _checkpoint(path: Path) -> sqlite3.Connection:
    db = _safe_database_path(path)
    connection = sqlite3.connect(str(db), timeout=10, isolation_level=None)
    try:
        connection.execute("PRAGMA busy_timeout=10000")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("BEGIN IMMEDIATE")
        app_id = connection.execute("PRAGMA application_id").fetchone()[0]
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        expected = {"collection_runs", "collection_steps"}
        if not tables and app_id == 0 and version == 0:
            connection.execute(
                "CREATE TABLE collection_runs (run_id TEXT PRIMARY KEY, "
                "roster_sha256 TEXT NOT NULL, journal_path TEXT NOT NULL, "
                "target_count INTEGER NOT NULL, next_index INTEGER NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE collection_steps (run_id TEXT NOT NULL, "
                "target_index INTEGER NOT NULL, "
                "observation_id INTEGER NOT NULL, response_sha256 TEXT NOT NULL, "
                "row_sha256 TEXT NOT NULL, source_key TEXT NOT NULL, "
                "PRIMARY KEY(run_id,target_index))"
            )
            connection.execute(f"PRAGMA application_id={_CHECKPOINT_APP_ID}")
            connection.execute("PRAGMA user_version=1")
        elif app_id != _CHECKPOINT_APP_ID or version != 1 or tables != expected:
            raise SmartsCollectionError("Incompatible collection checkpoint")
        if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise SmartsCollectionError("Collection checkpoint failed integrity check")
        for table, columns in {
            "collection_runs": (
                "run_id",
                "roster_sha256",
                "journal_path",
                "target_count",
                "next_index",
            ),
            "collection_steps": (
                "run_id",
                "target_index",
                "observation_id",
                "response_sha256",
                "row_sha256",
                "source_key",
            ),
        }.items():
            if (
                tuple(row[1] for row in connection.execute(f"PRAGMA table_info({table})"))
                != columns
            ):
                raise SmartsCollectionError("Collection checkpoint columns differ")
        return connection
    except Exception:
        connection.close()
        raise


def _verified_prefix(
    connection: sqlite3.Connection, run_id: str, next_index: int, journal_path: Path
) -> None:
    """A checkpoint is trusted only if every completed step still has evidence."""
    if next_index == 0:
        if (
            connection.execute(
                "SELECT 1 FROM collection_steps WHERE run_id=? LIMIT 1", (run_id,)
            ).fetchone()
            is not None
        ):
            raise SmartsCollectionError("Checkpoint has an extra step")
        return
    with sqlite3.connect(f"file:{quote(str(journal_path))}?mode=ro", uri=True) as journal:
        steps = connection.execute(
            "SELECT target_index,observation_id,response_sha256,row_sha256,source_key "
            "FROM collection_steps WHERE run_id=? ORDER BY target_index",
            (run_id,),
        ).fetchall()
        if len(steps) != next_index:
            raise SmartsCollectionError("Checkpoint has a missing or extra step")
        for expected_index, (index, observation_id, response_sha, row_sha, source_key) in enumerate(
            steps
        ):
            if index != expected_index:
                raise SmartsCollectionError("Checkpoint step order is incomplete")
            row = journal.execute(
                "SELECT response_sha256,row_sha256,source_key FROM smarts_observations WHERE id=?",
                (observation_id,),
            ).fetchone()
            if row != (response_sha, row_sha, source_key):
                raise SmartsCollectionError("Checkpoint evidence receipt is missing or changed")


def collect_roster(
    *,
    run_id: str,
    targets: Sequence[FacilityTarget],
    journal_path: Path,
    checkpoint_path: Path,
    max_requests: int,
    fetch: Callable[[FacilityTarget], SmartsPage],
) -> CollectionResult:
    """Capture up to max_requests exact records and checkpoint each committed receipt.

    A new run_id starts a new explicit sweep over the same or another roster.
    A failed lookup, invalid row, alias conflict, or write leaves the cursor at
    the failed target. The operator can correct the issue and rerun this ID.
    """
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", run_id):
        raise SmartsCollectionError("Invalid run ID")
    if type(max_requests) is not int or not 1 <= max_requests <= MAX_ROSTER:
        raise SmartsCollectionError("Request budget must be 1..25")
    if not 1 <= len(targets) <= MAX_ROSTER or any(
        not isinstance(t, FacilityTarget) for t in targets
    ):
        raise SmartsCollectionError("Invalid collection target roster")
    # Apply the same strict validation to direct Python callers.
    parse_roster(
        json.dumps(
            [
                {"county": t.county, "app_id": t.app_id}
                if t.app_id is not None
                else {"county": t.county, "wdid": t.wdid}
                for t in targets
            ]
        ).encode()
    )
    journal_path = Path(journal_path).absolute()
    checkpoint_path = Path(checkpoint_path).absolute()
    if journal_path == checkpoint_path:
        raise SmartsCollectionError("Checkpoint and evidence journal must be separate files")
    # Validate existing evidence before accepting any durable cursor. The
    # verifier also rejects a journal with missing immutability triggers.
    if journal_path.exists():
        verify_smarts_journal(journal_path)
    connection = _checkpoint(checkpoint_path)
    try:
        existing = connection.execute(
            "SELECT roster_sha256,journal_path,target_count,next_index "
            "FROM collection_runs WHERE run_id=?",
            (run_id,),
        ).fetchone()
        digest = _roster_digest(targets)
        if existing is None:
            # A new sweep cannot hide an unfinished earlier sweep.
            incomplete = connection.execute(
                "SELECT run_id FROM collection_runs WHERE next_index < target_count LIMIT 1"
            ).fetchone()
            if incomplete is not None:
                raise SmartsCollectionError("Complete or resolve the prior collection run first")
            connection.execute(
                "INSERT INTO collection_runs VALUES (?,?,?,?,0)",
                (run_id, digest, str(journal_path), len(targets)),
            )
            next_index = 0
        else:
            if existing[:3] != (digest, str(journal_path), len(targets)):
                raise SmartsCollectionError("Run ID, roster, or journal binding changed")
            next_index = existing[3]
            if type(next_index) is not int or not 0 <= next_index <= len(targets):
                raise SmartsCollectionError("Invalid checkpoint cursor")
            _verified_prefix(connection, run_id, next_index, journal_path)
        connection.commit()
        counts = {"first_observation": 0, "changed": 0, "unchanged": 0}
        requests = 0
        for index in range(next_index, min(len(targets), next_index + max_requests)):
            target = targets[index]
            page = fetch(target)
            if (
                page.resource != "facilities"
                or page.county != target.county
                or page.total != 1
                or len(page.records) != 1
            ):
                raise SmartsCollectionError("Exact lookup returned an incomplete or wrong page")
            row = page.records[0]
            if not isinstance(row, dict):
                raise SmartsCollectionError("Exact lookup returned an invalid record")
            if (target.app_id is not None and row.get("APP_ID") != target.app_id) or (
                target.wdid is not None and row.get("WDID") != target.wdid
            ):
                raise SmartsCollectionError("Exact lookup source identity drifted")
            preview = build_smarts_intake_preview(page, row)
            receipt = record_smarts_observation(journal_path, page, preview)
            # A crash here causes safe at-least-once replay on restart.
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    "INSERT INTO collection_steps VALUES (?,?,?,?,?,?)",
                    (
                        run_id,
                        index,
                        receipt.observation_id,
                        receipt.response_sha256,
                        receipt.row_sha256,
                        receipt.source_record_key,
                    ),
                )
                cursor = connection.execute(
                    "UPDATE collection_runs SET next_index=? WHERE run_id=? AND next_index=?",
                    (index + 1, run_id, index),
                )
                if cursor.rowcount != 1:
                    raise SmartsCollectionError("Checkpoint failed compare-and-advance")
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            counts[receipt.outcome] += 1
            requests += 1
        return CollectionResult(
            run_id,
            next_index + requests,
            len(targets),
            requests,
            counts["first_observation"],
            counts["changed"],
            counts["unchanged"],
        )
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Explicit bounded SMARTS facility roster collection"
    )
    parser.add_argument(
        "--roster", type=Path, required=True, help="JSON array of 1..25 exact facility IDs"
    )
    parser.add_argument("--run-id", required=True, help="Unique ID for one explicit roster sweep")
    parser.add_argument("--journal-path", type=Path, required=True)
    parser.add_argument("--checkpoint-path", type=Path, required=True)
    parser.add_argument("--max-requests", type=int, default=MAX_ROSTER)
    parser.add_argument("--execute-live", action="store_true")
    parser.add_argument("--retain-evidence", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute_live or not args.retain_evidence:
        parser.error("Collection requires both --execute-live and --retain-evidence")
    try:
        targets = parse_roster(args.roster.read_bytes())
        with httpx.Client(
            follow_redirects=False,
            timeout=httpx.Timeout(15.0, connect=5.0),
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        ) as client:
            result = collect_roster(
                run_id=args.run_id,
                targets=targets,
                journal_path=args.journal_path,
                checkpoint_path=args.checkpoint_path,
                max_requests=args.max_requests,
                fetch=lambda t: fetch_exact_facility(
                    client, county=t.county, app_id=t.app_id, wdid=t.wdid
                ),
            )
    except (
        OSError,
        SmartsCollectionError,
        SmartsApiError,
        SmartsEvidenceError,
        sqlite3.Error,
    ) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    print(json.dumps({"ok": True, **result.__dict__, "scope": "source_evidence_only"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
