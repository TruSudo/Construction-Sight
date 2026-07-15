from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from constructionsight import supply_chain

_HASH = "a" * 64


@dataclass(frozen=True)
class _Distribution:
    version: str


@dataclass(frozen=True)
class _InventoryDistribution:
    name: str | None
    version: str

    @property
    def metadata(self) -> dict[str, Any]:
        return {} if self.name is None else {"Name": self.name}


def _locked(requirement: str, *, digest: str = _HASH) -> str:
    return f"{requirement} --hash=sha256:{digest}\n"


def _with_project(
    values: dict[str, _Distribution],
    *,
    version: str = "0.1.0",
) -> dict[str, _Distribution]:
    return {**values, "constructionsight": _Distribution(version)}


def test_canonical_name_normalizes_python_distribution_identity() -> None:
    assert supply_chain.canonical_name("Python_DateUtil") == "python-dateutil"
    assert supply_chain.canonical_name("typing.extensions") == "typing-extensions"


def test_load_lock_rejects_nonexact_entry(tmp_path: Path) -> None:
    lock = tmp_path / "bad.lock"
    lock.write_text(
        f"example>=1.0 --hash=sha256:{_HASH}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="exact and SHA-256 hashed"):
        supply_chain.load_lock(lock)


def test_load_lock_rejects_unhashed_entry(tmp_path: Path) -> None:
    lock = tmp_path / "unhashed.lock"
    lock.write_text("example==1.0\n", encoding="utf-8")

    with pytest.raises(ValueError, match="exact and SHA-256 hashed"):
        supply_chain.load_lock(lock)


def test_load_lock_rejects_duplicate_canonical_identity(tmp_path: Path) -> None:
    lock = tmp_path / "duplicate.lock"
    lock.write_text(
        _locked("python-dateutil==2.9.0.post0")
        + _locked("Python_DateUtil==2.9.0.post0"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate lock entry"):
        supply_chain.load_lock(lock)


def test_load_lock_accepts_continued_hashed_entry_and_canonical_extras(
    tmp_path: Path,
) -> None:
    lock = tmp_path / "continued.lock"
    lock.write_text(
        "Example[b,a]==2.0 \\\n"
        f"  --hash=sha256:{_HASH}\n",
        encoding="utf-8",
    )

    entries = supply_chain.load_lock_entries(lock)

    assert len(entries) == 1
    assert entries[0].name == "example"
    assert entries[0].extras == ("a", "b")
    assert entries[0].hashes == (_HASH,)


def test_load_lock_rejects_dangling_continuation(tmp_path: Path) -> None:
    lock = tmp_path / "dangling.lock"
    lock.write_text("example==1.0 \\\n", encoding="utf-8")

    with pytest.raises(ValueError, match="dangling lock continuation"):
        supply_chain.load_lock(lock)


def test_installed_inventory_rejects_duplicate_distribution_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        supply_chain.importlib.metadata,
        "distributions",
        lambda: (
            _InventoryDistribution("Example", "1.0"),
            _InventoryDistribution("example", "1.0"),
        ),
    )

    with pytest.raises(RuntimeError, match="multiple installed distributions"):
        supply_chain.installed_inventory()


def test_installed_inventory_rejects_missing_name_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        supply_chain.importlib.metadata,
        "distributions",
        lambda: (_InventoryDistribution(None, "1.0"),),
    )

    with pytest.raises(RuntimeError, match="missing canonical Name"):
        supply_chain.installed_inventory()


def test_verify_lock_reports_missing_and_mismatched_versions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock = tmp_path / "environment.lock"
    lock.write_text(
        _locked("alpha==1.0")
        + _locked("beta==2.0")
        + _locked("gamma==3.0"),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        supply_chain,
        "installed_inventory",
        lambda: _with_project(
            {
                "alpha": _Distribution("1.0"),
                "beta": _Distribution("9.0"),
            }
        ),
    )

    report = supply_chain.verify_lock(lock)

    assert report["passed"] is False
    assert report["finding_count"] == 2
    assert [item["code"] for item in report["findings"]] == [
        "SUPPLY-MISSING-001",
        "SUPPLY-VERSION-001",
    ]


def test_verify_lock_rejects_unexpected_distribution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock = tmp_path / "environment.lock"
    lock.write_text(_locked("alpha==1.0"), encoding="utf-8")
    monkeypatch.setattr(
        supply_chain,
        "installed_inventory",
        lambda: _with_project(
            {
                "alpha": _Distribution("1.0"),
                "rogue-package": _Distribution("9.9"),
            }
        ),
    )

    report = supply_chain.verify_lock(lock)

    assert report["passed"] is False
    assert report["findings"] == [
        {
            "code": "SUPPLY-UNEXPECTED-001",
            "package": "rogue-package",
            "expected": "absent",
            "actual": "9.9",
        }
    ]


def test_verify_lock_rejects_project_version_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock = tmp_path / "environment.lock"
    lock.write_text(_locked("alpha==1.0"), encoding="utf-8")
    monkeypatch.setattr(
        supply_chain,
        "installed_inventory",
        lambda: _with_project(
            {"alpha": _Distribution("1.0")},
            version="9.9.9",
        ),
    )

    report = supply_chain.verify_lock(lock)

    assert report["passed"] is False
    assert report["findings"] == [
        {
            "code": "SUPPLY-PROJECT-VERSION-001",
            "package": "constructionsight",
            "expected": "0.1.0",
            "actual": "9.9.9",
        }
    ]


def test_verify_lock_requires_project_distribution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock = tmp_path / "environment.lock"
    lock.write_text(_locked("alpha==1.0"), encoding="utf-8")
    monkeypatch.setattr(
        supply_chain,
        "installed_inventory",
        lambda: {"alpha": _Distribution("1.0")},
    )

    report = supply_chain.verify_lock(lock)

    assert report["passed"] is False
    assert report["findings"] == [
        {
            "code": "SUPPLY-PROJECT-MISSING-001",
            "package": "constructionsight",
            "expected": "0.1.0",
        }
    ]


def test_verify_lock_accepts_exact_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock = tmp_path / "environment.lock"
    lock.write_text(
        _locked("alpha==1.0") + _locked("beta==2.0"),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        supply_chain,
        "installed_inventory",
        lambda: _with_project(
            {
                "alpha": _Distribution("1.0"),
                "beta": _Distribution("2.0"),
            }
        ),
    )

    report = supply_chain.verify_lock(lock)

    assert report["passed"] is True
    assert report["finding_count"] == 0
