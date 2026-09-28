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



def test_current_status_does_not_describe_resolved_defects_as_open() -> None:
    text = Path("docs/architecture/current_implementation_status.md").read_text(
        encoding="utf-8"
    )

    prohibited = (
        r"remain(?:s)? open work under CS-SR-\d+",
        r"remain(?:s)? under CS-SR-\d+ review",
        r"CS-SR-\d+(?:/\d+)* remain(?:s)? open",
    )
    for pattern in prohibited:
        assert re.search(pattern, text, flags=re.IGNORECASE) is None, (
            f"current implementation status contains stale resolved-defect language: {pattern}"
        )
