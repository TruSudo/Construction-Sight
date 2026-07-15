"""Deterministic installed-environment verification and SBOM generation."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final

SCHEMA_VERSION: Final = "constructionsight.supply-chain-report/v1"
_LOCK_PATTERN: Final = re.compile(r"^([A-Za-z0-9_.-]+)(?:\[[^]]+\])?==([^;\s]+)$")


def canonical_name(value: str) -> str:
    """Return the canonical distribution identity used by Python packaging."""

    return re.sub(r"[-_.]+", "-", value).lower()


def load_lock(path: Path) -> dict[str, str]:
    """Load an exact requirements lock and reject duplicate or nonexact rows."""

    entries: dict[str, str] = {}
    for number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _LOCK_PATTERN.fullmatch(stripped)
        if match is None:
            raise ValueError(f"{path}:{number}: lock entry is not exact: {stripped}")
        name = canonical_name(match.group(1))
        version = match.group(2)
        if name in entries:
            raise ValueError(f"{path}:{number}: duplicate lock entry: {name}")
        entries[name] = version
    if not entries:
        raise ValueError(f"{path}: lock is empty")
    return dict(sorted(entries.items()))


def installed_inventory() -> dict[str, importlib.metadata.Distribution]:
    """Return one deterministic installed distribution per canonical identity."""

    inventory: dict[str, importlib.metadata.Distribution] = {}
    for distribution in importlib.metadata.distributions():
        raw_name = distribution.metadata.get("Name")
        if not raw_name:
            continue
        name = canonical_name(raw_name)
        prior = inventory.get(name)
        if prior is not None and prior.version != distribution.version:
            raise RuntimeError(
                f"multiple installed versions for {name}: "
                f"{prior.version}, {distribution.version}"
            )
        inventory[name] = distribution
    return inventory


def verify_lock(path: Path) -> dict[str, Any]:
    """Verify that every locked distribution is installed at the exact version."""

    expected = load_lock(path)
    installed = installed_inventory()
    findings: list[dict[str, str]] = []
    for name, version in expected.items():
        distribution = installed.get(name)
        if distribution is None:
            findings.append(
                {"code": "SUPPLY-MISSING-001", "package": name, "expected": version}
            )
        elif distribution.version != version:
            findings.append(
                {
                    "code": "SUPPLY-VERSION-001",
                    "package": name,
                    "expected": version,
                    "actual": distribution.version,
                }
            )
    findings.sort(key=lambda item: (item["code"], item["package"]))
    return {
        "schema_version": SCHEMA_VERSION,
        "lock": path.as_posix(),
        "expected_distribution_count": len(expected),
        "finding_count": len(findings),
        "passed": not findings,
        "findings": findings,
    }


def _license_expression(distribution: importlib.metadata.Distribution) -> str:
    license_value = distribution.metadata.get("License")
    if license_value and license_value.strip() and license_value.strip() != "UNKNOWN":
        return license_value.strip()
    classifiers = distribution.metadata.get_all("Classifier") or []
    licenses = [
        value.partition("License :: OSI Approved :: ")[2]
        for value in classifiers
        if value.startswith("License :: OSI Approved :: ")
    ]
    return " OR ".join(sorted(set(licenses))) if licenses else "NOASSERTION"


def build_sbom(lock_path: Path) -> dict[str, Any]:
    """Build a deterministic CycloneDX 1.5 inventory for the exact lock."""

    expected = load_lock(lock_path)
    installed = installed_inventory()
    verification = verify_lock(lock_path)
    if not verification["passed"]:
        raise RuntimeError(
            "cannot generate an exact-environment SBOM from a mismatched lock"
        )
    components: list[dict[str, Any]] = []
    for name, version in expected.items():
        distribution = installed[name]
        metadata = distribution.metadata
        homepage = metadata.get("Project-URL") or metadata.get("Home-page")
        component: dict[str, Any] = {
            "type": "library",
            "bom-ref": f"pkg:pypi/{name}@{version}",
            "name": name,
            "version": version,
            "purl": f"pkg:pypi/{name}@{version}",
            "licenses": [{"expression": _license_expression(distribution)}],
        }
        if homepage:
            component["externalReferences"] = [
                {
                    "type": "website",
                    "url": str(homepage).split(",", 1)[0].strip(),
                }
            ]
        components.append(component)
    serial_material = json.dumps(
        components, sort_keys=True, separators=(",", ":")
    )
    serial = hashlib.sha256(serial_material.encode("utf-8")).hexdigest()
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": (
            f"urn:uuid:{serial[:8]}-{serial[8:12]}-{serial[12:16]}-"
            f"{serial[16:20]}-{serial[20:32]}"
        ),
        "version": 1,
        "metadata": {
            "tools": {
                "components": [
                    {
                        "type": "application",
                        "name": "ConstructionSight supply-chain certifier",
                        "version": SCHEMA_VERSION,
                    }
                ]
            },
            "properties": [
                {"name": "constructionsight.lock", "value": lock_path.as_posix()},
                {
                    "name": "constructionsight.environmentVerified",
                    "value": "true",
                },
            ],
        },
        "components": components,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify locked dependencies and emit an SBOM."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    verify = subparsers.add_parser("verify-lock")
    verify.add_argument("--lock", type=Path, required=True)
    verify.add_argument("--output", type=Path)
    sbom = subparsers.add_parser("sbom")
    sbom.add_argument("--lock", type=Path, required=True)
    sbom.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the supply-chain command and fail visibly on disagreement."""

    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "verify-lock":
            payload = verify_lock(arguments.lock)
            if arguments.output is not None:
                _write_json(arguments.output, payload)
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0 if payload["passed"] else 1
        payload = build_sbom(arguments.lock)
        _write_json(arguments.output, payload)
        print(
            f"Wrote {len(payload['components'])} locked components "
            f"to {arguments.output}"
        )
        return 0
    except (OSError, UnicodeError, ValueError, RuntimeError) as exc:
        print(f"Supply-chain certification failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
