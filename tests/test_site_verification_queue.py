from pathlib import Path

import pytest

from constructionsight import command_center_state as state
from constructionsight.live_command_center import projection


def snapshot() -> dict:
    return {
        "rows": [
            {
                "source_key": "site",
                "SITE_NAME": "Warehouse",
                "SITE_ADDRESS": "100 Main St",
                "SITE_CITY": "Perris",
                "SITE_COUNTY": "Riverside",
                "row_sha256": "a" * 64,
                "CONSTRUCTION_COMMENCEMENT_DATE": "2000-01-01",
                "COMPLETE_PROJECT_DATE": "2099-01-01",
            }
        ],
        "captured_at": "2026-10-15",
        "requests": 0,
        "totals": {},
        "baseline": True,
        "missing_count": 0,
    }


def test_review_requires_evidence_then_persists_and_invalidates_on_site_change(
    tmp_path: Path,
) -> None:
    data = snapshot()
    state.save_contact(tmp_path, "site", {"email": "actual@example.test", "source": "Demo fixture"})
    lead = projection(data, tmp_path)["rows"][0]
    assert lead["readiness"] == "review"
    review = {
        "verified": True,
        "source": "https://county.example.test/permit/123",
        "note": "Demo evidence: checked parcel address and site identity.",
    }
    for invalid in (
        {**review, "source": ""},
        {**review, "note": "short"},
        {**review, "source": "https://user:password@example.test/"},
        {**review, "verified": "true"},
    ):
        with pytest.raises(ValueError):
            state.review_site(tmp_path, lead, invalid)
    state.review_site(tmp_path, lead, review)
    checked = projection(data, tmp_path)["rows"][0]
    assert checked["site_verification"]["source"] == review["source"]
    assert checked["site_verification"]["reviewer"] == "—"
    assert checked["readiness"] == "ready"
    state.control(tmp_path, "site", {"dnc": True})
    assert projection(data, tmp_path)["rows"][0]["readiness"] == "not_ready"
    data["rows"][0]["row_sha256"] = "b" * 64
    changed = projection(data, tmp_path)["rows"][0]
    assert changed["site_verification"]["stale"] and not changed["site_verified"]
    assert any(e["kind"] == "site_review" for e in state.activity(tmp_path, "site"))
