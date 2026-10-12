"""Explicit SMARTS exact-record preview with optional private evidence journal.

Preview (never persists):
python -m constructionsight.smarts_intake_cli --county Riverside --app-id 600752 --execute-live

Opt-in evidence retention requires an already existing owner-only journal directory:
python -m constructionsight.smarts_intake_cli --county Riverside --app-id 600752 \
    --execute-live --retain-evidence --journal-path private/evidence.sqlite3
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx

from constructionsight.smarts_api import (
    COUNTIES,
    USER_AGENT,
    SmartsApiError,
    fetch_exact_facility,
)
from constructionsight.smarts_evidence_ledger import (
    SmartsEvidenceError,
    record_smarts_observation,
)
from constructionsight.smarts_intake_bridge import build_smarts_intake_preview


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect a SMARTS facility through existing ConstructionSight intake"
    )
    parser.add_argument("--county", required=True, choices=COUNTIES)
    identity = parser.add_mutually_exclusive_group(required=True)
    identity.add_argument("--app-id", help="Numeric SMARTS APP_ID; NA is not usable")
    identity.add_argument("--wdid", help="Exact SMARTS WDID, including internal spaces")
    parser.add_argument("--execute-live", action="store_true")
    parser.add_argument(
        "--retain-evidence", action="store_true",
        help="Explicitly retain original source bytes in a private append-only evidence journal",
    )
    parser.add_argument("--journal-path", type=Path, help="Private .sqlite3 evidence journal path")
    args = parser.parse_args(argv)
    if not args.execute_live:
        parser.error("Network execution requires --execute-live")
    if args.retain_evidence != (args.journal_path is not None):
        parser.error("--retain-evidence and --journal-path must be provided together")
    try:
        with httpx.Client(
            follow_redirects=False,
            timeout=httpx.Timeout(15.0, connect=5.0),
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        ) as client:
            page = fetch_exact_facility(
                client, county=args.county, app_id=args.app_id, wdid=args.wdid
            )
        preview = build_smarts_intake_preview(page, page.records[0])
        result: dict[str, object] = {
            "ok": True,
            "preview": preview.model_dump(mode="json"),
        }
        if args.journal_path is not None:
            receipt = record_smarts_observation(args.journal_path, page, preview)
            result["evidence_journal"] = {
                "source_record_key": receipt.source_record_key,
                "observation_id": receipt.observation_id,
                "semantic_version": receipt.version,
                "outcome": receipt.outcome,
                "raw_response_sha256": receipt.response_sha256,
                "record_sha256": receipt.row_sha256,
                "write_scope": "private_source_evidence_only",
            }
    except (SmartsApiError, SmartsEvidenceError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1

    # The retained raw bytes may contain contact information; they stay in the
    # owner-only sidecar DB and are never displayed or added to project state.
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
