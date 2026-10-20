"""Read-only native review of one original bounded SMARTS facility roster.

The exact roster belongs to the original small, county-scoped source collector.
No collection, checkpoint initialization, journal creation or timer is performed.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from constructionsight.smarts_collection import _roster_digest, parse_roster
from constructionsight.smarts_evidence_ledger import verify_smarts_journal
from constructionsight.storage.runtime_artifacts import read_runtime_artifact

_SCHEMA = "constructionsight.native-original-smarts-roster-audit/v1"
_MAX_ROSTER_BYTES = 8_192


def original_retained_smarts_roster_audit(
    roster_file: Path | None,
    journal_path: Path | None,
) -> dict[str, Any]:
    """Inspect the original roster and optionally verify an existing source journal."""
    if roster_file is None:
        return {
            "schema_version": _SCHEMA,
            "available": False,
            "configured": False,
            "read_only": True,
            "network_executed": False,
            "collector_executed": False,
            "schedule_activated": False,
            "reason": (
                "Select --operator-smarts-collection-roster at launch to review "
                "an existing exact, bounded original SMARTS facility roster."
            ),
        }
    raw = read_runtime_artifact(roster_file, max_bytes=_MAX_ROSTER_BYTES)
    targets = parse_roster(raw)
    journal_status = "not_configured"
    if journal_path is not None:
        if journal_path.is_symlink() or not journal_path.is_file():
            raise ValueError("retained original SMARTS journal must be an existing file")
        verify_smarts_journal(journal_path)
        journal_status = "original_integrity_verified"
    rows = [
        {
            "county": target.county,
            "identifier_kind": "APP_ID" if target.app_id is not None else "WDID",
            "exact_identifier": target.app_id or target.wdid,
        }
        for target in targets
    ]
    if read_runtime_artifact(roster_file, max_bytes=_MAX_ROSTER_BYTES) != raw:
        raise ValueError("original SMARTS roster changed during source review")
    return {
        "schema_version": _SCHEMA,
        "available": True,
        "configured": True,
        "roster_sha256": hashlib.sha256(raw).hexdigest(),
        "original_roster_digest": _roster_digest(targets),
        "roster_count": len(targets),
        "county_scope": sorted({target.county for target in targets}),
        "exact_facility_targets": rows,
        "source_journal_status": journal_status,
        "original_roster_integrity_verified": True,
        "original_source_journal_integrity_verified": (
            journal_status == "original_integrity_verified"
        ),
        "read_only": True,
        "network_executed": False,
        "collector_executed": False,
        "checkpoint_created": False,
        "journal_mutated": False,
        "schedule_activated": False,
        "live_source_access_authorized": False,
        "commercial_authority_granted": False,
        "meaning": (
            "Offline original 1–25 exact county-scoped facility roster review. "
            "A valid roster or journal does not authorize a CKAN GET, "
            "collection checkpoint, scheduled run, source promotion, or outreach."
        ),
    }
