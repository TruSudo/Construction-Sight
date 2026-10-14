"""Exercise the real retained reference against benign resampling and injected defects."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_recorded_calibration_rejects_single_missing_controls(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "tests/visual/calibrate.py"), str(tmp_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads((tmp_path / "calibration-results.json").read_text())
    cases = {r["challenge"]: r for r in report["challenges"]}
    assert cases["identity"]["passed"]
    assert cases["resampled_75_percent"]["passed"]
    for name in ("shifted_3px", "wrong_amber_color", "missing_element_per_region"):
        assert not cases[name]["passed"]
        assert not any(cases[name]["regions"].values())
    for region in report["settings"]["thresholds"]:
        case = cases["missing_" + region]
        assert not case["passed"]
        assert case["regions"][region] is False
        assert sum(case["regions"].values()) == 7
