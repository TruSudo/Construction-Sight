"""Read existing CEQA/permit intelligence in the native SMARTS Command Center.

This module bridges *views*, not identities or storage. Source-family keys,
provenance, and limitations remain separate from SMARTS commercial leads.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from constructionsight.operator_dashboard import build_dashboard_snapshot
from constructionsight.operator_entity_index import build_entity_index
from constructionsight.storage.operator_read_store import create_operator_read_engine


def source_intelligence_overview(database_path: Path | None) -> dict[str, Any]:
    """Return one bounded, read-only snapshot; never initialize a database.

    Without an explicitly selected database, counts are unknown (not zero).
    An invalid or incompatible selected database raises instead of fabricating
    an empty or complete inventory.
    """

    if database_path is None:
        return {
            "state": "unconfigured",
            "read_only": True,
            "records": None,
            "entities": None,
            "limitations": [
                "No existing CEQA/permit database was selected.",
                "SMARTS and government records have not been joined or verified.",
            ],
        }

    engine = create_operator_read_engine(database_path)
    try:
        with Session(engine, autoflush=False) as session:
            records = build_dashboard_snapshot(session, limit=25, offset=0)
            entities = build_entity_index(session)
            return {
                "state": "connected",
                "read_only": True,
                "records": records.model_dump(mode="json"),
                "entities": entities.model_dump(mode="json"),
                "limitations": [
                    "Government source records are not deduplicated SMARTS leads.",
                    "Matching names, coordinates or parcels do not verify site identity.",
                    "Displayed records and entity keys are bounded source-claimed views.",
                    "No outreach, source write, or bid is authorized by this view.",
                ],
            }
    finally:
        engine.dispose()
