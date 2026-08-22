"""Exact top-level and ledger-shape certification for governance contracts."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any, Final

from constructionsight.assurance_certification import (
    ASSURANCE_CONTRACT_FIELDS,
    CANONICAL_ASSURANCE_ARTIFACT,
    audit_assurance_contract,
)
from constructionsight.governance_certification_core import GovernanceFinding, _finding
from constructionsight.repository_path_certification import (
    RepositoryPathError,
    resolve_repository_file,
)

_CONTRACT_FIELDS: Final = {
    "governance/architecture_contract.toml": (
        {"schema_version", "contract_id", "production_root", "prohibit_module_cycles", "layers"},
        {"exceptions"},
    ),
    "governance/capability_contract.toml": (
        {"schema_version", "contract_id", "capabilities"},
        set(),
    ),
    "governance/dependency_contract.toml": (
        {
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
        },
        set(),
    ),
    "governance/network_contract.toml": (
        {
            "schema_version",
            "contract_id",
            "production_scheduling_authorized",
            "concurrent_live_integration_authorized",
            "policies",
        },
        set(),
    ),
    "governance/authorization_contract.toml": (
        {
            "schema_version",
            "contract_id",
            "hosted_identity_supported",
            "tenant_isolation_supported",
            "delegation_supported",
            "impersonation_supported",
            "temporary_elevation_supported",
            "operations",
        },
        set(),
    ),
    "governance/adversarial_test_contract.toml": (
        {"schema_version", "contract_id", "required_categories", "matrices"},
        set(),
    ),
    "governance/mutation_contract.toml": (
        {"schema_version", "contract_id", "execution", "timeout_seconds", "cases"},
        set(),
    ),
    "governance/active_defects.toml": (
        {"schema_version", "certification_requires_zero", "defects"},
        set(),
    ),
    "governance/resolved_defects.toml": (
        {"schema_version", "defects"},
        set(),
    ),
    "governance/open_work.toml": (
        {"schema_version", "overlaps"},
        set(),
    ),
    "governance/vulnerability_exceptions.toml": (
        {"schema_version", "exceptions"},
        set(),
    ),
    "governance/assurance_contract.toml": (
        set(ASSURANCE_CONTRACT_FIELDS),
        set(),
    ),
}
_ACTIVE_DEFECT_FIELDS: Final = {
    "id",
    "severity",
    "area",
    "root_cause",
    "discovered_against",
    "required_resolution",
}
_RESOLVED_DEFECT_FIELDS: Final = _ACTIVE_DEFECT_FIELDS | {
    "resolution_summary",
    "resolution_commit",
    "evidence_paths",
    "regression_tests",
    "review_artifact",
    "reviewed_tree_digest",
}
_OVERLAP_FIELDS: Final = {
    "repository",
    "pull_request",
    "head_commit",
    "status",
    "scope",
    "handling",
    "conflicting_paths",
}
_VULNERABILITY_EXCEPTION_FIELDS: Final = {
    "id",
    "package",
    "version",
    "advisory",
    "severity",
    "owner",
    "reason",
    "compensating_control",
    "issued_on",
    "expires_on",
    "review_evidence",
}
_CANONICAL_REVIEW_ARTIFACT: Final = CANONICAL_ASSURANCE_ARTIFACT


def _nonblank(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def _exact_fields(
    value: Mapping[str, Any],
    expected: set[str],
    *,
    path: str,
    code: str,
    label: str,
    findings: list[GovernanceFinding],
) -> None:
    missing = expected - set(value)
    unknown = set(value) - expected
    if missing or unknown:
        findings.append(
            _finding(
                code,
                path,
                f"{label} fields disagree with schema; "
                f"missing={sorted(missing)}, unknown={sorted(unknown)}",
            )
        )


def _audit_top_level(
    contracts: Mapping[str, Mapping[str, Any]],
    findings: list[GovernanceFinding],
) -> None:
    for path, (required, optional) in _CONTRACT_FIELDS.items():
        payload = contracts.get(path)
        if payload is None:
            findings.append(
                _finding("GOV-SHAPE-001", path, "governance payload was not loaded")
            )
            continue
        missing = required - set(payload)
        unknown = set(payload) - required - optional
        if missing or unknown:
            findings.append(
                _finding(
                    "GOV-SHAPE-002",
                    path,
                    "top-level fields disagree with schema; "
                    f"missing={sorted(missing)}, unknown={sorted(unknown)}",
                )
            )
        if "contract_id" in required and not _nonblank(payload.get("contract_id")):
            findings.append(
                _finding("GOV-SHAPE-003", path, "contract_id must be nonblank trimmed text")
            )


def _audit_policy_boundaries(
    contracts: Mapping[str, Mapping[str, Any]],
    findings: list[GovernanceFinding],
) -> None:
    architecture = contracts["governance/architecture_contract.toml"]
    if architecture.get("production_root") != "src/constructionsight":
        findings.append(
            _finding(
                "GOV-BOUNDARY-001",
                "governance/architecture_contract.toml",
                "production_root must remain src/constructionsight",
            )
        )
    if architecture.get("prohibit_module_cycles") is not True:
        findings.append(
            _finding(
                "GOV-BOUNDARY-002",
                "governance/architecture_contract.toml",
                "module cycles must remain prohibited",
            )
        )

    network = contracts["governance/network_contract.toml"]
    for field in (
        "production_scheduling_authorized",
        "concurrent_live_integration_authorized",
    ):
        if network.get(field) is not False:
            findings.append(
                _finding(
                    "GOV-BOUNDARY-003",
                    "governance/network_contract.toml",
                    f"{field} must remain false until its entry conditions are implemented",
                )
            )

    authorization = contracts["governance/authorization_contract.toml"]
    for field in (
        "hosted_identity_supported",
        "tenant_isolation_supported",
        "delegation_supported",
        "impersonation_supported",
        "temporary_elevation_supported",
    ):
        if authorization.get(field) is not False:
            findings.append(
                _finding(
                    "GOV-BOUNDARY-004",
                    "governance/authorization_contract.toml",
                    f"{field} must remain false until hosted identity controls exist",
                )
            )

    active = contracts["governance/active_defects.toml"]
    if active.get("certification_requires_zero") is not True:
        findings.append(
            _finding(
                "GOV-BOUNDARY-005",
                "governance/active_defects.toml",
                "certification_requires_zero must be true",
            )
        )

    mutation = contracts["governance/mutation_contract.toml"]
    timeout = mutation.get("timeout_seconds")
    if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0:
        findings.append(
            _finding(
                "GOV-BOUNDARY-006",
                "governance/mutation_contract.toml",
                "timeout_seconds must be a positive integer",
            )
        )


def _audit_active_defects(
    payload: Mapping[str, Any],
    findings: list[GovernanceFinding],
) -> set[str]:
    path = "governance/active_defects.toml"
    defects = payload.get("defects")
    if not isinstance(defects, list):
        findings.append(_finding("GOV-LEDGER-001", path, "defects must be an array"))
        return set()
    ids: set[str] = set()
    for defect in defects:
        if not isinstance(defect, dict):
            findings.append(
                _finding("GOV-LEDGER-002", path, "every active defect must be a table")
            )
            continue
        _exact_fields(
            defect,
            _ACTIVE_DEFECT_FIELDS,
            path=path,
            code="GOV-LEDGER-003",
            label="active defect",
            findings=findings,
        )
        defect_id = defect.get("id")
        if not isinstance(defect_id, str) or not re.fullmatch(r"CS-SR-[0-9]{3}", defect_id):
            findings.append(
                _finding("GOV-LEDGER-004", path, "active defect ID must match CS-SR-NNN")
            )
        elif defect_id in ids:
            findings.append(
                _finding("GOV-LEDGER-005", path, f"duplicate active defect ID: {defect_id}")
            )
        else:
            ids.add(defect_id)
        if defect.get("severity") not in {"P0", "P1", "P2", "P3"}:
            findings.append(
                _finding(
                    "GOV-LEDGER-006",
                    path,
                    f"invalid severity for active defect {defect_id}",
                )
            )
        discovered = defect.get("discovered_against")
        if not isinstance(discovered, str) or not re.fullmatch(r"[0-9a-f]{40}", discovered):
            findings.append(
                _finding(
                    "GOV-LEDGER-007",
                    path,
                    f"active defect {defect_id} must bind a full commit SHA",
                )
            )
        for field in ("area", "root_cause", "required_resolution"):
            if not _nonblank(defect.get(field)):
                findings.append(
                    _finding(
                        "GOV-LEDGER-008",
                        path,
                        f"active defect {defect_id}.{field} must be nonblank trimmed text",
                    )
                )
    return ids


def _safe_existing_paths(
    root: Path,
    values: object,
    *,
    require_tests: bool,
) -> bool:
    if (
        not isinstance(values, list)
        or not values
        or not all(_nonblank(value) for value in values)
        or values != sorted(set(values))
    ):
        return False
    for raw_value in values:
        assert isinstance(raw_value, str)
        try:
            resolve_repository_file(
                root,
                raw_value,
                required_prefix="tests" if require_tests else None,
                required_suffix=".py" if require_tests else None,
            )
        except RepositoryPathError:
            return False
    return True


def _audit_resolved_defects(
    root: Path,
    payload: Mapping[str, Any],
    active_ids: set[str],
    findings: list[GovernanceFinding],
) -> None:
    path = "governance/resolved_defects.toml"
    defects = payload.get("defects")
    if not isinstance(defects, list):
        findings.append(_finding("GOV-RESOLVED-001", path, "defects must be an array"))
        return
    ids: set[str] = set()
    for defect in defects:
        if not isinstance(defect, dict):
            findings.append(
                _finding("GOV-RESOLVED-002", path, "every resolved defect must be a table")
            )
            continue
        _exact_fields(
            defect,
            _RESOLVED_DEFECT_FIELDS,
            path=path,
            code="GOV-RESOLVED-003",
            label="resolved defect",
            findings=findings,
        )
        defect_id = defect.get("id")
        if not isinstance(defect_id, str) or not re.fullmatch(r"CS-SR-[0-9]{3}", defect_id):
            findings.append(
                _finding("GOV-RESOLVED-004", path, "resolved defect ID must match CS-SR-NNN")
            )
        elif defect_id in ids:
            findings.append(
                _finding("GOV-RESOLVED-005", path, f"duplicate resolved defect ID: {defect_id}")
            )
        else:
            ids.add(defect_id)
        if isinstance(defect_id, str) and defect_id in active_ids:
            findings.append(
                _finding(
                    "GOV-RESOLVED-006",
                    path,
                    f"defect cannot be both active and resolved: {defect_id}",
                )
            )
        if defect.get("severity") not in {"P0", "P1", "P2", "P3"}:
            findings.append(
                _finding(
                    "GOV-RESOLVED-007",
                    path,
                    f"invalid severity for resolved defect {defect_id}",
                )
            )
        for field in ("discovered_against", "resolution_commit"):
            value = defect.get(field)
            if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value):
                findings.append(
                    _finding(
                        "GOV-RESOLVED-008",
                        path,
                        f"resolved defect {defect_id}.{field} must be a full commit SHA",
                    )
                )
        for field in ("area", "root_cause", "required_resolution", "resolution_summary"):
            if not _nonblank(defect.get(field)):
                findings.append(
                    _finding(
                        "GOV-RESOLVED-009",
                        path,
                        f"resolved defect {defect_id}.{field} must be nonblank trimmed text",
                    )
                )
        if not _safe_existing_paths(
            root,
            defect.get("evidence_paths"),
            require_tests=False,
        ):
            findings.append(
                _finding(
                    "GOV-RESOLVED-010",
                    path,
                    f"resolved defect {defect_id}.evidence_paths must be safe, existing, "
                    "unique, and sorted",
                )
            )
        if not _safe_existing_paths(
            root,
            defect.get("regression_tests"),
            require_tests=True,
        ):
            findings.append(
                _finding(
                    "GOV-RESOLVED-011",
                    path,
                    f"resolved defect {defect_id}.regression_tests must be safe existing "
                    "tests, unique, and sorted",
                )
            )
        review_artifact = defect.get("review_artifact")
        review_path: Path | None = None
        if review_artifact == _CANONICAL_REVIEW_ARTIFACT:
            try:
                _relative, review_path = resolve_repository_file(
                    root,
                    _CANONICAL_REVIEW_ARTIFACT,
                    required_prefix="governance/reviews",
                    required_suffix=".json",
                )
            except RepositoryPathError:
                review_path = None
        if review_path is None:
            findings.append(
                _finding(
                    "GOV-RESOLVED-012",
                    path,
                    f"resolved defect {defect_id} must reference the existing canonical "
                    "assurance artifact",
                )
            )
        reviewed_tree_digest = defect.get("reviewed_tree_digest")
        if not isinstance(reviewed_tree_digest, str) or not re.fullmatch(
            r"[0-9a-f]{64}", reviewed_tree_digest
        ):
            findings.append(
                _finding(
                    "GOV-RESOLVED-013",
                    path,
                    f"resolved defect {defect_id}.reviewed_tree_digest must be a lowercase "
                    "SHA-256 digest",
                )
            )
        elif review_path is not None:
            try:
                review_payload = json.loads(review_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                findings.append(
                    _finding(
                        "GOV-RESOLVED-014",
                        path,
                        f"resolved defect {defect_id} cannot verify malformed "
                        "assurance evidence",
                    )
                )
            else:
                if not isinstance(review_payload, dict) or review_payload.get(
                    "reviewed_tree_digest"
                ) != reviewed_tree_digest:
                    findings.append(
                        _finding(
                            "GOV-RESOLVED-015",
                            path,
                            f"resolved defect {defect_id} does not bind the canonical "
                            "reviewed-tree digest",
                        )
                    )


def _audit_open_work(
    payload: Mapping[str, Any],
    findings: list[GovernanceFinding],
) -> None:
    path = "governance/open_work.toml"
    overlaps = payload.get("overlaps")
    if not isinstance(overlaps, list):
        findings.append(_finding("GOV-OVERLAP-001", path, "overlaps must be an array"))
        return
    identities: set[tuple[str, int]] = set()
    for overlap in overlaps:
        if not isinstance(overlap, dict):
            findings.append(
                _finding("GOV-OVERLAP-002", path, "every overlap must be a table")
            )
            continue
        _exact_fields(
            overlap,
            _OVERLAP_FIELDS,
            path=path,
            code="GOV-OVERLAP-003",
            label="overlap",
            findings=findings,
        )
        repository = overlap.get("repository")
        pull_request = overlap.get("pull_request")
        if not _nonblank(repository) or isinstance(pull_request, bool) or not isinstance(
            pull_request, int
        ) or pull_request <= 0:
            findings.append(
                _finding("GOV-OVERLAP-004", path, "overlap repository/PR identity is invalid")
            )
        elif (repository, pull_request) in identities:
            findings.append(
                _finding(
                    "GOV-OVERLAP-005",
                    path,
                    f"duplicate overlap identity: {repository}#{pull_request}",
                )
            )
        else:
            assert isinstance(repository, str)
            identities.add((repository, pull_request))
        head = overlap.get("head_commit")
        if not isinstance(head, str) or not re.fullmatch(r"[0-9a-f]{40}", head):
            findings.append(
                _finding("GOV-OVERLAP-006", path, "overlap head_commit must be a full SHA")
            )
        paths = overlap.get("conflicting_paths")
        if (
            not isinstance(paths, list)
            or not paths
            or not all(_nonblank(value) for value in paths)
            or paths != sorted(set(paths))
            or any(Path(value).is_absolute() or ".." in Path(value).parts for value in paths)
        ):
            findings.append(
                _finding(
                    "GOV-OVERLAP-007",
                    path,
                    "conflicting_paths must be nonempty, safe, unique, and sorted",
                )
            )
        for field in ("status", "scope", "handling"):
            if not _nonblank(overlap.get(field)):
                findings.append(
                    _finding(
                        "GOV-OVERLAP-008",
                        path,
                        f"overlap {field} must be nonblank trimmed text",
                    )
                )


def _audit_vulnerability_exceptions(
    payload: Mapping[str, Any],
    root: Path,
    findings: list[GovernanceFinding],
) -> None:
    path = "governance/vulnerability_exceptions.toml"
    exceptions = payload.get("exceptions")
    if not isinstance(exceptions, list):
        findings.append(
            _finding("GOV-VULN-001", path, "exceptions must be an array")
        )
        return
    ids: set[str] = set()
    for exception in exceptions:
        if not isinstance(exception, dict):
            findings.append(
                _finding("GOV-VULN-002", path, "every exception must be a table")
            )
            continue
        _exact_fields(
            exception,
            _VULNERABILITY_EXCEPTION_FIELDS,
            path=path,
            code="GOV-VULN-003",
            label="vulnerability exception",
            findings=findings,
        )
        exception_id = exception.get("id")
        if not isinstance(exception_id, str) or not re.fullmatch(
            r"CS-VULN-[0-9]{3}", exception_id
        ):
            findings.append(
                _finding("GOV-VULN-004", path, "exception ID must match CS-VULN-NNN")
            )
        elif exception_id in ids:
            findings.append(
                _finding("GOV-VULN-005", path, f"duplicate exception ID: {exception_id}")
            )
        else:
            ids.add(exception_id)
        try:
            issued = date.fromisoformat(str(exception.get("issued_on")))
            expires = date.fromisoformat(str(exception.get("expires_on")))
            if issued > expires or expires < date.today():
                raise ValueError
        except ValueError:
            findings.append(
                _finding(
                    "GOV-VULN-006",
                    path,
                    f"exception {exception_id} has invalid or expired dates",
                )
            )
        evidence = exception.get("review_evidence")
        try:
            resolve_repository_file(root, evidence)
        except RepositoryPathError:
            findings.append(
                _finding(
                    "GOV-VULN-007",
                    path,
                    f"exception {exception_id} review evidence is missing or unsafe",
                )
            )
        for field in (
            "package",
            "version",
            "advisory",
            "severity",
            "owner",
            "reason",
            "compensating_control",
        ):
            if not _nonblank(exception.get(field)):
                findings.append(
                    _finding(
                        "GOV-VULN-008",
                        path,
                        f"exception {exception_id}.{field} must be nonblank trimmed text",
                    )
                )


def audit_governance_contract_shapes(
    root: Path,
    contracts: Mapping[str, Mapping[str, Any]],
    findings: list[GovernanceFinding],
) -> None:
    """Reject unknown, missing, malformed, or authority-expanding governance fields."""

    _audit_top_level(contracts, findings)
    if any(path not in contracts for path in _CONTRACT_FIELDS):
        return
    _audit_policy_boundaries(contracts, findings)
    active_ids = _audit_active_defects(
        contracts["governance/active_defects.toml"], findings
    )
    _audit_resolved_defects(
        root,
        contracts["governance/resolved_defects.toml"],
        active_ids,
        findings,
    )
    _audit_open_work(contracts["governance/open_work.toml"], findings)
    _audit_vulnerability_exceptions(
        contracts["governance/vulnerability_exceptions.toml"],
        root,
        findings,
    )
    audit_assurance_contract(
        contracts["governance/assurance_contract.toml"],
        findings,
    )
