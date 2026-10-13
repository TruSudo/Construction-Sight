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


def test_smarts_source_event_parcel_review_requires_exact_evidence_and_no_authority() -> None:
    js = (ASSETS / "operator_command_center.js").read_text(encoding="utf-8")
    assert "async function showSmartsParcelCandidates(item, index, token)" in js
    assert 'fetchJson("/api/smarts-parcel-candidates?"' in js
    assert "snapshot_id:String(item.snapshot_id),source_key:item.source_key" in js
    assert "data.source_history_integrity_verified!==true" in js
    assert "data.parcel_identity_verified!==false" in js
    assert "data.project_identity_verified!==false" in js
    assert "data.construction_activity_verified!==false" in js
    assert "data.lead_created!==false" in js
    assert "data.outreach_authorized!==false" in js
    assert "data.bid_authorized!==false" in js
    assert "source_apn_missing" in js
    assert "conflicting_source_apns" in js
    assert "parcel_candidate_ambiguous" in js
    assert "historical_snapshot_requires_current_review" in js
    assert "Independent assessor, permit and location evidence" in js
    assert "data-smarts-parcel-index" in js
