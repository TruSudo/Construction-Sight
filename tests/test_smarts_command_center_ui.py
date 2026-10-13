"""SMARTS source-change review integrates without redesign or commercial shortcuts."""

from __future__ import annotations

from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / "src" / "constructionsight"


def test_smarts_change_review_preserves_approved_command_center_structure() -> None:
    html = (ASSETS / "operator_command_center.html").read_text(encoding="utf-8")
    js = (ASSETS / "operator_command_center.js").read_text(encoding="utf-8")
    assert 'data-section="sources"' in html
    assert "CONSTRUCTION" in html and "SIGHT" in html
    assert "function renderSmartsStatus(data)" in js
    assert "async function showSmartsChanges(offset=0)" in js
    assert 'id="smarts-change-county"' in js
    assert 'id="smarts-change-results"' in js
    assert 'id="smarts-review-load"' in js
    assert 'fetchJson("/api/smarts-changes?"' in js
    assert "data.verified_private_history!==data.configured" in js
    assert "data.missing_is_deletion!==false" in js
    assert "data.source_identity_is_project_identity!==false" in js
    assert "data.parcel_or_project_matches_verified!==false" in js
    assert "data.outreach_authorized!==false" in js
    assert "data.bid_authorized!==false" in js
    assert "item.source_scoped_candidate_only!==true" in js
    assert "item.original_file_sha256" in js
    assert 'escapeText(item.source_key)' in js
    assert 'data.returned>10' in js
    assert 'showSmartsChanges(offset+10)' in js
    assert "Missing-from-new does not mean deleted" in js
    assert "No parcel identity, construction phase" in js
    assert "This operator never acquires SMARTS data or schedules polling" in js
    assert "fetch(\"https://publish.data.ca.gov" not in js
