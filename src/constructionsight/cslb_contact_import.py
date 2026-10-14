"""Explicit import of the freely published CSLB license-master CSV, with exact company matches."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from constructionsight import command_center_state as state
from constructionsight.contact_call_list import UNKNOWN_COMPANIES

SOURCE = "https://web.cslb.ca.gov/onlineservices/dataportal/ContractorList"
ALIASES = {
    "license": ("licensenumber", "licenseno", "license", "licno"),
    "company": ("businessname", "companyname"),
    "phone": ("businessphone", "businessphonenumber", "phonenumber", "phone"),
}


def import_master(
    path: Path,
    expected_sha256: str,
    rows: list[dict[str, Any]],
    directory: Path,
    *,
    apply: bool = False,
) -> dict[str, Any]:
    raw = path.read_bytes()
    if len(raw) > 100_000_000 or hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("CSLB file hash mismatch or size limit exceeded")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    normalized = {re.sub(r"[^a-z0-9]", "", str(h).casefold()): h for h in reader.fieldnames or []}
    headers = {
        k: next((normalized[a] for a in aliases if a in normalized), None)
        for k, aliases in ALIASES.items()
    }
    if any(h is None for h in headers.values()):
        raise ValueError("CSLB CSV needs license number, business name and business phone fields")
    companies: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in reader:
        company = str(item.get(headers["company"] or "") or "").strip()
        license_number = str(item.get(headers["license"] or "") or "").strip()
        phone = str(item.get(headers["phone"] or "") or "").strip()
        if re.fullmatch(r"\d{1,8}", license_number) and 7 <= len(re.sub(r"\D", "", phone)) <= 15:
            companies[" ".join(company.casefold().split())].append(
                {"company": company, "license": license_number, "phone": phone}
            )
    results = []
    for row in rows:
        name = " ".join(str(row.get("DEVELOPER_NAME") or "").casefold().split())
        matches = companies.get(name, []) if name not in UNKNOWN_COMPANIES else []
        licenses = {m["license"] for m in matches}
        if not matches:
            results.append({"source_key": row["source_key"], "status": "no_match"})
            continue
        if len(licenses) != 1 or len({m["phone"] for m in matches}) != 1:
            results.append({"source_key": row["source_key"], "status": "ambiguous"})
            continue
        match = matches[0]
        contact = {
            "name": "",
            "role": "License-reported business phone; company match unverified",
            "company": match["company"],
            "phone": match["phone"],
            "email": "",
            "source": (
                f"CSLB published license master; license {match['license']}; "
                f"CSV SHA-256 {expected_sha256}; {SOURCE}"
            ),
        }
        if apply:
            state.save_contact(directory, row["source_key"], contact)
        results.append(
            {
                "source_key": row["source_key"],
                "status": "imported" if apply else "candidate",
                "contact": contact,
                "confidence": 0.4,
                "verified": False,
            }
        )
    return {
        "source_url": SOURCE,
        "csv_sha256": expected_sha256,
        "results": results,
        "method": (
            "Exact unambiguous reported business name; "
            "no legal entity or purchasing-authority verification"
        ),
        "emails_provided": False,
        "applied": apply,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    snapshot = json.loads(args.snapshot.read_text())
    report = import_master(args.csv, args.sha256, snapshot["rows"], args.data_dir, apply=args.apply)
    args.report.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
