"""One-call offline SMARTS facility version and compliance evidence review.

Operator-controlled local inputs only. Results are deliberately restricted to
source-scoped candidates, with no graph writes, automated outreach or promotions.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from constructionsight.smarts_inspection_review import (
    build_inspection_summary,
    review_inspections,
)
from constructionsight.smarts_snapshot_diff import (
    COUNTIES,
    SmartsSnapshotError,
    build_review_summary,
    load_facility_snapshot,
    reconcile_snapshots,
)


def prepare_source_review(
    *,
    county: str,
    previous: Path,
    current: Path,
    inspections: Path | None = None,
) -> dict[str, Any]:
    """Return a read-only, provenance-linked operator review envelope."""
    inputs = [previous, current, *([inspections] if inspections is not None else [])]
    if len({path.resolve() for path in inputs}) != len(inputs):
        raise SmartsSnapshotError("Each source input must be a separate retained file")
    prior = load_facility_snapshot(previous, county=county)
    present = load_facility_snapshot(current, county=county)
    difference = reconcile_snapshots(prior, present)
    facility_summary = build_review_summary(prior, present, difference)
    inspection_summary = None
    if inspections is not None:
        inspection_summary = build_inspection_summary(
            present,
            review_inspections(inspections, facilities=present),
        )
    return {
        "ok": True,
        "mode": "smarts_offline_review",
        "county": county,
        "facility_change_review": facility_summary,
        "inspection_review": inspection_summary,
        "human_review_required": True,
        "source_maturity": "unverified",
        "site_identity": "source_scoped_only",
        "physical_construction_verified": False,
        "lead_readiness": "blocked_pending_independent_verification",
        "application_graph_writes": False,
        "outreach": False,
        "bid_actions": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="One-call offline SMARTS facility and inspection evidence review"
    )
    parser.add_argument("--county", choices=COUNTIES, required=True)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--inspections", type=Path)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(
            prepare_source_review(
                county=args.county,
                previous=args.previous,
                current=args.current,
                inspections=args.inspections,
            ),
            indent=2,
        ))
    except SmartsSnapshotError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
