"""Exact declaration, registry, and hashed-lock agreement checks."""

from __future__ import annotations

import re
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from constructionsight.governance_certification_core import GovernanceFinding, _finding
from constructionsight.supply_chain import load_lock_entries

_EXACT_REQUIREMENT = re.compile(
    r"^(?P<name>[A-Za-z0-9_.-]+)(?:\[(?P<extras>[A-Za-z0-9_,.-]+)\])?"
    r"==(?P<version>[^;\s]+)$"
)


def _canonical_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _parse_exact(value: str) -> tuple[str, tuple[str, ...], str] | None:
    match = _EXACT_REQUIREMENT.fullmatch(value.strip())
    if match is None:
        return None
    raw_extras = match.group("extras")
    extras = (
        tuple(sorted({_canonical_name(value) for value in raw_extras.split(",")}))
        if raw_extras
        else ()
    )
    return _canonical_name(match.group("name")), extras, match.group("version")


def _direct_requirements(root: Path) -> dict[str, tuple[tuple[str, ...], str]]:
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    raw: list[str] = []
    project = pyproject.get("project", {})
    raw.extend(str(value) for value in project.get("dependencies", []))
    for values in project.get("optional-dependencies", {}).values():
        raw.extend(str(value) for value in values)
    raw.extend(str(value) for value in pyproject.get("build-system", {}).get("requires", []))
    parsed: dict[str, tuple[tuple[str, ...], str]] = {}
    for requirement in raw:
        exact = _parse_exact(requirement)
        if exact is None:
            continue
        name, extras, version = exact
        parsed[name] = (extras, version)
    return parsed


def audit_dependency_agreement(
    root: Path,
    contract: Mapping[str, Any],
    findings: list[GovernanceFinding],
) -> None:
    """Reject disagreement among declarations, registry, and artifact-hashed locks."""

    path = "governance/dependency_contract.toml"
    direct = _direct_requirements(root)
    entries = contract.get("dependencies")
    if not isinstance(entries, list):
        return
    registry: dict[str, tuple[tuple[str, ...], str]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = _canonical_name(str(entry.get("name", "")))
        raw_extras = entry.get("extras")
        extras = (
            tuple(
                sorted(
                    {_canonical_name(str(value)) for value in raw_extras}
                )
            )
            if isinstance(raw_extras, list)
            else ()
        )
        version = str(entry.get("version", ""))
        registry[name] = (extras, version)
    for name, declaration in sorted(direct.items()):
        registered = registry.get(name)
        if registered is not None and registered != declaration:
            findings.append(
                _finding(
                    "DEP-REGISTRY-002",
                    path,
                    f"registry disagrees with pyproject for {name}: "
                    f"declared={declaration}, registry={registered}",
                )
            )

    lock_paths = contract.get("lock_files")
    if not isinstance(lock_paths, list):
        return
    for raw_path in lock_paths:
        lock_path = Path(str(raw_path))
        absolute = root / lock_path
        if not absolute.is_file():
            continue
        try:
            lock_entries = load_lock_entries(absolute)
        except (OSError, UnicodeError, ValueError) as exc:
            code = "DEP-LOCK-005" if "duplicate lock entry" in str(exc) else "DEP-LOCK-007"
            findings.append(
                _finding(
                    code,
                    lock_path,
                    f"lock cannot be certified: {exc}",
                )
            )
            continue
        locked = {
            entry.name: (entry.extras, entry.version)
            for entry in lock_entries
        }
        for name, declaration in sorted(direct.items()):
            lock_value = locked.get(name)
            if lock_value is not None and lock_value != declaration:
                findings.append(
                    _finding(
                        "DEP-LOCK-006",
                        lock_path,
                        f"lock disagrees with pyproject for {name}: "
                        f"declared={declaration}, lock={lock_value}",
                    )
                )
