"""Deterministic hashed-lock verification and SBOM generation."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import re
import sys
import tomllib
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final
from urllib.parse import urlsplit

from constructionsight import __version__

SCHEMA_VERSION: Final = "constructionsight.supply-chain-report/v1"
_REQUIREMENT_PATTERN: Final = re.compile(
    r"^(?P<name>[A-Za-z0-9_.-]+)"
    r"(?:\[(?P<extras>[A-Za-z0-9_,.-]+)\])?"
    r"==(?P<version>[^;\\\s]+)"
    r"(?P<options>(?:\s+--hash=sha256:[0-9a-f]{64})+)$"
)
_HASH_TOKEN_PATTERN: Final = re.compile(r"--hash=sha256:([0-9a-f]{64})")
_EXPECTED_UNLOCKED_DISTRIBUTIONS: Final = {"constructionsight": __version__}


@dataclass(frozen=True)
class LockedRequirement:
    """One canonical exact requirement bound to approved SHA-256 artifacts."""

    name: str
    extras: tuple[str, ...]
    version: str
    hashes: tuple[str, ...]
    line: int


@dataclass(frozen=True)
class SourceProject:
    """Non-executable project metadata bound to the reviewed source tree."""

    name: str
    version: str
    license_expression: str
    root: Path


def canonical_name(value: str) -> str:
    """Return the canonical distribution or extra identity used by packaging."""

    return re.sub(r"[-_.]+", "-", value).lower()


def _logical_lock_rows(path: Path) -> tuple[tuple[int, str], ...]:
    """Join backslash-continued requirement rows without accepting hidden content."""

    rows: list[tuple[int, str]] = []
    parts: list[str] = []
    first_line: int | None = None
    for number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            if parts:
                raise ValueError(
                    f"{path}:{number}: comments or blank lines cannot interrupt a lock entry"
                )
            continue
        if first_line is None:
            first_line = number
        continued = stripped.endswith("\\")
        segment = stripped[:-1].rstrip() if continued else stripped
        if not segment:
            raise ValueError(f"{path}:{number}: empty lock continuation")
        parts.append(segment)
        if continued:
            continue
        rows.append((first_line, " ".join(parts)))
        parts = []
        first_line = None
    if parts:
        assert first_line is not None
        raise ValueError(f"{path}:{first_line}: dangling lock continuation")
    return tuple(rows)


def load_lock_entries(path: Path) -> tuple[LockedRequirement, ...]:
    """Load canonical hashed requirements and reject ambiguity or hidden drift."""

    entries: list[LockedRequirement] = []
    seen: set[str] = set()
    for number, row in _logical_lock_rows(path):
        match = _REQUIREMENT_PATTERN.fullmatch(row)
        if match is None:
            raise ValueError(
                f"{path}:{number}: lock entry must be exact and SHA-256 hashed: {row}"
            )
        raw_name = match.group("name")
        name = canonical_name(raw_name)
        if raw_name != name:
            raise ValueError(
                f"{path}:{number}: distribution name must be canonical: {raw_name}"
            )
        raw_extras = match.group("extras")
        extras = (
            tuple(canonical_name(value) for value in raw_extras.split(","))
            if raw_extras
            else ()
        )
        if extras != tuple(sorted(set(extras))):
            raise ValueError(
                f"{path}:{number}: extras must be canonical, unique, and sorted"
            )
        hashes = tuple(_HASH_TOKEN_PATTERN.findall(match.group("options")))
        if not hashes:
            raise ValueError(f"{path}:{number}: lock entry has no SHA-256 artifact hash")
        if hashes != tuple(sorted(set(hashes))):
            raise ValueError(
                f"{path}:{number}: artifact hashes must be unique and sorted"
            )
        if name in seen:
            raise ValueError(f"{path}:{number}: duplicate lock entry: {name}")
        seen.add(name)
        entries.append(
            LockedRequirement(
                name=name,
                extras=extras,
                version=match.group("version"),
                hashes=hashes,
                line=number,
            )
        )
    if not entries:
        raise ValueError(f"{path}: lock is empty")
    names = tuple(entry.name for entry in entries)
    if names != tuple(sorted(names)):
        raise ValueError(f"{path}: lock entries must be sorted by canonical name")
    return tuple(entries)


def load_lock(path: Path) -> dict[str, str]:
    """Return canonical exact versions after validating every artifact hash."""

    return {entry.name: entry.version for entry in load_lock_entries(path)}


def _metadata_value(
    distribution: importlib.metadata.Distribution,
    key: str,
) -> str | None:
    """Return one metadata value without relying on an untyped get method."""

    values = distribution.metadata.get_all(key)
    return values[0] if values else None


def installed_inventory() -> dict[str, importlib.metadata.Distribution]:
    """Return exactly one installed distribution per canonical identity."""

    inventory: dict[str, importlib.metadata.Distribution] = {}
    for distribution in importlib.metadata.distributions():
        raw_name = _metadata_value(distribution, "Name")
        if not raw_name:
            raise RuntimeError("installed distribution is missing canonical Name metadata")
        name = canonical_name(raw_name)
        prior = inventory.get(name)
        if prior is not None:
            raise RuntimeError(
                f"multiple installed distributions for {name}: "
                f"{prior.version}, {distribution.version}"
            )
        inventory[name] = distribution
    return inventory


def _source_project(root: Path) -> SourceProject:
    """Load project identity from reviewed source metadata without invoking a backend."""

    resolved_root = root.resolve(strict=True)
    pyproject = resolved_root / "pyproject.toml"
    package_init = resolved_root / "src/constructionsight/__init__.py"
    certifier = resolved_root / "src/constructionsight/supply_chain.py"
    for path in (pyproject, package_init, certifier):
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"source project path is missing or symbolic: {path}")
    if Path(__file__).resolve() != certifier.resolve():
        raise ValueError("supply-chain certifier is not executing from the reviewed source tree")
    try:
        payload = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"cannot parse source project metadata: {exc}") from exc
    project = payload.get("project")
    if not isinstance(project, dict):
        raise ValueError("source project metadata is missing [project]")
    raw_name = project.get("name")
    raw_version = project.get("version")
    if not isinstance(raw_name, str) or canonical_name(raw_name) != "constructionsight":
        raise ValueError("source project name is not constructionsight")
    if not isinstance(raw_version, str) or raw_version != __version__:
        raise ValueError("source project version disagrees with package version")
    license_field = project.get("license")
    raw_license = license_field.get("text") if isinstance(license_field, dict) else license_field
    license_expression = (
        raw_license.strip()
        if isinstance(raw_license, str) and raw_license.strip()
        else "NOASSERTION"
    )
    return SourceProject(
        name="constructionsight",
        version=raw_version,
        license_expression=license_expression,
        root=resolved_root,
    )


def _verification_report(
    path: Path,
    expected: dict[str, str],
    installed: dict[str, importlib.metadata.Distribution],
    *,
    source_project: SourceProject | None = None,
) -> dict[str, Any]:
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
    for name, version in _EXPECTED_UNLOCKED_DISTRIBUTIONS.items():
        distribution = installed.get(name)
        if source_project is not None:
            if source_project.name != name or source_project.version != version:
                findings.append(
                    {
                        "code": "SUPPLY-PROJECT-SOURCE-IDENTITY-001",
                        "package": name,
                        "expected": version,
                        "actual": source_project.version,
                    }
                )
            if distribution is not None:
                findings.append(
                    {
                        "code": "SUPPLY-PROJECT-SHADOW-001",
                        "package": name,
                        "expected": "absent-installed-distribution",
                        "actual": distribution.version,
                    }
                )
        elif distribution is None:
            findings.append(
                {
                    "code": "SUPPLY-PROJECT-MISSING-001",
                    "package": name,
                    "expected": version,
                }
            )
        elif distribution.version != version:
            findings.append(
                {
                    "code": "SUPPLY-PROJECT-VERSION-001",
                    "package": name,
                    "expected": version,
                    "actual": distribution.version,
                }
            )
    unexpected = sorted(
        set(installed) - set(expected) - set(_EXPECTED_UNLOCKED_DISTRIBUTIONS)
    )
    for name in unexpected:
        findings.append(
            {
                "code": "SUPPLY-UNEXPECTED-001",
                "package": name,
                "expected": "absent",
                "actual": installed[name].version,
            }
        )
    findings.sort(key=lambda item: (item["code"], item["package"]))
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "lock": path.as_posix(),
        "locked_distribution_count": len(expected),
        "expected_project_distributions": dict(_EXPECTED_UNLOCKED_DISTRIBUTIONS),
        "installed_distribution_count": len(installed),
        "project_execution_mode": (
            "reviewed-source-tree" if source_project is not None else "installed-distribution"
        ),
        "finding_count": len(findings),
        "passed": not findings,
        "findings": findings,
    }
    if source_project is not None:
        report["source_project_root"] = source_project.root.as_posix()
    return report


def verify_lock(path: Path, *, source_root: Path | None = None) -> dict[str, Any]:
    """Verify exact versions and reject every undeclared installed distribution."""

    source_project = _source_project(source_root) if source_root is not None else None
    return _verification_report(
        path,
        load_lock(path),
        installed_inventory(),
        source_project=source_project,
    )


def _license_expression(distribution: importlib.metadata.Distribution) -> str:
    license_value = _metadata_value(distribution, "License")
    if license_value and license_value.strip() and license_value.strip() != "UNKNOWN":
        return license_value.strip()
    classifiers = distribution.metadata.get_all("Classifier") or []
    licenses = [
        value.partition("License :: OSI Approved :: ")[2]
        for value in classifiers
        if value.startswith("License :: OSI Approved :: ")
    ]
    return " OR ".join(sorted(set(licenses))) if licenses else "NOASSERTION"


def _authoritative_project_url(
    distribution: importlib.metadata.Distribution,
) -> str | None:
    candidates: list[str] = []
    for raw in distribution.metadata.get_all("Project-URL") or []:
        _, separator, value = raw.partition(",")
        candidates.append(value.strip() if separator else raw.strip())
    homepage = _metadata_value(distribution, "Home-page")
    if homepage:
        candidates.append(homepage.strip())
    for candidate in candidates:
        parsed = urlsplit(candidate)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return candidate
    return None


def _component(
    distribution: importlib.metadata.Distribution,
    *,
    name: str,
    version: str,
    component_type: str,
    purl_type: str,
    hashes: tuple[str, ...] = (),
) -> dict[str, Any]:
    purl = f"pkg:{purl_type}/{name}@{version}"
    component: dict[str, Any] = {
        "type": component_type,
        "bom-ref": purl,
        "name": name,
        "version": version,
        "purl": purl,
        "licenses": [{"expression": _license_expression(distribution)}],
    }
    if hashes:
        component["hashes"] = [
            {"alg": "SHA-256", "content": digest}
            for digest in hashes
        ]
    homepage = _authoritative_project_url(distribution)
    if homepage is not None:
        component["externalReferences"] = [
            {
                "type": "website",
                "url": homepage,
            }
        ]
    return component


def _source_component(project: SourceProject) -> dict[str, Any]:
    purl = f"pkg:generic/{project.name}@{project.version}"
    return {
        "type": "application",
        "bom-ref": purl,
        "name": project.name,
        "version": project.version,
        "purl": purl,
        "licenses": [{"expression": project.license_expression}],
    }


def build_sbom(lock_path: Path, *, source_root: Path | None = None) -> dict[str, Any]:
    """Build a deterministic CycloneDX 1.5 inventory for the exact environment."""

    entries = load_lock_entries(lock_path)
    expected = {entry.name: entry.version for entry in entries}
    installed = installed_inventory()
    source_project = _source_project(source_root) if source_root is not None else None
    verification = _verification_report(
        lock_path,
        expected,
        installed,
        source_project=source_project,
    )
    if not verification["passed"]:
        raise RuntimeError(
            "cannot generate an exact-environment SBOM from a mismatched lock"
        )
    project_name, project_version = next(iter(_EXPECTED_UNLOCKED_DISTRIBUTIONS.items()))
    if source_project is None:
        project_component = _component(
            installed[project_name],
            name=project_name,
            version=project_version,
            component_type="application",
            purl_type="generic",
        )
    else:
        project_component = _source_component(source_project)
    components = [
        _component(
            installed[entry.name],
            name=entry.name,
            version=entry.version,
            component_type="library",
            purl_type="pypi",
            hashes=entry.hashes,
        )
        for entry in entries
    ]
    serial_material = json.dumps(
        {"project": project_component, "components": components},
        sort_keys=True,
        separators=(",", ":"),
    )
    serial_digest = hashlib.sha256(serial_material.encode("utf-8")).hexdigest()
    serial = uuid.UUID(hex=serial_digest[:32], version=5)
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{serial}",
        "version": 1,
        "metadata": {
            "component": project_component,
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
                {
                    "name": "constructionsight.projectExecutionMode",
                    "value": verification["project_execution_mode"],
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


def _source_root_for_cli() -> Path | None:
    root = Path.cwd()
    if (root / "pyproject.toml").is_file() and (
        root / "src/constructionsight/supply_chain.py"
    ).is_file():
        return root
    return None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify hashed locked dependencies and emit an SBOM."
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
    """Run supply-chain commands and fail visibly on disagreement."""

    arguments = _parser().parse_args(argv)
    source_root = _source_root_for_cli()
    try:
        if arguments.command == "verify-lock":
            payload = verify_lock(arguments.lock, source_root=source_root)
            if arguments.output is not None:
                _write_json(arguments.output, payload)
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0 if payload["passed"] else 1
        payload = build_sbom(arguments.lock, source_root=source_root)
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
