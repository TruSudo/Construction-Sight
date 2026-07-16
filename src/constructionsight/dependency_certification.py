"""Exact declaration, registry, hashed-lock, and Action-pin certification."""

from __future__ import annotations

import re
import tomllib
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any, Final
from urllib.parse import urlsplit

from constructionsight import __version__
from constructionsight.governance_certification_core import GovernanceFinding, _finding
from constructionsight.supply_chain import load_lock_entries

_EXACT_REQUIREMENT: Final = re.compile(
    r"^(?P<name>[A-Za-z0-9_.-]+)(?:\[(?P<extras>[A-Za-z0-9_,.-]+)\])?"
    r"==(?P<version>[^;\s]+)$"
)
_TOP_LEVEL_FIELDS: Final = {
    "schema_version",
    "contract_id",
    "supported_python",
    "supported_runner",
    "lock_files",
    "lock_format",
    "require_hashes",
    "binary_only",
    "reject_unexpected_installed_distributions",
    "expected_project_distribution",
    "bootstrap_distributions",
    "install_policy",
    "hash_policy",
    "vulnerability_tool",
    "vulnerability_failure_policy",
    "vulnerability_exceptions",
    "sbom_format",
    "sbom_output",
    "review_evidence",
    "dependencies",
}
_DEPENDENCY_FIELDS: Final = {
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
_NONEMPTY_TEXT_FIELDS: Final = {
    "canonical_project",
    "version",
    "purpose",
    "authoritative_registry",
    "authoritative_project_source",
    "license",
    "security_review",
    "maintenance_review",
    "review_process",
    "replacement_considerations",
}
_REQUIRED_CI_SNIPPETS: Final = {
    "--require-hashes",
    "--only-binary=:all:",
    "--no-deps",
    "python -m constructionsight.supply_chain verify-lock",
    "python -m pip check",
    "pypa/gh-action-pip-audit@",
    "python -m constructionsight.supply_chain sbom",
    "python -m constructionsight.mutation_certification",
    "python -m constructionsight.repository_certification_v2",
}


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


def _is_https_url(value: object, *, host: str | None = None) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlsplit(value)
    return (
        parsed.scheme == "https"
        and bool(parsed.netloc)
        and (host is None or parsed.hostname == host)
    )


def _safe_relative_path(value: object) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        return None
    return path


def _audit_contract_policy(
    root: Path,
    contract: Mapping[str, Any],
    findings: list[GovernanceFinding],
) -> None:
    path = "governance/dependency_contract.toml"
    missing = _TOP_LEVEL_FIELDS - set(contract)
    unknown = set(contract) - _TOP_LEVEL_FIELDS
    if missing or unknown:
        findings.append(
            _finding(
                "DEP-CONTRACT-000",
                path,
                "top-level dependency fields disagree with schema; "
                f"missing={sorted(missing)}, unknown={sorted(unknown)}",
            )
        )
    expected_policy: tuple[tuple[str, object], ...] = (
        ("supported_python", ["3.11", "3.12"]),
        ("supported_runner", "github-hosted-ubuntu-x86_64"),
        ("lock_format", "pip-requirements-sha256-v1"),
        ("require_hashes", True),
        ("binary_only", True),
        ("reject_unexpected_installed_distributions", True),
        ("expected_project_distribution", f"constructionsight=={__version__}"),
        ("sbom_format", "CycloneDX 1.5 JSON"),
    )
    for field, expected in expected_policy:
        if contract.get(field) != expected:
            findings.append(
                _finding(
                    "DEP-POLICY-001",
                    path,
                    f"{field} must equal {expected!r}",
                )
            )
    for artifact_field in ("vulnerability_exceptions", "review_evidence"):
        relative = _safe_relative_path(contract.get(artifact_field))
        if relative is None or not (root / relative).is_file():
            findings.append(
                _finding(
                    "DEP-POLICY-002",
                    path,
                    f"{artifact_field} must reference an existing safe relative path",
                )
            )
    bootstrap = contract.get("bootstrap_distributions")
    if not isinstance(bootstrap, list) or not bootstrap:
        findings.append(
            _finding(
                "DEP-POLICY-003",
                path,
                "bootstrap_distributions must be a nonempty exact-requirement array",
            )
        )
    elif any(_parse_exact(str(value)) is None for value in bootstrap):
        findings.append(
            _finding(
                "DEP-POLICY-003",
                path,
                "every bootstrap distribution must use one exact requirement",
            )
        )


def _audit_registry_entry(
    entry: Mapping[str, Any],
    *,
    path: str,
    findings: list[GovernanceFinding],
) -> str | None:
    missing = _DEPENDENCY_FIELDS - set(entry)
    unknown = set(entry) - _DEPENDENCY_FIELDS
    if missing or unknown:
        findings.append(
            _finding(
                "DEP-CONTRACT-002",
                path,
                "dependency fields disagree with schema; "
                f"missing={sorted(missing)}, unknown={sorted(unknown)}",
            )
        )
    raw_name = entry.get("name")
    if not isinstance(raw_name, str) or not raw_name.strip():
        findings.append(
            _finding("DEP-CONTRACT-004", path, "dependency name must be nonblank text")
        )
        return None
    name = _canonical_name(raw_name)
    if raw_name != name:
        findings.append(
            _finding(
                "DEP-CONTRACT-004",
                path,
                f"dependency name must be canonical: {raw_name}",
            )
        )
    canonical_project = entry.get("canonical_project")
    if not isinstance(canonical_project, str) or _canonical_name(canonical_project) != name:
        findings.append(
            _finding(
                "DEP-IDENTITY-001",
                path,
                f"canonical_project disagrees with dependency identity: {raw_name}",
            )
        )
    for field in _NONEMPTY_TEXT_FIELDS:
        value = entry.get(field)
        if not isinstance(value, str) or not value.strip() or value != value.strip():
            findings.append(
                _finding(
                    "DEP-CONTRACT-005",
                    path,
                    f"{raw_name}.{field} must be nonblank trimmed text",
                )
            )
    if entry.get("classification") not in {"runtime", "development", "build"}:
        findings.append(
            _finding(
                "DEP-CONTRACT-006",
                path,
                f"invalid dependency classification for {raw_name}",
            )
        )
    extras = entry.get("extras")
    if not isinstance(extras, list) or not all(isinstance(value, str) for value in extras):
        findings.append(
            _finding("DEP-CONTRACT-007", path, f"invalid extras for {raw_name}")
        )
    else:
        canonical_extras = [_canonical_name(value) for value in extras]
        if extras != sorted(set(canonical_extras)):
            findings.append(
                _finding(
                    "DEP-CONTRACT-007",
                    path,
                    f"extras must be canonical, unique, and sorted for {raw_name}",
                )
            )
    capabilities = entry.get("capabilities")
    if (
        not isinstance(capabilities, list)
        or not capabilities
        or not all(isinstance(value, str) and value.strip() for value in capabilities)
        or capabilities != sorted(set(capabilities))
    ):
        findings.append(
            _finding(
                "DEP-CONTRACT-008",
                path,
                f"capabilities must be nonempty, unique, and sorted for {raw_name}",
            )
        )
    if not _is_https_url(entry.get("authoritative_registry"), host="pypi.org"):
        findings.append(
            _finding(
                "DEP-IDENTITY-002",
                path,
                f"authoritative_registry must be an HTTPS pypi.org URL for {raw_name}",
            )
        )
    if not _is_https_url(entry.get("authoritative_project_source")):
        findings.append(
            _finding(
                "DEP-IDENTITY-003",
                path,
                f"authoritative_project_source must be an HTTPS URL for {raw_name}",
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
                    f"dependency review date is in the future: {raw_name}",
                )
            )
    except ValueError:
        findings.append(
            _finding(
                "DEP-CONTRACT-003",
                path,
                f"invalid reviewed_on for {raw_name}",
            )
        )
    return name


def audit_dependencies(
    root: Path,
    contract: Mapping[str, Any],
    findings: list[GovernanceFinding],
) -> int:
    """Audit dependency declarations, registry, hashed locks, and Action identities."""

    path = "governance/dependency_contract.toml"
    _audit_contract_policy(root, contract, findings)
    pyproject_path = root / "pyproject.toml"
    if not pyproject_path.is_file():
        findings.append(
            _finding("DEP-PROJECT-001", "pyproject.toml", "project declaration is missing")
        )
        return 0

    direct_raw = _raw_direct_requirements(root)
    parsed_direct = [_parse_exact(value) for value in direct_raw]
    seen_direct: set[str] = set()
    for raw, parsed in zip(direct_raw, parsed_direct, strict=True):
        if parsed is None:
            findings.append(
                _finding(
                    "DEP-PIN-001",
                    "pyproject.toml",
                    f"direct/build dependency must use exact == pin: {raw}",
                )
            )
            continue
        name = parsed[0]
        if name in seen_direct:
            findings.append(
                _finding(
                    "DEP-PIN-002",
                    "pyproject.toml",
                    f"duplicate canonical direct dependency: {name}",
                )
            )
        seen_direct.add(name)
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
    if len(entries) != len(registry):
        findings.append(
            _finding(
                "DEP-CONTRACT-009",
                path,
                "every dependency registry element must be a table",
            )
        )
    by_name: dict[str, Mapping[str, Any]] = {}
    for entry in entries:
        name = _audit_registry_entry(entry, path=path, findings=findings)
        if name is None:
            continue
        if name in by_name:
            findings.append(
                _finding(
                    "DEP-REGISTRY-003",
                    path,
                    f"duplicate canonical dependency registry identity: {name}",
                )
            )
            continue
        by_name[name] = entry
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

    lock_paths = contract.get("lock_files")
    lock_versions: list[tuple[Path, dict[str, str]]] = []
    if not isinstance(lock_paths, list) or not lock_paths:
        findings.append(
            _finding("DEP-LOCK-001", path, "at least one lock file is required")
        )
    else:
        for raw_path in lock_paths:
            lock_path = _safe_relative_path(raw_path)
            if lock_path is None:
                findings.append(
                    _finding(
                        "DEP-LOCK-008",
                        path,
                        f"lock path must be safe and repository-relative: {raw_path}",
                    )
                )
                continue
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
            locked = {entry.name: entry.version for entry in lock_entries}
            lock_versions.append((lock_path, locked))
            missing_names = direct_names - set(locked)
            if missing_names:
                findings.append(
                    _finding(
                        "DEP-LOCK-004",
                        lock_path,
                        f"lock omits direct dependencies: {sorted(missing_names)}",
                    )
                )
            bootstrap = contract.get("bootstrap_distributions", [])
            if isinstance(bootstrap, list):
                for raw in bootstrap:
                    parsed = _parse_exact(str(raw))
                    if parsed is None:
                        continue
                    name, _extras, version = parsed
                    if locked.get(name) != version:
                        findings.append(
                            _finding(
                                "DEP-LOCK-009",
                                lock_path,
                                f"bootstrap distribution disagreement: {name}=={version}",
                            )
                        )
        if len(lock_versions) > 1:
            reference_path, reference = lock_versions[0]
            for lock_path, locked in lock_versions[1:]:
                if locked != reference:
                    findings.append(
                        _finding(
                            "DEP-LOCK-010",
                            lock_path,
                            "supported locks disagree on package/version inventory: "
                            f"reference={reference_path.as_posix()}",
                        )
                    )

    workflow_paths = sorted((root / ".github/workflows").glob("*.y*ml"))
    workflow_text = "\n".join(
        workflow.read_text(encoding="utf-8")
        for workflow in workflow_paths
    )
    for snippet in sorted(_REQUIRED_CI_SNIPPETS):
        if snippet not in workflow_text:
            findings.append(
                _finding(
                    "DEP-CI-001",
                    ".github/workflows",
                    f"mandatory supply-chain CI command is absent: {snippet}",
                )
            )
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
            action = match.group("action")
            if action.startswith("./"):
                continue
            ref = match.group("ref")
            comment = match.group("comment")
            if not re.fullmatch(r"[0-9a-f]{40}", ref):
                findings.append(
                    _finding(
                        "DEP-ACTION-001",
                        relative,
                        "third-party Action is not pinned to an immutable SHA: "
                        f"{action}@{ref}",
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
        if name not in registry:
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
        lock_path = _safe_relative_path(raw_path)
        if lock_path is None:
            continue
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
