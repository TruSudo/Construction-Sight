from __future__ import annotations

import re
import tomllib
from pathlib import Path


def _active_defect_count() -> int:
    payload = tomllib.loads(Path("governance/active_defects.toml").read_text(encoding="utf-8"))
    defects = payload.get("defects", [])
    assert isinstance(defects, list)
    return len(defects)


def _documented_count(path: str) -> int:
    text = Path(path).read_text(encoding="utf-8")
    match = re.search(r"Current active-defect count: \*\*(\d+)\*\*\.", text)
    assert match is not None, f"{path} must expose the authoritative active-defect count"
    return int(match.group(1))


# Regression: CS-SR-087
def test_current_status_surfaces_match_authoritative_active_defect_count() -> None:
    expected = _active_defect_count()

    assert _documented_count("README.md") == expected
    assert _documented_count("docs/architecture/current_implementation_status.md") == expected
