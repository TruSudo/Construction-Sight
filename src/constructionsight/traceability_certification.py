"""Capability and dependency traceability certification."""

from __future__ import annotations

import re
import tomllib
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

from constructionsight.governance_certification_core import (
    GovernanceFinding,
    _finding,
    _module_name,
)
from constructionsight.repository_path_certification import (
    RepositoryPathError,
    resolve_repository_file,
)


def _match_contract_owner(
    display_path: str,
    entries: Sequence[Mapping[str, Any]],
    *,
    patterns_field: str,
    default_field: str,
    contract_path: str,
    findings: list[GovernanceFinding],
) -> list[Mapping[str, Any]]:
    explicit: list[Mapping[str, Any]] = []
    defaults: list[Mapping[str, Any]] = []
    for entry in entries:
        if entry.get(default_field) is True:
            defaults.append(entry)
            continue
        patterns = entry.get(patterns_field)
        if not isinstance(patterns, list):
            continue
        try:
            if any(re.fullmatch(str(pattern), display_path) for pattern in patterns):
                explicit.append(entry)
        except re.error as exc:
            findings.append(
                _finding(
                    "GOV-CONTRACT-005",
                    contract_path,
                    f"invalid ownership pattern: {exc}",
                )
            )
    return explicit if explicit else defaults


def _audit_capabilities(
    root: Path,
    tracked: tuple[Path, ...],
    contract: Mapping[str, Any],
    layer_by_module: Mapping[str, str],
    findings: list[GovernanceFinding],
) -> int:
    path = "governance/capability_contract.toml"
    raw_entries = contract.get("capabilities")
    if not isinstance(raw_entries, list) or not raw_entries:
        findings.append(_finding("CAP-CONTRACT-001", path, "at least one capability is required"))
        return 0
    entries = [entry for entry in raw_entries if isinstance(entry, dict)]
    ids: set[str] = set()
    defaults = 0
    allowed_statuses = {
        "implemented",
        "guarded",
        "planned",
        "externally_blocked",
        "deprecated",
    }
    required = {
        "id",
        "status",
        "business_intent",
        "owning_layer",
        "module_patterns",
        "default_owner",
        "tests",
        "doctrine",
        "adrs",
        "persistence",
        "operator_exposure",
        "network_authority",
        "mutation_authority",
        "authorization_model",
        "provenance_rule",
        "compatibility_rule",
        "failure_rule",
        "limitation_rule",
        "negative_constraints",
        "future_entry_conditions",
        "replacement",
        "network_policy_ids",
        "authorization_operation_ids",
    }
    for entry in entries:
        unknown = set(entry) - required
        missing = required - set(entry)
        if unknown or missing:
            findings.append(
                _finding(
                    "CAP-CONTRACT-002",
                    path,
                    "capability fields disagree with schema; "
                    f"missing={sorted(missing)}, unknown={sorted(unknown)}",
                )
            )
            continue
        capability_id = entry.get("id")
        if not isinstance(capability_id, str) or not re.fullmatch(
            r"CS-CAP-[0-9]{3}", capability_id
        ):
            findings.append(
                _finding("CAP-CONTRACT-003", path, "capability ID must match CS-CAP-NNN")
            )
            continue
        if capability_id in ids:
            findings.append(
                _finding("CAP-CONTRACT-004", path, f"duplicate capability {capability_id}")
            )
        ids.add(capability_id)
        defaults += int(entry.get("default_owner") is True)
        if entry.get("status") not in allowed_statuses:
            findings.append(
                _finding("CAP-CONTRACT-005", path, f"unsupported status for {capability_id}")
            )
        for artifact_field in ("tests", "doctrine", "adrs"):
            values = entry.get(artifact_field)
            if not isinstance(values, list):
                findings.append(
                    _finding(
                        "CAP-CONTRACT-006",
                        path,
                        f"{capability_id}.{artifact_field} must be an array",
                    )
                )
                continue
            for value in values:
                required_prefix = {
                    "tests": "tests",
                    "doctrine": "docs",
                    "adrs": "docs",
                }[artifact_field]
                required_suffix = ".py" if artifact_field == "tests" else ".md"
                try:
                    resolve_repository_file(
                        root,
                        value,
                        required_prefix=required_prefix,
                        required_suffix=required_suffix,
                    )
                except RepositoryPathError:
                    findings.append(
                        _finding(
                            "CAP-ARTIFACT-001",
                            path,
                            f"{capability_id} references missing or unsafe {artifact_field} "
                            f"artifact: {value}",
                        )
                    )
        negative = entry.get("negative_constraints")
        if not isinstance(negative, list) or not negative:
            findings.append(
                _finding(
                    "CAP-CONTRACT-007",
                    path,
                    f"{capability_id} requires explicit negative constraints",
                )
            )
        if entry.get("status") in {"planned", "externally_blocked"}:
            future = entry.get("future_entry_conditions")
            if not isinstance(future, list) or not future:
                findings.append(
                    _finding(
                        "CAP-CONTRACT-008",
                        path,
                        f"{capability_id} requires future entry conditions",
                    )
                )
        if entry.get("status") == "deprecated" and not entry.get("replacement"):
            findings.append(
                _finding(
                    "CAP-CONTRACT-009",
                    path,
                    f"deprecated {capability_id} requires replacement/removal doctrine",
                )
            )
        if entry.get("network_authority") is True and not entry.get(
            "network_policy_ids"
        ):
            findings.append(
                _finding(
                    "CAP-POLICY-001",
                    path,
                    f"network capability {capability_id} lacks network policy IDs",
                )
            )
        if entry.get("mutation_authority") is True and not entry.get(
            "authorization_operation_ids"
        ):
            findings.append(
                _finding(
                    "CAP-POLICY-002",
                    path,
                    f"mutation capability {capability_id} lacks authorization operation IDs",
                )
            )
        if entry.get("authorization_model") == "boolean":
            findings.append(
                _finding(
                    "CAP-AUTH-001",
                    path,
                    f"{capability_id} uses prohibited boolean-only authorization",
                )
            )
    if defaults != 1:
        findings.append(
            _finding(
                "CAP-CONTRACT-010",
                path,
                "exactly one default capability owner is required",
            )
        )

    module_paths = tuple(
        candidate
        for candidate in tracked
        if candidate.as_posix().startswith("src/constructionsight/")
        and candidate.suffix == ".py"
    )
    matched_counts: defaultdict[str, int] = defaultdict(int)
    for module_path in module_paths:
        owners = _match_contract_owner(
            module_path.as_posix(),
            entries,
            patterns_field="module_patterns",
            default_field="default_owner",
            contract_path=path,
            findings=findings,
        )
        if len(owners) != 1:
            findings.append(
                _finding(
                    "CAP-OWNER-001",
                    module_path,
                    "production module must have exactly one capability owner, "
                    f"found {len(owners)}",
                )
            )
            continue
        owner = owners[0]
        owner_id = str(owner.get("id"))
        matched_counts[owner_id] += 1
        module = _module_name(module_path)
        architecture_layer = layer_by_module.get(module)
        if owner.get("owning_layer") != architecture_layer:
            findings.append(
                _finding(
                    "CAP-OWNER-002",
                    module_path,
                    f"capability {owner_id} owning layer {owner.get('owning_layer')} "
                    f"disagrees with architecture layer {architecture_layer}",
                )
            )
        if owner.get("status") in {"planned", "externally_blocked"}:
            findings.append(
                _finding(
                    "CAP-RUNTIME-001",
                    module_path,
                    f"planned/blocked capability {owner_id} is exposed by production code",
                )
            )
    for entry in entries:
        capability_id = str(entry.get("id"))
        if entry.get("status") in {"implemented", "guarded"} and not matched_counts[
            capability_id
        ]:
            findings.append(
                _finding(
                    "CAP-OWNER-003",
                    path,
                    f"implemented capability {capability_id} owns no production module",
                )
            )
    return len(entries)


def _canonical_distribution(raw: str) -> tuple[str, str | None, str | None]:
    match = re.fullmatch(
        r"([A-Za-z0-9_.-]+)(\[[A-Za-z0-9_,.-]+\])?==([^;\s]+)",
        raw.strip(),
    )
    if not match:
        return re.sub(r"[-_.]+", "-", raw.strip()).lower(), None, None
    name = re.sub(r"[-_.]+", "-", match.group(1)).lower()
    extras = match.group(2)
    return name, extras[1:-1] if extras else None, match.group(3)


def _audit_dependencies(
    root: Path,
    contract: Mapping[str, Any],
    findings: list[GovernanceFinding],
) -> int:
    path = "governance/dependency_contract.toml"
    try:
        _relative, pyproject_path = resolve_repository_file(root, "pyproject.toml")
    except RepositoryPathError:
        return 0
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    direct_raw: list[str] = []
    project = pyproject.get("project", {})
    direct_raw.extend(str(value) for value in project.get("dependencies", []))
    for values in project.get("optional-dependencies", {}).values():
        direct_raw.extend(str(value) for value in values)
    direct_raw.extend(
        str(value) for value in pyproject.get("build-system", {}).get("requires", [])
    )
    parsed = [_canonical_distribution(value) for value in direct_raw]
    for raw, (_, _, version) in zip(direct_raw, parsed, strict=True):
        if version is None:
            findings.append(
                _finding(
                    "DEP-PIN-001",
                    "pyproject.toml",
                    f"direct/build dependency must use exact == pin: {raw}",
                )
            )

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
    by_name = {str(entry.get("name")): entry for entry in entries}
    direct_names = {name for name, _, _ in parsed}
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
        findings.append(_finding("DEP-LOCK-001", path, "at least one lock file is required"))
    else:
        for lock_path in lock_paths:
            try:
                _relative, lock = resolve_repository_file(
                    root,
                    lock_path,
                    required_prefix="requirements",
                    required_suffix=".lock",
                )
            except RepositoryPathError:
                findings.append(
                    _finding(
                        "DEP-LOCK-002",
                        str(lock_path),
                        "declared lock file is missing or unsafe",
                    )
                )
                continue
            lock_names: set[str] = set()
            for number, line in enumerate(
                lock.read_text(encoding="utf-8").splitlines(), start=1
            ):
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                name, _, version = _canonical_distribution(stripped)
                if version is None:
                    findings.append(
                        _finding(
                            "DEP-LOCK-003",
                            str(lock_path),
                            f"lock entry is not exact: {stripped}",
                            number,
                        )
                    )
                lock_names.add(name)
            missing_names = direct_names - lock_names
            if missing_names:
                findings.append(
                    _finding(
                        "DEP-LOCK-004",
                        str(lock_path),
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
