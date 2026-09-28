"""Bounded, read-only source-family revision signal for the local GUI.

This lightweight change indicator does not fetch remote sources or certify project activity.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from constructionsight.storage.domain_orm import CeqaDomainRecord, PermitDomainRecord


def build_source_revision_snapshot(session: Session) -> dict[str, Any]:
    """Return a digest of persisted source counts, row identities and update markers."""

    families: dict[str, dict[str, object]] = {}
    for label, row_type in (
        ("ceqa", CeqaDomainRecord),
        ("permit", PermitDomainRecord),
    ):
        count, highest_id, latest_update = session.execute(
            select(
                func.count(row_type.id),
                func.max(row_type.id),
                func.max(row_type.updated_at),
            )
        ).one()
        families[label] = {
            "record_count": int(count),
            "highest_row_id": highest_id,
            "latest_updated_at": (
                latest_update.isoformat()
                if hasattr(latest_update, "isoformat")
                else str(latest_update) if latest_update is not None else None
            ),
        }
    encoded = json.dumps(families, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "revision_identity": hashlib.sha256(encoded).hexdigest(),
        "source_families": families,
        "read_only": True,
        "live_collection_enabled": False,
        "meaning": (
            "Local SQLite source-record change indicator, not an independent "
            "construction activity signal or remote acquisition status."
        ),
    }
