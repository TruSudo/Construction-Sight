"""Bulk imports preserve evidence gates and call-list grouping cannot bypass DNC."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

import pytest

from constructionsight import command_center_state as state
from constructionsight.contact_call_list import bulk_import, call_list_csv, contact_coverage
from constructionsight.cslb_contact_import import import_master
from constructionsight.live_command_center import projection
from constructionsight.smarts_active import collect_active
from tests.test_live_command_center import client_for


def test_bulk_proof_import_is_idempotent_and_records_one_result_per_lead(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests import test_live_command_center as legacy

    old = legacy.row
    monkeypatch.setattr(
        legacy,
        "row",
        lambda i: {
            **old(i),
            "DEVELOPER_EMAIL": "person@example.test",
            "DEVELOPER_PHONE": "9515550123",
            "DEVELOPER_CONTACT_FIRST_NAME": "Source",
            "DEVELOPER_CONTACT_LAST_NAME": "Contact",
            "SITE_EMAIL": "person@example.test",
            "SITE_PHONE": "9515550123",
        },
    )
    with client_for({"San Bernardino": [], "Riverside": [legacy.row(1)]}) as client:
        snapshot = collect_active(client, tmp_path)
    rows = snapshot["rows"]
    bad = {**rows[0], "source_key": "unknown-source", "response_sha256": "0" * 64}
    report = bulk_import(tmp_path, [*rows, bad])
    assert report["journal_verified"]
    assert [r["status"] for r in report["results"]] == ["imported", "error"]
    assert len(json.loads((tmp_path / "bulk-contact-results.json").read_text())["results"]) == 2
    bulk_import(tmp_path, rows)
    projected = projection(snapshot, tmp_path)["rows"]
    assert len(projected[0]["sourced_contacts"]) == 1
    coverage = contact_coverage(projected)
    assert (
        coverage["both"] == 1
        and coverage["developer_contacts"] == 1
        and coverage["site_contacts"] == 1
    )
    assert rows[0]["response_sha256"] in projected[0]["sourced_contacts"][0]["source"]


def test_missing_journal_produces_errors_without_contacts(tmp_path: Path) -> None:
    report = bulk_import(tmp_path, [{"source_key": "one"}, {"source_key": "two"}])
    assert report["status_counts"] == {"error": 2}
    assert [r["source_key"] for r in report["results"]] == ["one", "two"]
    assert not report["journal_verified"]


def test_call_list_order_company_dedupe_dnc_and_consultant_flags() -> None:
    contact = {
        "name": "Sourced consultant",
        "role": "SWPPP QSD",
        "phone": "9515550123",
        "email": "a@example.test",
        "source": "SMARTS source-reported developer contact",
    }

    def lead(key: str, company: str, ready: str = "review", dnc: bool = False) -> dict:
        return {
            "source_key": key,
            "DEVELOPER_NAME": company,
            "SITE_NAME": "Site " + key,
            "SITE_ADDRESS": "100 Main St",
            "SITE_CITY": "Perris",
            "security_fit": 60,
            "readiness": ready,
            "sourced_contacts": [contact],
            "do_not_contact": dnc,
        }

    rows = [
        lead("a", "Company A"),
        lead("b", "Company A"),
        lead("c", "Company B", "ready"),
        lead("d", "Blocked Company", dnc=True),
    ]
    exported = list(csv.DictReader(io.StringIO(call_list_csv(rows).decode("utf-8-sig"))))
    assert len(exported) == 2 and exported[0]["status"] == "Ready for Outreach"
    assert exported[1]["project"] == "Site a\nSite b"
    assert "possible stormwater consultant" in exported[1]["role"]
    assert "Blocked Company" not in str(exported)


def test_cslb_preview_hash_ambiguity_and_no_guessed_email(tmp_path: Path) -> None:
    path = tmp_path / "master.csv"
    path.write_text("License Number,Business Name,Business Phone\n123,Company A,9515550123\n")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    rows = [{"source_key": "a", "DEVELOPER_NAME": "Company A"}]
    report = import_master(path, digest, rows, tmp_path)
    assert report["results"][0]["status"] == "candidate"
    assert not report["applied"] and report["results"][0]["contact"]["email"] == ""
    assert not (tmp_path / "workflow.sqlite3").exists()
    import_master(path, digest, rows, tmp_path, apply=True)
    with state.connect(tmp_path) as db:
        assert db.execute("SELECT COUNT(*) FROM cc_contacts").fetchone()[0] == 1
    with pytest.raises(ValueError, match="hash mismatch"):
        import_master(path, "0" * 64, rows, tmp_path)
    path.write_text(path.read_text() + "124,Company A,9515550144\n")
    assert (
        import_master(path, hashlib.sha256(path.read_bytes()).hexdigest(), rows, tmp_path)[
            "results"
        ][0]["status"]
        == "ambiguous"
    )
