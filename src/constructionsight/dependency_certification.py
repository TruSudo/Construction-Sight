"""Exact declaration, registry, and lock agreement checks."""

from __future__ import annotations

import re
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from constructionsight.governance_certification_core import GovernanceFinding, _finding

_EXACT_REQUIREMENT = re.compile(
    r"^(?P<name>[A-Za-z0-9_.-]+)(?:\[(?P<extras>[A-Za-z0-9_,.-]+)\])?==(?P<version>[^;\s]+)$"
)


def _canonical_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _parse_exact(value: str) -> tuple[str, tuple[str, ...], str] | None:
    match = _EXACT_REQUIREMENT.fullmatch(value.strip())
    if match is None:
        return None
    raw_extras = match.group("extras")
    extras = tuple(sorted(raw_extras.split(","))) if raw_extras else ()
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
    """Reject version or extras disagreement among declaration, registry, and locks."""

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
            tuple(sorted(str(value) for value in raw_extras))
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
        locked: dict[str, tuple[tuple[str, ...], str]] = {}
        for number, line in enumerate(
            absolute.read_text(encoding="utf-8").splitlines(), start=1
        ):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            exact = _parse_exact(stripped)
            if exact is None:
                continue
            name, extras, version = exact
            if name in locked:
                findings.append(
                    _finding(
                        "DEP-LOCK-005",
                        lock_path,
                        f"duplicate canonical lock identity: {name}",
                        number,
                    )
                )
            locked[name] = (extras, version)
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
