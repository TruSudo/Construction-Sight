"""Explicit, read-only SMARTS to ConstructionSight intake/site preview.

Example:
python -m constructionsight.smarts_intake_cli --county Riverside --app-id 600752 --execute-live
"""

from __future__ import annotations

import argparse
import json

import httpx

from constructionsight.smarts_api import (
    COUNTIES,
    USER_AGENT,
    SmartsApiError,
    fetch_exact_facility,
)
from constructionsight.smarts_intake_bridge import build_smarts_intake_preview


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect one SMARTS facility using existing ConstructionSight intake"
    )
    parser.add_argument("--county", required=True, choices=COUNTIES)
    identity = parser.add_mutually_exclusive_group(required=True)
    identity.add_argument("--app-id", help="Numeric SMARTS APP_ID; NA is not usable")
    identity.add_argument("--wdid", help="Exact SMARTS WDID, including internal spaces")
    parser.add_argument("--execute-live", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute_live:
        parser.error("Network execution requires --execute-live")
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
    except SmartsApiError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1

    # Strictly a derived review artifact. Contact email, phone and other raw
    # fields are not copied from SMARTS into the output or the project graph.
    print(json.dumps(
        {"ok": True, "preview": preview.model_dump(mode="json")},
        indent=2, ensure_ascii=False,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
