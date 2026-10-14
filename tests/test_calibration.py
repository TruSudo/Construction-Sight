from pathlib import Path

import pytest

from constructionsight import calibration
from constructionsight import command_center_state as state


def test_historical_cohorts_and_unknown_win_rate() -> None:
    rows = [
        {
            "source_key": "a",
            "project_type": "industrial",
            "security_fit": 20,
            "feedback": {
                "status": "Won",
                "score_at_update": 75,
                "project_type_at_update": "commercial",
            },
        },
        {
            "source_key": "b",
            "project_type": "industrial",
            "security_fit": 80,
            "feedback": {"status": "New"},
        },
    ]
    report = calibration.report(rows)
    assert report[0]["project_type"] == "commercial"
    assert report[0]["score_band"] == "60–100"
    assert report[0]["win_rate"] == 1
    assert report[1]["win_rate"] is None
    assert report[0]["source_keys"] == ["a"]
    assert report[1]["statuses"]["Lost"] == 0


def test_reviewed_weights_atomic_changelog_and_stale_review(tmp_path: Path) -> None:
    before = state.settings(tmp_path)["weights"]
    payload = {
        "weights": {**before, "industrial": 41},
        "expected_digest": state.fingerprint(before),
        "reason": "Reviewed outcomes",
        "reviewed": True,
    }
    with pytest.raises(ValueError):
        calibration.apply(tmp_path, {**payload, "reviewed": False})
    result = calibration.apply(tmp_path, payload)
    assert result["weights"]["industrial"] == 41
    change = result["changes"][0]
    assert change["before"] == before and change["reason"] == "Reviewed outcomes"
    assert change["after_digest"] == state.fingerprint(payload["weights"])
    with pytest.raises(ValueError, match="changed since review"):
        calibration.apply(tmp_path, payload)
    assert len(calibration.changes(tmp_path)) == 1
    state.save_settings(tmp_path, {"weights": before})
    assert len(calibration.changes(tmp_path)) == 2
