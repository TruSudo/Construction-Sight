from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from constructionsight import supply_chain

_HASH = "a" * 64


class _Metadata(dict[str, str]):
    def get_all(self, key: str) -> list[str] | None:
        value = self.get(key)
        return [value] if value is not None else None


@dataclass(frozen=True)
class _Distribution:
    name: str
    version: str

    @property
    def metadata(self) -> _Metadata:
        return _Metadata({"Name": self.name, "License": "MIT"})


def _lock(tmp_path: Path) -> Path:
    lock = tmp_path / "environment.lock"
    lock.write_text(
        f"alpha==1.0 --hash=sha256:{_HASH}\n",
        encoding="utf-8",
    )
    return lock


def test_source_tree_mode_accepts_absent_project_distribution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        supply_chain,
        "installed_inventory",
        lambda: {"alpha": _Distribution("alpha", "1.0")},
    )

    report = supply_chain.verify_lock(_lock(tmp_path), source_root=Path.cwd())

    assert report["passed"] is True
    assert report["finding_count"] == 0
    assert report["project_execution_mode"] == "reviewed-source-tree"
    assert report["source_project_root"] == Path.cwd().resolve().as_posix()


def test_source_tree_mode_rejects_installed_project_shadow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        supply_chain,
        "installed_inventory",
        lambda: {
            "alpha": _Distribution("alpha", "1.0"),
            "constructionsight": _Distribution("ConstructionSight", "0.1.0"),
        },
    )

    report = supply_chain.verify_lock(_lock(tmp_path), source_root=Path.cwd())

    assert report["passed"] is False
    assert report["findings"] == [
        {
            "code": "SUPPLY-PROJECT-SHADOW-001",
            "package": "constructionsight",
            "expected": "absent-installed-distribution",
            "actual": "0.1.0",
        }
    ]


def test_source_tree_sbom_uses_reviewed_project_metadata_without_install(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        supply_chain,
        "installed_inventory",
        lambda: {"alpha": _Distribution("alpha", "1.0")},
    )

    sbom = supply_chain.build_sbom(_lock(tmp_path), source_root=Path.cwd())

    project = sbom["metadata"]["component"]
    assert project == {
        "type": "application",
        "bom-ref": "pkg:generic/constructionsight@0.1.0",
        "name": "constructionsight",
        "version": "0.1.0",
        "purl": "pkg:generic/constructionsight@0.1.0",
        "licenses": [{"expression": "Proprietary"}],
    }
    properties = {
        item["name"]: item["value"] for item in sbom["metadata"]["properties"]
    }
    assert properties["constructionsight.projectExecutionMode"] == "reviewed-source-tree"


def test_supported_locks_retain_reviewed_anyio_security_patch() -> None:
    """Reject reversion of the reviewed AnyIO security fix in either runtime lock."""

    root = Path(__file__).resolve().parents[1]
    reviewed_wheel_hash = "9f505dda5ac9f0c8309b5e8bd445a8c2bf7246f3ce950121e45ea15bc41d1494"
    for interpreter in ("311", "312"):
        entries = supply_chain.load_lock_entries(
            root / "requirements" / f"py{interpreter}.lock"
        )
        package = next(entry for entry in entries if entry.name == "anyio")
        assert package.version == "4.14.2"
        assert package.hashes == (reviewed_wheel_hash,)
