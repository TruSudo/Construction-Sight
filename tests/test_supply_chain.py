from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from constructionsight import supply_chain


@dataclass(frozen=True)
class _Distribution:
    version: str


def test_canonical_name_normalizes_python_distribution_identity() -> None:
    assert supply_chain.canonical_name("Python_DateUtil") == "python-dateutil"
    assert supply_chain.canonical_name("typing.extensions") == "typing-extensions"


def test_load_lock_rejects_nonexact_entry(tmp_path: Path) -> None:
    lock = tmp_path / "bad.lock"
    lock.write_text("example>=1.0\n", encoding="utf-8")

    with pytest.raises(ValueError, match="not exact"):
        supply_chain.load_lock(lock)


def test_load_lock_rejects_duplicate_canonical_identity(tmp_path: Path) -> None:
    lock = tmp_path / "duplicate.lock"
    lock.write_text(
        "python-dateutil==2.9.0.post0\nPython_DateUtil==2.9.0.post0\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate lock entry"):
        supply_chain.load_lock(lock)


def test_verify_lock_reports_missing_and_mismatched_versions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock = tmp_path / "environment.lock"
    lock.write_text("alpha==1.0\nbeta==2.0\ngamma==3.0\n", encoding="utf-8")
    monkeypatch.setattr(
        supply_chain,
        "installed_inventory",
        lambda: {
            "alpha": _Distribution("1.0"),
            "beta": _Distribution("9.0"),
        },
    )

    report = supply_chain.verify_lock(lock)

    assert report["passed"] is False
    assert report["finding_count"] == 2
    assert [item["code"] for item in report["findings"]] == [
        "SUPPLY-MISSING-001",
        "SUPPLY-VERSION-001",
    ]


def test_verify_lock_accepts_exact_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock = tmp_path / "environment.lock"
    lock.write_text("alpha==1.0\nbeta==2.0\n", encoding="utf-8")
    monkeypatch.setattr(
        supply_chain,
        "installed_inventory",
        lambda: {
            "alpha": _Distribution("1.0"),
            "beta": _Distribution("2.0"),
        },
    )

    report = supply_chain.verify_lock(lock)

    assert report["passed"] is True
    assert report["finding_count"] == 0
