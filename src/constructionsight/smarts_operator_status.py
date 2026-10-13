"""Read-only, privacy-preserving SMARTS evidence status for the local operator.

This is an evidence-journal projection, not a source freshness or commercial
readiness determination. It never reads a remote endpoint, reveals raw rows,
promotes a project, or mutates the private journal.
"""

from __future__ import annotations

from pathlib import Path

from constructionsight.smarts_evidence_ledger import verify_smarts_journal

SCHEMA_VERSION = "constructionsight.smarts_operator_status.v1"


def build_smarts_operator_status(journal_path: Path | None) -> dict[str, object]:
    """Expose verified aggregate observations from an explicitly selected journal."""
    configured = journal_path is not None
    counts = (
        verify_smarts_journal(journal_path, read_only=True)
        if journal_path is not None
        else {"observations": 0, "versions": 0, "sources": 0}
    )
    observations = counts["observations"]
    versions = counts["versions"]
    sources = counts["sources"]
    if not (0 <= sources <= versions <= observations):
        raise ValueError("SMARTS journal summary is inconsistent")
    return {
        "schema_version": SCHEMA_VERSION,
        "configured": configured,
        "read_only": True,
        "network_executed": False,
        "journal_mutated": False,
        "source_rows_exposed": False,
        "journal_integrity_verified": configured,
        "observations": observations,
        "semantic_versions": versions,
        "source_identities": sources,
        "live_collection_enabled": False,
        "scheduled_collection_enabled": False,
        "county_coverage_verified": False,
        "source_freshness_verified": False,
        "parcel_or_project_matches_verified": False,
        "lead_readiness_authorized": False,
        "outreach_authorized": False,
        "bid_authorized": False,
    }
