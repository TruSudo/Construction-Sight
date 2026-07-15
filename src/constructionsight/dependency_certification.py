"""Exact declaration, registry, hashed-lock, and Action-pin certification."""

from __future__ import annotations

import re
import tomllib
from collections.abc import Mapping
from datetime import date
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


def _raw_direct_requirements(root: Path) -> list[str]:
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    raw: list[str] = []
    project = pyproject.get("project", {})
    raw.extend(str(value) for value in project.get("dependencies", []))
    for values in project.get("optional-dependencies", {}).values():
        raw.extend(str(value) for value in values)
    raw.extend(
        str(value)
        for value in pyproject.get("build-system", {}).get("requires", [])
    )
    return raw


def _direct_requirements(root: Path) -> dict[str, tuple[tuple[str, ...], str]]:
    parsed: dict[str, tuple[tuple[str, ...], str]] = {}
    for requirement in _raw_direct_requirements(root):
        exact = _parse_exact(requirement)
        if exact is None:
            continue
        name, extras, version = exact
        parsed[name] = (extras, version)
    return parsed


def audit_dependencies(
    root: Path,
    contract: Mapping[str, Any],
    findings: list[GovernanceFinding],
) -> int:
    """Audit dependency declarations, registry, hashed locks, and Action identities."""

    path = "governance/dependency_contract.toml"
    pyproject_path = root / "pyproject.toml"
    if not pyproject_path.is_file():
        findings.append(
            _finding("DEP-PROJECT-001", "pyproject.toml", "project declaration is missing")
        )
        return 0

    direct_raw = _raw_direct_requirements(root)
    parsed_direct = [_parse_exact(value) for value in direct_raw]
    for raw, parsed in zip(direct_raw, parsed_direct, strict=True):
        if parsed is None:
            findings.append(
                _finding(
                    "DEP-PIN-001",
                    "pyproject.toml",
                    f"direct/build dependency must use exact == pin: {raw}",
                )
            )
    direct_names = {
        parsed[0]
        for parsed in parsed_direct
        if parsed is not None
    }

    registry = contract.get("dependencies")
    if not isinstance(registry, list):
        findings.append(
            _finding(
                "DEP-CONTRACT-001",
                path,
                "dependencies registry must be an array of tables",
            )
        )
        return 0
    entries = [entry for entry in registry if isinstance(entry, dict)]
    by_name = {
        _canonical_name(str(entry.get("name", ""))): entry
        for entry in entries
    }
    if set(by_name) != direct_names:
        findings.append(
            _finding(
                "DEP-REGISTRY-001",
                path,
                "dependency registry mismatch; "
                f"declared-only={sorted(direct_names - set(by_name))}, "
                f"registry-only={sorted(set(by_name) - direct_names)}",
            )
        )

    required = {
        "name",
        "canonical_project",
        "extras",
        "version",
        "classification",
        "purpose",
        "capabilities",
        "authoritative_registry",
        "authoritative_project_source",
        "license",
        "security_review",
        "maintenance_review",
        "reviewed_on",
        "review_process",
        "replacement_considerations",
    }
    for entry in entries:
        missing = required - set(entry)
        unknown = set(entry) - required
        if missing or unknown:
            findings.append(
                _finding(
                    "DEP-CONTRACT-002",
                    path,
                    "dependency fields disagree with schema; "
                    f"missing={sorted(missing)}, unknown={sorted(unknown)}",
                )
            )
        reviewed = entry.get("reviewed_on")
        try:
            reviewed_date = date.fromisoformat(str(reviewed))
            if reviewed_date > date.today():
                findings.append(
                    _finding(
                        "DEP-REVIEW-001",
                        path,
                        f"dependency review date is in the future: {entry.get('name')}",
                    )
                )
        except ValueError:
            findings.append(
                _finding(
                    "DEP-CONTRACT-003",
                    path,
                    f"invalid reviewed_on for {entry.get('name')}",
                )
            )

    lock_paths = contract.get("lock_files")
    if not isinstance(lock_paths, list) or not lock_paths:
        findings.append(
            _finding("DEP-LOCK-001", path, "at least one lock file is required")
        )
    else:
        for raw_path in lock_paths:
            lock_path = Path(str(raw_path))
            absolute = root / lock_path
            if not absolute.is_file():
                findings.append(
                    _finding("DEP-LOCK-002", lock_path, "declared lock file is missing")
                )
                continue
            try:
                lock_entries = load_lock_entries(absolute)
            except (OSError, UnicodeError, ValueError) as exc:
                findings.append(
                    _finding(
                        "DEP-LOCK-003",
                        lock_path,
                        f"lock cannot be parsed as exact artifact-hashed requirements: {exc}",
                    )
                )
                continue
            lock_names = {entry.name for entry in lock_entries}
            missing_names = direct_names - lock_names
            if missing_names:
                findings.append(
                    _finding(
                        "DEP-LOCK-004",
                        lock_path,
                        f"lock omits direct dependencies: {sorted(missing_names)}",
                    )
                )

    workflow_paths = sorted((root / ".github/workflows").glob("*.y*ml"))
    action_pattern = re.compile(
        r"^(?P<indent>\s*)uses:\s*(?P<action>[^@\s]+)@"
        r"(?P<ref>[^\s#]+)(?P<comment>.*)$"
    )
    for workflow in workflow_paths:
        relative = workflow.relative_to(root)
        for number, line in enumerate(
            workflow.read_text(encoding="utf-8").splitlines(), start=1
        ):
            match = action_pattern.match(line)
            if not match:
                continue
            ref = match.group("ref")
            comment = match.group("comment")
            if not re.fullmatch(r"[0-9a-f]{40}", ref):
                findings.append(
                    _finding(
                        "DEP-ACTION-001",
                        relative,
                        "third-party Action is not pinned to an immutable SHA: "
                        f"{match.group('action')}@{ref}",
                        number,
                    )
                )
            if "#" not in comment or not comment.split("#", 1)[1].strip():
                findings.append(
                    _finding(
                        "DEP-ACTION-002",
                        relative,
                        "pinned Action requires a release/version comment",
                        number,
                    )
                )
    return len(entries)


def audit_dependency_agreement(
    root: Path,
    contract: Mapping[str, Any],
    findings: list[GovernanceFinding],
) -> None:
    """Reject version or extras disagreement among declarations, registry, and locks."""

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
            code = (
                "DEP-LOCK-005"
                if "duplicate lock entry" in str(exc)
                else "DEP-LOCK-007"
            )
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
