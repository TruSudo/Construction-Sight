"""Explicit bulk contact import and company call lists; no messages or guessed identities."""

from __future__ import annotations

import argparse
import csv
import io
import json
import sqlite3
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from constructionsight import command_center_state as state
from constructionsight.smarts_evidence_ledger import verify_smarts_journal

COLUMNS = [
    "score",
    "project",
    "address",
    "city",
    "company",
    "contact name",
    "role",
    "phone",
    "email",
    "source",
    "confidence",
    "status",
]
CONSULTANT_TERMS = (
    "stormwater",
    "swppp",
    "qsd",
    "qsp",
    "consultant",
    "environmental",
    "hydrosolutions",
    "kimley-horn",
    "compliance specialist",
)
UNKNOWN_COMPANIES = {
    "",
    "na",
    "n/a",
    "unknown",
    "none",
    "null",
    "tbd",
    "owner",
    "private owner",
    "—",
}


def contact_view(contact: dict[str, Any]) -> dict[str, Any]:
    text = " ".join(
        str(contact.get(k) or "") for k in ("name", "company", "role", "email")
    ).casefold()
    flags = [word for word in CONSULTANT_TERMS if word in text]
    source = str(contact.get("source") or "")
    kind = (
        "developer"
        if "source-reported developer contact" in source
        else ("site" if "source-reported site contact" in source else "other")
    )
    return {
        **contact,
        "contact_kind": kind,
        "confidence": (0.4 if source.startswith("CSLB") else 0.5) if source else 0.0,
        "confidence_basis": (
            "Heuristic source-reported contact; identity and purchasing authority unverified"
        ),
        "possible_stormwater_consultant": bool(flags),
        "consultant_cues": flags,
    }


def contact_coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    report: dict[str, Any] = {
        "total_leads": len(rows),
        "email": 0,
        "phone": 0,
        "both": 0,
        "email_only": 0,
        "phone_only": 0,
        "neither": 0,
        "developer_contacts": 0,
        "site_contacts": 0,
        "other_contacts": 0,
        "possible_consultant_contacts": 0,
        "possible_consultant_leads": 0,
    }
    for row in rows:
        contacts = [
            contact_view(c)
            for c in row.get("sourced_contacts", [])
            if c.get("source") and (c.get("phone") or c.get("email"))
        ]
        email, phone = any(c.get("email") for c in contacts), any(c.get("phone") for c in contacts)
        report["email"] += email
        report["phone"] += phone
        report["both"] += email and phone
        report["email_only"] += email and not phone
        report["phone_only"] += phone and not email
        report["neither"] += not email and not phone
        report["possible_consultant_leads"] += any(
            c["possible_stormwater_consultant"] for c in contacts
        )
        for contact in contacts:
            for kind in contact.get("source_kinds", [contact["contact_kind"]]):
                report[kind + "_contacts"] += 1
            report["possible_consultant_contacts"] += contact["possible_stormwater_consultant"]
    return report


def _bulk_import(directory: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Verify one immutable journal snapshot, then bind each import to original row/page hashes."""
    results = []
    # Snapshot makes the journal verification and per-lead reads refer to exactly
    # the same bytes even if another local process appends a capture concurrently.
    with tempfile.TemporaryDirectory(prefix="cs-contact-proof-") as temporary:
        proof = Path(temporary) / "evidence.sqlite3"
        with (
            sqlite3.connect(f"file:{directory / 'evidence.sqlite3'}?mode=ro", uri=True) as original,
            sqlite3.connect(proof) as copied,
        ):
            original.backup(copied)
        proof.chmod(0o600)
        try:
            verified = verify_smarts_journal(proof, read_only=True)
        except (ValueError, sqlite3.Error) as exc:
            return {
                "results": [
                    {"source_key": r["source_key"], "status": "error", "error": str(exc)}
                    for r in rows
                ],
                "journal_verified": False,
                "status_counts": {"error": len(rows)},
            }
        with sqlite3.connect(f"file:{proof}?mode=ro", uri=True) as journal:
            for row in rows:
                try:
                    found = journal.execute(
                        "SELECT raw_response,request_url FROM smarts_observations "
                        "WHERE source_key=? AND row_sha256=? AND response_sha256=? "
                        "ORDER BY id DESC LIMIT 1",
                        (row["source_key"], row.get("row_sha256"), row.get("response_sha256")),
                    ).fetchone()
                    if found is None:
                        raise ValueError("Original hash-bound source observation is unavailable")
                    imported = state._import_verified_contact_body(
                        directory, row, found[0], source_url=found[1]
                    )
                    contacts = [contact_view(c) for c in imported["contacts"]]
                    results.append(
                        {
                            "source_key": row["source_key"],
                            "status": "imported" if contacts else "no_contact",
                            "contact_count": len(contacts),
                            "reported_contact_kinds": imported["reported_contact_kinds"],
                            "contacts": contacts,
                            "response_sha256": row["response_sha256"],
                        }
                    )
                except (ValueError, KeyError, StopIteration, sqlite3.Error) as exc:
                    results.append(
                        {"source_key": row["source_key"], "status": "error", "error": str(exc)}
                    )
    report = {
        "results": results,
        "journal_verified": True,
        "journal_counts": verified,
        "status_counts": dict(Counter(r["status"] for r in results)),
    }
    return report


def bulk_import(directory: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        report = _bulk_import(directory, rows)
    except (OSError, ValueError, sqlite3.Error) as exc:
        report = {
            "results": [
                {"source_key": r["source_key"], "status": "error", "error": str(exc)} for r in rows
            ],
            "journal_verified": False,
            "status_counts": {"error": len(rows)},
        }
    temporary_path = directory / "bulk-contact-results.json.tmp"
    temporary_path.write_text(json.dumps(report, indent=2) + "\n")
    temporary_path.replace(directory / "bulk-contact-results.json")
    return report


def company_call_list(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for row in sorted(
        rows, key=lambda r: (r.get("readiness") != "ready", -r.get("security_fit", 0))
    ):
        if (
            row.get("do_not_contact")
            or row.get("hidden")
            or row.get("feedback", {}).get("status") == "Not a fit"
            or row.get("readiness") not in ("ready", "review")
        ):
            continue
        contacts = [
            contact_view(c)
            for c in row.get("sourced_contacts", [])
            if c.get("source") and (c.get("email") or c.get("phone"))
        ]
        if not contacts:
            continue
        company = str(row.get("DEVELOPER_NAME") or "").strip()
        if company.casefold() in UNKNOWN_COMPANIES:
            company = next(
                (
                    str(c.get("company") or "").strip()
                    for c in contacts
                    if str(c.get("company") or "").strip().casefold() not in UNKNOWN_COMPANIES
                ),
                "—",
            )
        key = (
            " ".join(company.casefold().split()) if company != "—" else "site:" + row["source_key"]
        )
        group = groups.setdefault(
            key,
            {
                "score": row.get("security_fit"),
                "company": company,
                "status": "Ready for Outreach" if row["readiness"] == "ready" else "In Review",
                "sites": [],
                "contacts": [],
            },
        )
        group["score"] = max(group.get("score") or 0, row.get("security_fit") or 0)
        group["sites"].append(row)
        for contact in contacts:
            signature = tuple(contact.get(k) for k in ("name", "role", "email", "phone", "source"))
            if not any(
                tuple(c.get(k) for k in ("name", "role", "email", "phone", "source")) == signature
                for c in group["contacts"]
            ):
                group["contacts"].append(contact)
    output = []
    for group in groups.values():
        sites, contacts = group.pop("sites"), group.pop("contacts")

        def joined(key: str, items: list[dict[str, Any]]) -> str:
            return "\n".join(dict.fromkeys(str(item.get(key) or "—") for item in items))

        roles = [
            " ".join(
                filter(
                    None,
                    [
                        str(c.get("role") or "—"),
                        "[possible stormwater consultant]"
                        if c["possible_stormwater_consultant"]
                        else "",
                    ],
                )
            )
            for c in contacts
        ]
        output.append(
            {
                **group,
                "project": joined("SITE_NAME", sites),
                "address": joined("SITE_ADDRESS", sites),
                "city": joined("SITE_CITY", sites),
                "contact name": "\n".join(str(c.get("name") or "—") for c in contacts),
                "role": "\n".join(roles),
                "phone": "\n".join(str(c.get("phone") or "—") for c in contacts),
                "email": "\n".join(str(c.get("email") or "—") for c in contacts),
                "source": "\n".join(str(c.get("source") or "—") for c in contacts),
                "confidence": min(c["confidence"] for c in contacts),
                "site_count": len(sites),
            }
        )
    return output


def call_list_csv(rows: list[dict[str, Any]]) -> bytes:
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=COLUMNS)
    writer.writeheader()
    for row in company_call_list(rows):
        record = {}
        for key in COLUMNS:
            value = str(row.get(key) if row.get(key) is not None else "—")
            record[key] = "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value
        writer.writerow(record)
    return out.getvalue().encode("utf-8-sig")


def main() -> None:
    from constructionsight.live_command_center import projection

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--import-all", action="store_true")
    parser.add_argument("--export", type=Path)
    args = parser.parse_args()
    snapshot = json.loads(args.snapshot.read_text())
    if args.import_all:
        imported = bulk_import(args.data_dir, snapshot["rows"])
        print(json.dumps(imported.get("status_counts", {})))
    rows = projection(snapshot, args.data_dir)["rows"]
    print(json.dumps(contact_coverage(rows)))
    if args.export:
        args.export.write_bytes(call_list_csv(rows))


if __name__ == "__main__":
    main()
