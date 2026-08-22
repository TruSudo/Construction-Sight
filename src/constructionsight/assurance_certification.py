"""Native-maximum assurance policy, evidence, and exact-tree certification."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final, cast

from constructionsight.defect_closure_certification import audit_defect_closure
from constructionsight.governance_certification_core import (
    _ASSURANCE_CONTRACT_SCHEMA,
    _ASSURANCE_REVIEW_SCHEMA,
    GovernanceContractError,
    GovernanceFinding,
    _finding,
)
from constructionsight.repository_path_certification import (
    RepositoryPathError,
    resolve_repository_file,
)

CANONICAL_ASSURANCE_ARTIFACT: Final = "governance/reviews/assurance_review.json"
ASSURANCE_EVIDENCE_PREFIX: Final = "governance/reviews/evidence"

ASSURANCE_CONTRACT_FIELDS: Final = frozenset(
    {
        "schema_version",
        "contract_id",
        "operating_model",
        "required_mode",
        "canonical_artifact",
        "allowed_modes",
        "minimum_context_isolated_passes",
        "minimum_deep_standard_passes",
        "required_native_pass_kinds",
        "blind_candidate_union_required",
        "complete_coverage_required",
        "unresolved_candidates_allowed",
        "deferred_candidates_allowed",
        "coverage_gaps_allowed",
        "surviving_security_mutants_allowed",
        "exact_commit_binding_required",
        "exact_tree_binding_required",
        "owner_acceptance_required",
        "change_invalidates_assurance",
        "external_model_required",
        "external_model_counts_as_human",
        "independent_human_required",
        "none_mode_allowed",
        "bypass_allowed",
        "self_approval_counts_as_independent_human",
        "required_quality_gates",
    }
)

_ASSURANCE_REVIEW_FIELDS: Final = frozenset(
    {
        "schema_version",
        "status",
        "assurance_mode",
        "independence_claim",
        "owner",
        "owner_acceptance",
        "reviewer",
        "review_method",
        "reviewed_commit",
        "reviewed_active_defects_digest",
        "reviewed_tree_digest",
        "pull_request_number",
        "surviving_security_mutants",
        "passes",
        "candidate_union",
        "quality_gates",
        "limitations",
    }
)
_PASS_FIELDS: Final = frozenset(
    {
        "pass_id",
        "kind",
        "reviewer",
        "provider",
        "model",
        "fresh_context",
        "completed_reviews",
        "status",
        "artifact_path",
        "artifact_sha256",
        "candidate_count",
        "coverage_complete",
        "coverage_gap_count",
        "unresolved_candidate_count",
        "deferred_candidate_count",
    }
)
_PASS_EVIDENCE_FIELDS: Final = frozenset(
    {
        "schema_version",
        "pass_id",
        "kind",
        "reviewed_commit",
        "status",
        "fresh_context",
        "completed_reviews",
        "candidate_count",
        "coverage_complete",
        "coverage_gap_count",
        "unresolved_candidate_count",
        "deferred_candidate_count",
        "tool",
        "source_artifact_sha256",
    }
)
_CANDIDATE_UNION_REFERENCE_FIELDS: Final = frozenset(
    {"artifact_path", "artifact_sha256"}
)
_CANDIDATE_UNION_FIELDS: Final = frozenset(
    {
        "schema_version",
        "reviewed_commit",
        "blind_union",
        "source_pass_ids",
        "coverage_complete",
        "coverage_gaps",
        "candidates",
    }
)
_CANDIDATE_FIELDS: Final = frozenset(
    {
        "id",
        "source_pass_ids",
        "severity",
        "disposition",
        "rationale",
        "resolution_commit",
        "evidence_paths",
    }
)
_QUALITY_GATE_FIELDS: Final = frozenset(
    {"gate_id", "status", "artifact_path", "artifact_sha256"}
)
_QUALITY_GATE_EVIDENCE_FIELDS: Final = frozenset(
    {"schema_version", "reviewed_commit", "gates"}
)
_QUALITY_GATE_RESULT_FIELDS: Final = frozenset(
    {"gate_id", "status", "source_artifact_sha256"}
)

_ALLOWED_MODES: Final = frozenset(
    {"native_maximum", "independent_external_model", "independent_human"}
)
_NATIVE_PASS_KINDS: Final = frozenset(
    {"deep_repository", "exact_diff", "adversarial_invariant"}
)
_PASS_KINDS: Final = _NATIVE_PASS_KINDS | {
    "external_model",
    "independent_human",
}
_MANDATORY_QUALITY_GATES: Final = frozenset(
    {
        "adapter-audit",
        "architecture-certification",
        "capability-certification",
        "compileall-py311",
        "compileall-py312",
        "dependency-integrity-py311",
        "dependency-integrity-py312",
        "diff-hygiene",
        "exact-checkout-py311",
        "exact-checkout-py312",
        "governance-contract-certification",
        "lock-verification-py311",
        "lock-verification-py312",
        "mypy-strict",
        "pytest-py311",
        "pytest-py312",
        "ruff",
        "sbom-py311",
        "sbom-py312",
        "security-mutation",
        "semantic-authorization-certification",
        "source-coverage-audit",
        "vulnerability-audit-py311",
        "vulnerability-audit-py312",
    }
)
_MODE_LIMITATION: Final = {
    "native_maximum": "no_independent_external_model_or_human_review",
    "independent_external_model": "external_model_review_is_not_human_approval",
    "independent_human": "human_review_does_not_replace_native_assurance",
}
_MODE_CLAIM: Final = {
    "native_maximum": "native_context_isolated_not_independent",
    "independent_external_model": "independent_external_model_not_human",
    "independent_human": "independent_human",
}
_ALLOWED_AFTER_ASSURANCE_EXACT: Final = frozenset(
    {
        "governance/active_defects.toml",
        "governance/resolved_defects.toml",
        "docs/audits/silent_risk_certification_2026-07-15.md",
    }
)
_ALLOWED_AFTER_ASSURANCE_PREFIXES: Final = ("governance/reviews/",)
_ASSURED_TREE_DOMAIN: Final = b"constructionsight.assured-tree/v1\0"
_COMMIT_PATTERN: Final = re.compile(r"[0-9a-f]{40}")
_DIGEST_PATTERN: Final = re.compile(r"[0-9a-f]{64}")
_PASS_ID_PATTERN: Final = re.compile(r"[a-z][a-z0-9-]{2,79}")
_CANDIDATE_ID_PATTERN: Final = re.compile(r"CS-AC-[0-9]{3}")
_CANDIDATE_UNION_SCHEMA: Final = "constructionsight.assurance-candidate-union/v1"
_PASS_EVIDENCE_SCHEMA: Final = "constructionsight.assurance-pass-evidence/v1"
_QUALITY_GATE_EVIDENCE_SCHEMA: Final = "constructionsight.assurance-quality-gates/v1"


def _nonblank(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def _positive_integer(value: object) -> bool:
    return not isinstance(value, bool) and isinstance(value, int) and value > 0


def _nonnegative_integer(value: object) -> bool:
    return not isinstance(value, bool) and isinstance(value, int) and value >= 0


def _record(
    findings: list[GovernanceFinding],
    code: str,
    path: str | Path,
    message: str,
) -> None:
    findings.append(_finding(code, path, message))


def _exact_fields(
    value: Mapping[str, Any],
    expected: frozenset[str],
    *,
    findings: list[GovernanceFinding],
    code: str,
    path: str,
    label: str,
) -> bool:
    missing = expected - set(value)
    unknown = set(value) - expected
    if not missing and not unknown:
        return True
    _record(
        findings,
        code,
        path,
        f"{label} fields disagree with schema; "
        f"missing={sorted(missing)}, unknown={sorted(unknown)}",
    )
    return False


def _canonical_strings(value: object, *, nonempty: bool = True) -> list[str] | None:
    if not isinstance(value, list) or (nonempty and not value):
        return None
    if not all(_nonblank(item) for item in value):
        return None
    strings = [str(item) for item in value]
    if strings != sorted(set(strings)):
        return None
    return strings


def audit_assurance_contract(
    contract: Mapping[str, Any],
    findings: list[GovernanceFinding],
) -> None:
    """Reject any weakening or ambiguous expansion of the assurance policy."""

    path = "governance/assurance_contract.toml"
    _exact_fields(
        contract,
        ASSURANCE_CONTRACT_FIELDS,
        findings=findings,
        code="ASSURANCE-POLICY-001",
        path=path,
        label="assurance contract",
    )
    if contract.get("schema_version") != _ASSURANCE_CONTRACT_SCHEMA:
        _record(findings, "ASSURANCE-POLICY-002", path, "unsupported assurance schema")
    expected_scalars: dict[str, object] = {
        "operating_model": "private-open-source-solo-maintained",
        "required_mode": "native_maximum",
        "canonical_artifact": CANONICAL_ASSURANCE_ARTIFACT,
        "blind_candidate_union_required": True,
        "complete_coverage_required": True,
        "unresolved_candidates_allowed": 0,
        "deferred_candidates_allowed": 0,
        "coverage_gaps_allowed": 0,
        "surviving_security_mutants_allowed": 0,
        "exact_commit_binding_required": True,
        "exact_tree_binding_required": True,
        "owner_acceptance_required": True,
        "change_invalidates_assurance": True,
        "external_model_required": False,
        "external_model_counts_as_human": False,
        "independent_human_required": False,
        "none_mode_allowed": False,
        "bypass_allowed": False,
        "self_approval_counts_as_independent_human": False,
    }
    weakened = {
        field: contract.get(field)
        for field, expected in expected_scalars.items()
        if contract.get(field) != expected
    }
    if weakened:
        _record(
            findings,
            "ASSURANCE-POLICY-003",
            path,
            f"mandatory assurance invariants changed: {weakened}",
        )
    allowed_modes = _canonical_strings(contract.get("allowed_modes"))
    if allowed_modes is None or set(allowed_modes) != _ALLOWED_MODES:
        _record(
            findings,
            "ASSURANCE-POLICY-004",
            path,
            "allowed_modes must contain exactly the three cumulative assurance modes",
        )
    required_kinds = _canonical_strings(contract.get("required_native_pass_kinds"))
    if required_kinds is None or set(required_kinds) != _NATIVE_PASS_KINDS:
        _record(
            findings,
            "ASSURANCE-POLICY-005",
            path,
            "all three native analytical pass kinds are mandatory",
        )
    context_passes = contract.get("minimum_context_isolated_passes")
    deep_passes = contract.get("minimum_deep_standard_passes")
    if not _positive_integer(context_passes) or cast(int, context_passes) < 5:
        _record(
            findings,
            "ASSURANCE-POLICY-006",
            path,
            "minimum_context_isolated_passes may not be lower than five",
        )
    if not _positive_integer(deep_passes) or cast(int, deep_passes) < 3:
        _record(
            findings,
            "ASSURANCE-POLICY-007",
            path,
            "minimum_deep_standard_passes may not be lower than three",
        )
    quality_gates = _canonical_strings(contract.get("required_quality_gates"))
    if quality_gates is None or not _MANDATORY_QUALITY_GATES.issubset(quality_gates):
        missing = sorted(
            _MANDATORY_QUALITY_GATES - set(quality_gates or [])
        )
        _record(
            findings,
            "ASSURANCE-POLICY-008",
            path,
            f"mandatory quality gates are missing or noncanonical: {missing}",
        )


def _run_git(root: Path, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=False,
            capture_output=True,
        )
    except OSError as exc:
        raise GovernanceContractError(f"cannot execute git: {exc}") from exc


def _git_error(completed: subprocess.CompletedProcess[bytes]) -> str:
    return (
        completed.stderr.decode("utf-8", errors="replace").strip()
        or completed.stdout.decode("utf-8", errors="replace").strip()
        or "unknown git error"
    )


def _commit_exists(root: Path, commit: str) -> bool:
    return _run_git(root, "cat-file", "-e", f"{commit}^{{commit}}").returncode == 0


def _is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    completed = _run_git(root, "merge-base", "--is-ancestor", ancestor, descendant)
    if completed.returncode == 0:
        return True
    if completed.returncode == 1:
        return False
    raise GovernanceContractError(f"cannot verify commit ancestry: {_git_error(completed)}")


def _allowed_after_assurance(path: bytes) -> bool:
    if path.decode("utf-8", errors="surrogateescape") in _ALLOWED_AFTER_ASSURANCE_EXACT:
        return True
    return any(
        path.startswith(prefix.encode("utf-8"))
        for prefix in _ALLOWED_AFTER_ASSURANCE_PREFIXES
    )


def _assert_assurance_worktree_clean(root: Path) -> None:
    command = [
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--",
        ".",
        *(f":(exclude){path}" for path in sorted(_ALLOWED_AFTER_ASSURANCE_EXACT)),
        ":(exclude)governance/reviews/**",
    ]
    completed = _run_git(root, *command)
    if completed.returncode != 0:
        raise GovernanceContractError(_git_error(completed))
    if completed.stdout:
        dirty = completed.stdout.replace(b"\0", b"\n").decode(
            "utf-8", errors="replace"
        ).strip()
        raise GovernanceContractError(
            "assurance-covered worktree is dirty outside permitted finalization "
            f"paths: {dirty}"
        )


def assured_tree_digest(root: Path) -> str:
    """Return a topology-independent digest of the frozen assurance-covered tree."""

    _assert_assurance_worktree_clean(root)
    completed = _run_git(root, "ls-files", "--stage", "-z")
    if completed.returncode != 0:
        raise GovernanceContractError(_git_error(completed))

    entries: list[tuple[bytes, bytes, bytes]] = []
    for raw_entry in completed.stdout.split(b"\0"):
        if not raw_entry:
            continue
        metadata, separator, path = raw_entry.partition(b"\t")
        fields = metadata.split()
        if not separator or len(fields) != 3:
            raise GovernanceContractError("git index entry has an unexpected shape")
        mode, object_id, stage = fields
        if stage != b"0":
            display_path = path.decode("utf-8", errors="replace")
            raise GovernanceContractError(
                f"git index contains an unresolved stage for {display_path!r}"
            )
        if _allowed_after_assurance(path):
            continue
        entries.append((path, mode, object_id))

    digest = hashlib.sha256()
    digest.update(_ASSURED_TREE_DOMAIN)
    for path, mode, object_id in sorted(entries, key=lambda entry: entry[0]):
        digest.update(len(path).to_bytes(8, byteorder="big"))
        digest.update(path)
        digest.update(b"\0")
        digest.update(mode)
        digest.update(b"\0")
        digest.update(object_id)
        digest.update(b"\0")
    return digest.hexdigest()


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON object from {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload at {path} must be an object")
    return payload


def _evidence_artifact(
    root: Path,
    raw_path: object,
    raw_digest: object,
    *,
    findings: list[GovernanceFinding],
    label: str,
) -> tuple[str, dict[str, Any]] | None:
    report_path = CANONICAL_ASSURANCE_ARTIFACT
    if not _nonblank(raw_path) or not isinstance(raw_digest, str) or not _DIGEST_PATTERN.fullmatch(
        raw_digest
    ):
        _record(
            findings,
            "ASSURANCE-010",
            report_path,
            f"{label} must bind a safe JSON path and lowercase SHA-256 digest",
        )
        return None
    assert isinstance(raw_path, str)
    try:
        canonical_path, path = resolve_repository_file(
            root,
            raw_path,
            required_prefix=ASSURANCE_EVIDENCE_PREFIX,
            required_suffix=".json",
        )
    except RepositoryPathError:
        _record(
            findings,
            "ASSURANCE-010",
            report_path,
            f"{label} references missing or unsafe evidence: {raw_path}",
        )
        return None
    try:
        content = path.read_bytes()
        payload = json.loads(content.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        _record(
            findings,
            "ASSURANCE-010",
            report_path,
            f"{label} evidence is not a readable JSON object: {exc}",
        )
        return None
    if not isinstance(payload, dict):
        _record(
            findings,
            "ASSURANCE-010",
            report_path,
            f"{label} evidence must be a JSON object",
        )
        return None
    actual_digest = hashlib.sha256(content).hexdigest()
    if actual_digest != raw_digest:
        _record(
            findings,
            "ASSURANCE-010",
            report_path,
            f"{label} evidence digest does not match {canonical_path.as_posix()}",
        )
        return None
    return canonical_path.as_posix(), payload


def _audit_passes(
    root: Path,
    raw_passes: object,
    contract: Mapping[str, Any],
    reviewed_commit: object,
    findings: list[GovernanceFinding],
) -> tuple[dict[str, Mapping[str, Any]], set[str]]:
    path = CANONICAL_ASSURANCE_ARTIFACT
    if not isinstance(raw_passes, list) or not raw_passes:
        _record(findings, "ASSURANCE-008", path, "passes must be a nonempty array")
        return {}, set()
    passes: dict[str, Mapping[str, Any]] = {}
    evidence_paths: set[str] = set()
    evidence_owners: dict[str, str] = {}
    native_review_count = 0
    deep_review_count = 0
    for index, raw in enumerate(raw_passes):
        label = f"passes[{index}]"
        if not isinstance(raw, dict):
            _record(findings, "ASSURANCE-008", path, f"{label} must be an object")
            continue
        _exact_fields(
            raw,
            _PASS_FIELDS,
            findings=findings,
            code="ASSURANCE-008",
            path=path,
            label=label,
        )
        pass_id = raw.get("pass_id")
        kind = raw.get("kind")
        if (
            not isinstance(pass_id, str)
            or _PASS_ID_PATTERN.fullmatch(pass_id) is None
            or pass_id in passes
        ):
            _record(
                findings,
                "ASSURANCE-008",
                path,
                f"{label}.pass_id is malformed or duplicated",
            )
            continue
        passes[pass_id] = raw
        if kind not in _PASS_KINDS:
            _record(findings, "ASSURANCE-008", path, f"{pass_id}.kind is unsupported")
        for field in ("reviewer", "provider", "model"):
            if not _nonblank(raw.get(field)):
                _record(
                    findings,
                    "ASSURANCE-008",
                    path,
                    f"{pass_id}.{field} must be nonblank trimmed text",
                )
        if raw.get("fresh_context") is not True:
            _record(
                findings,
                "ASSURANCE-009",
                path,
                f"{pass_id} was not a fresh-context pass",
            )
        completed_reviews = raw.get("completed_reviews")
        if not _positive_integer(completed_reviews):
            _record(
                findings,
                "ASSURANCE-008",
                path,
                f"{pass_id}.completed_reviews must be positive",
            )
            completed_count = 0
        else:
            completed_count = cast(int, completed_reviews)
        if raw.get("status") != "passed":
            _record(findings, "ASSURANCE-009", path, f"{pass_id} has not passed")
        if raw.get("coverage_complete") is not True:
            _record(findings, "ASSURANCE-009", path, f"{pass_id} coverage is incomplete")
        for field in (
            "candidate_count",
            "coverage_gap_count",
            "unresolved_candidate_count",
            "deferred_candidate_count",
        ):
            if not _nonnegative_integer(raw.get(field)):
                _record(
                    findings,
                    "ASSURANCE-008",
                    path,
                    f"{pass_id}.{field} must be a nonnegative integer",
                )
        for field in (
            "coverage_gap_count",
            "unresolved_candidate_count",
            "deferred_candidate_count",
        ):
            if raw.get(field) != 0:
                _record(
                    findings,
                    "ASSURANCE-009",
                    path,
                    f"{pass_id}.{field} must be zero",
                )
        if kind in _NATIVE_PASS_KINDS:
            native_review_count += completed_count
            if str(raw.get("provider")).casefold() != "openai":
                _record(
                    findings,
                    "ASSURANCE-023",
                    path,
                    f"{pass_id} must identify the native OpenAI provider honestly",
                )
        if kind == "deep_repository":
            deep_review_count += completed_count
        evidence = _evidence_artifact(
            root,
            raw.get("artifact_path"),
            raw.get("artifact_sha256"),
            findings=findings,
            label=pass_id,
        )
        if evidence is not None:
            evidence_path, payload = evidence
            prior = evidence_owners.get(evidence_path)
            if prior is not None:
                _record(
                    findings,
                    "ASSURANCE-010",
                    path,
                    f"analytical passes {prior} and {pass_id} reuse one evidence artifact",
                )
            evidence_owners[evidence_path] = pass_id
            evidence_paths.add(evidence_path)
            _exact_fields(
                payload,
                _PASS_EVIDENCE_FIELDS,
                findings=findings,
                code="ASSURANCE-010",
                path=path,
                label=f"{pass_id} evidence",
            )
            if payload.get("schema_version") != _PASS_EVIDENCE_SCHEMA:
                _record(
                    findings,
                    "ASSURANCE-010",
                    path,
                    f"{pass_id} evidence schema is unsupported",
                )
            for field in (
                "pass_id",
                "kind",
                "status",
                "fresh_context",
                "completed_reviews",
                "candidate_count",
                "coverage_complete",
                "coverage_gap_count",
                "unresolved_candidate_count",
                "deferred_candidate_count",
            ):
                if payload.get(field) != raw.get(field):
                    _record(
                        findings,
                        "ASSURANCE-010",
                        path,
                        f"{pass_id} evidence disagrees on {field}",
                    )
            if payload.get("reviewed_commit") != reviewed_commit:
                _record(
                    findings,
                    "ASSURANCE-010",
                    path,
                    f"{pass_id} evidence does not bind reviewed_commit",
                )
            if not _nonblank(payload.get("tool")) or not isinstance(
                payload.get("source_artifact_sha256"), str
            ) or _DIGEST_PATTERN.fullmatch(
                str(payload.get("source_artifact_sha256"))
            ) is None:
                _record(
                    findings,
                    "ASSURANCE-010",
                    path,
                    f"{pass_id} evidence lacks tool or source-artifact identity",
                )

    present_native = {
        str(raw.get("kind"))
        for raw in passes.values()
        if raw.get("kind") in _NATIVE_PASS_KINDS
    }
    required_native = set(contract.get("required_native_pass_kinds", []))
    if present_native != required_native:
        _record(
            findings,
            "ASSURANCE-009",
            path,
            "native pass kinds disagree with policy; "
            f"present={sorted(present_native)}, required={sorted(required_native)}",
        )
    minimum_native = contract.get("minimum_context_isolated_passes")
    if not _positive_integer(minimum_native) or native_review_count < cast(
        int, minimum_native
    ):
        _record(
            findings,
            "ASSURANCE-009",
            path,
            f"only {native_review_count} context-isolated native reviews are evidenced",
        )
    minimum_deep = contract.get("minimum_deep_standard_passes")
    if not _positive_integer(minimum_deep) or deep_review_count < cast(
        int, minimum_deep
    ):
        _record(
            findings,
            "ASSURANCE-009",
            path,
            f"only {deep_review_count} complete deep Standard reviews are evidenced",
        )
    return passes, evidence_paths


def _safe_candidate_paths(
    root: Path,
    values: object,
    findings: list[GovernanceFinding],
    candidate_id: str,
) -> None:
    paths = _canonical_strings(values)
    if paths is None:
        _record(
            findings,
            "ASSURANCE-012",
            CANONICAL_ASSURANCE_ARTIFACT,
            f"candidate {candidate_id} requires safe, unique, sorted evidence paths",
        )
        return
    for raw_path in paths:
        try:
            resolve_repository_file(root, raw_path)
        except RepositoryPathError:
            _record(
                findings,
                "ASSURANCE-012",
                CANONICAL_ASSURANCE_ARTIFACT,
                f"candidate {candidate_id} references missing or unsafe evidence: {raw_path}",
            )


def _audit_candidate_union(
    root: Path,
    raw_reference: object,
    passes: Mapping[str, Mapping[str, Any]],
    reviewed_commit: object,
    findings: list[GovernanceFinding],
) -> set[str]:
    path = CANONICAL_ASSURANCE_ARTIFACT
    if not isinstance(raw_reference, dict):
        _record(findings, "ASSURANCE-011", path, "candidate_union must be an object")
        return set()
    _exact_fields(
        raw_reference,
        _CANDIDATE_UNION_REFERENCE_FIELDS,
        findings=findings,
        code="ASSURANCE-011",
        path=path,
        label="candidate_union",
    )
    evidence = _evidence_artifact(
        root,
        raw_reference.get("artifact_path"),
        raw_reference.get("artifact_sha256"),
        findings=findings,
        label="candidate_union",
    )
    if evidence is None:
        return set()
    evidence_path, payload = evidence
    _exact_fields(
        payload,
        _CANDIDATE_UNION_FIELDS,
        findings=findings,
        code="ASSURANCE-011",
        path=path,
        label="candidate-union artifact",
    )
    if payload.get("schema_version") != _CANDIDATE_UNION_SCHEMA:
        _record(findings, "ASSURANCE-011", path, "candidate-union schema is unsupported")
    if payload.get("reviewed_commit") != reviewed_commit:
        _record(
            findings,
            "ASSURANCE-013",
            path,
            "candidate union does not bind the assurance reviewed_commit",
        )
    if payload.get("blind_union") is not True:
        _record(findings, "ASSURANCE-012", path, "candidate union was not blind")
    if payload.get("coverage_complete") is not True or payload.get("coverage_gaps") != []:
        _record(
            findings,
            "ASSURANCE-012",
            path,
            "candidate union contains incomplete coverage or coverage gaps",
        )
    source_pass_ids = _canonical_strings(payload.get("source_pass_ids"))
    if source_pass_ids is None or set(source_pass_ids) != set(passes):
        _record(
            findings,
            "ASSURANCE-013",
            path,
            "candidate union does not account exactly for every analytical pass",
        )
    raw_candidates = payload.get("candidates")
    if not isinstance(raw_candidates, list):
        _record(findings, "ASSURANCE-011", path, "candidates must be an array")
        return {evidence_path}
    candidate_ids: set[str] = set()
    candidate_counts: Counter[str] = Counter()
    for index, raw in enumerate(raw_candidates):
        label = f"candidates[{index}]"
        if not isinstance(raw, dict):
            _record(findings, "ASSURANCE-011", path, f"{label} must be an object")
            continue
        _exact_fields(
            raw,
            _CANDIDATE_FIELDS,
            findings=findings,
            code="ASSURANCE-011",
            path=path,
            label=label,
        )
        candidate_id = raw.get("id")
        if (
            not isinstance(candidate_id, str)
            or _CANDIDATE_ID_PATTERN.fullmatch(candidate_id) is None
            or candidate_id in candidate_ids
        ):
            _record(
                findings,
                "ASSURANCE-011",
                path,
                f"{label}.id is malformed or duplicated",
            )
            candidate_id = label
        else:
            candidate_ids.add(candidate_id)
        candidate_sources = _canonical_strings(raw.get("source_pass_ids"))
        if (
            candidate_sources is None
            or not set(candidate_sources).issubset(passes)
        ):
            _record(
                findings,
                "ASSURANCE-013",
                path,
                f"candidate {candidate_id} has invalid source pass IDs",
            )
        else:
            candidate_counts.update(candidate_sources)
        if raw.get("severity") not in {"P0", "P1", "P2", "P3", "informational"}:
            _record(
                findings,
                "ASSURANCE-011",
                path,
                f"candidate {candidate_id} has invalid severity",
            )
        disposition = raw.get("disposition")
        if disposition not in {"resolved", "rejected"}:
            _record(
                findings,
                "ASSURANCE-012",
                path,
                f"candidate {candidate_id} remains unresolved or deferred",
            )
        if not _nonblank(raw.get("rationale")):
            _record(
                findings,
                "ASSURANCE-011",
                path,
                f"candidate {candidate_id} requires a nonblank rationale",
            )
        resolution_commit = raw.get("resolution_commit")
        if disposition == "resolved":
            if (
                not isinstance(resolution_commit, str)
                or _COMMIT_PATTERN.fullmatch(resolution_commit) is None
                or not _commit_exists(root, resolution_commit)
            ):
                _record(
                    findings,
                    "ASSURANCE-012",
                    path,
                    f"candidate {candidate_id} resolution commit is invalid",
                )
            elif isinstance(reviewed_commit, str):
                try:
                    if not _is_ancestor(root, resolution_commit, reviewed_commit):
                        _record(
                            findings,
                            "ASSURANCE-012",
                            path,
                            f"candidate {candidate_id} was not resolved in reviewed history",
                        )
                except GovernanceContractError as exc:
                    _record(findings, "ASSURANCE-012", path, str(exc))
        elif resolution_commit is not None:
            _record(
                findings,
                "ASSURANCE-011",
                path,
                f"rejected candidate {candidate_id} must use null resolution_commit",
            )
        _safe_candidate_paths(root, raw.get("evidence_paths"), findings, candidate_id)

    for pass_id, review_pass in passes.items():
        expected = review_pass.get("candidate_count")
        if _nonnegative_integer(expected) and candidate_counts[pass_id] != expected:
            _record(
                findings,
                "ASSURANCE-013",
                path,
                f"candidate union count for {pass_id} is {candidate_counts[pass_id]}, "
                f"not {expected}",
            )
    return {evidence_path}


def _audit_quality_gates(
    root: Path,
    raw_gates: object,
    contract: Mapping[str, Any],
    reviewed_commit: object,
    findings: list[GovernanceFinding],
) -> set[str]:
    path = CANONICAL_ASSURANCE_ARTIFACT
    if not isinstance(raw_gates, list) or not raw_gates:
        _record(findings, "ASSURANCE-014", path, "quality_gates must be nonempty")
        return set()
    gate_ids: set[str] = set()
    evidence_paths: set[str] = set()
    evidence_results: dict[str, dict[str, Mapping[str, Any]]] = {}
    for index, raw in enumerate(raw_gates):
        label = f"quality_gates[{index}]"
        if not isinstance(raw, dict):
            _record(findings, "ASSURANCE-014", path, f"{label} must be an object")
            continue
        _exact_fields(
            raw,
            _QUALITY_GATE_FIELDS,
            findings=findings,
            code="ASSURANCE-014",
            path=path,
            label=label,
        )
        gate_id = raw.get("gate_id")
        if not _nonblank(gate_id) or gate_id in gate_ids:
            _record(
                findings,
                "ASSURANCE-014",
                path,
                f"{label}.gate_id is malformed or duplicated",
            )
            continue
        assert isinstance(gate_id, str)
        gate_ids.add(gate_id)
        if raw.get("status") != "passed":
            _record(findings, "ASSURANCE-014", path, f"quality gate {gate_id} failed")
        evidence = _evidence_artifact(
            root,
            raw.get("artifact_path"),
            raw.get("artifact_sha256"),
            findings=findings,
            label=f"quality gate {gate_id}",
        )
        if evidence is not None:
            evidence_path, payload = evidence
            evidence_paths.add(evidence_path)
            if evidence_path not in evidence_results:
                _exact_fields(
                    payload,
                    _QUALITY_GATE_EVIDENCE_FIELDS,
                    findings=findings,
                    code="ASSURANCE-015",
                    path=path,
                    label=f"quality-gate evidence {evidence_path}",
                )
                if payload.get("schema_version") != _QUALITY_GATE_EVIDENCE_SCHEMA:
                    _record(
                        findings,
                        "ASSURANCE-015",
                        path,
                        f"quality-gate evidence {evidence_path} has unsupported schema",
                    )
                if payload.get("reviewed_commit") != reviewed_commit:
                    _record(
                        findings,
                        "ASSURANCE-015",
                        path,
                        f"quality-gate evidence {evidence_path} does not bind reviewed_commit",
                    )
                raw_results = payload.get("gates")
                results: dict[str, Mapping[str, Any]] = {}
                if not isinstance(raw_results, list) or not raw_results:
                    _record(
                        findings,
                        "ASSURANCE-015",
                        path,
                        f"quality-gate evidence {evidence_path} has no gate results",
                    )
                else:
                    for raw_result in raw_results:
                        if not isinstance(raw_result, dict):
                            _record(
                                findings,
                                "ASSURANCE-015",
                                path,
                                f"quality-gate evidence {evidence_path} has malformed result",
                            )
                            continue
                        _exact_fields(
                            raw_result,
                            _QUALITY_GATE_RESULT_FIELDS,
                            findings=findings,
                            code="ASSURANCE-015",
                            path=path,
                            label=f"quality-gate result in {evidence_path}",
                        )
                        result_id = raw_result.get("gate_id")
                        if not _nonblank(result_id) or result_id in results:
                            _record(
                                findings,
                                "ASSURANCE-015",
                                path,
                                f"quality-gate evidence {evidence_path} duplicates a gate",
                            )
                            continue
                        assert isinstance(result_id, str)
                        results[result_id] = raw_result
                        if raw_result.get("status") != "passed" or not isinstance(
                            raw_result.get("source_artifact_sha256"), str
                        ) or _DIGEST_PATTERN.fullmatch(
                            str(raw_result.get("source_artifact_sha256"))
                        ) is None:
                            _record(
                                findings,
                                "ASSURANCE-015",
                                path,
                                f"quality-gate evidence {result_id} is not a hash-bound pass",
                            )
                evidence_results[evidence_path] = results
            bound_result = evidence_results[evidence_path].get(gate_id)
            if bound_result is None or bound_result.get("status") != raw.get("status"):
                _record(
                    findings,
                    "ASSURANCE-015",
                    path,
                    f"quality gate {gate_id} disagrees with its evidence artifact",
                )
    required = set(contract.get("required_quality_gates", []))
    if gate_ids != required:
        _record(
            findings,
            "ASSURANCE-014",
            path,
            "quality-gate evidence disagrees with policy; "
            f"missing={sorted(required - gate_ids)}, unknown={sorted(gate_ids - required)}",
        )
    return evidence_paths


def _audit_mode(
    report: Mapping[str, Any],
    passes: Mapping[str, Mapping[str, Any]],
    contract: Mapping[str, Any],
    findings: list[GovernanceFinding],
) -> None:
    path = CANONICAL_ASSURANCE_ARTIFACT
    mode = report.get("assurance_mode")
    allowed_modes = set(contract.get("allowed_modes", []))
    if mode not in _ALLOWED_MODES or mode not in allowed_modes:
        _record(findings, "ASSURANCE-007", path, "assurance_mode is unsupported")
        return
    if report.get("independence_claim") != _MODE_CLAIM[mode]:
        _record(
            findings,
            "ASSURANCE-007",
            path,
            f"independence_claim is dishonest for {mode}",
        )
    limitations = _canonical_strings(report.get("limitations"))
    if limitations is None or _MODE_LIMITATION[mode] not in limitations:
        _record(
            findings,
            "ASSURANCE-016",
            path,
            f"limitations must disclose {_MODE_LIMITATION[mode]}",
        )
    external_passes = [
        value for value in passes.values() if value.get("kind") == "external_model"
    ]
    human_passes = [
        value for value in passes.values() if value.get("kind") == "independent_human"
    ]
    reviewer = report.get("reviewer")
    pull_request_number = report.get("pull_request_number")
    if mode == "native_maximum":
        if external_passes or human_passes or reviewer != report.get("owner"):
            _record(
                findings,
                "ASSURANCE-025",
                path,
                "native_maximum must not imply external or human independence",
            )
        if pull_request_number is not None:
            _record(
                findings,
                "ASSURANCE-025",
                path,
                "native_maximum must use null pull_request_number",
            )
    elif mode == "independent_external_model":
        if not external_passes or human_passes:
            _record(
                findings,
                "ASSURANCE-023",
                path,
                "external-model mode requires an external-model pass and no human claim",
            )
        external_reviewers: set[object] = set()
        for review_pass in external_passes:
            external_reviewers.add(review_pass.get("reviewer"))
            provider = str(review_pass.get("provider")).casefold()
            if provider in {"openai", "github", "local", "native"}:
                _record(
                    findings,
                    "ASSURANCE-023",
                    path,
                    "external-model pass must identify a different model provider",
                )
            if str(review_pass.get("model")).casefold() == "not-applicable":
                _record(
                    findings,
                    "ASSURANCE-023",
                    path,
                    "external-model pass must identify the exact model",
                )
        if reviewer not in external_reviewers or pull_request_number is not None:
            _record(
                findings,
                "ASSURANCE-023",
                path,
                "external-model mode reviewer or pull-request binding is invalid",
            )
    else:
        human_reviewers: set[object] = set()
        if not human_passes:
            _record(
                findings,
                "ASSURANCE-024",
                path,
                "independent-human mode requires a human pass",
            )
        for review_pass in human_passes:
            human_reviewers.add(review_pass.get("reviewer"))
            if (
                str(review_pass.get("provider")).casefold() != "github"
                or str(review_pass.get("model")).casefold() != "not-applicable"
            ):
                _record(
                    findings,
                    "ASSURANCE-024",
                    path,
                    "human pass must be bound to GitHub and use no model identity",
                )
        if reviewer not in human_reviewers or not _positive_integer(pull_request_number):
            _record(
                findings,
                "ASSURANCE-024",
                path,
                "human mode requires its reviewer and positive pull-request number",
            )


def _audit_review_directory(
    root: Path,
    expected_paths: set[str],
    findings: list[GovernanceFinding],
) -> None:
    review_root = root / "governance/reviews"
    actual_paths: set[str] = set()
    try:
        for candidate in review_root.rglob("*"):
            if candidate.is_symlink():
                raise OSError(f"symbolic link is prohibited: {candidate}")
            if candidate.is_file():
                actual_paths.add(candidate.relative_to(root).as_posix())
    except OSError as exc:
        _record(
            findings,
            "ASSURANCE-022",
            CANONICAL_ASSURANCE_ARTIFACT,
            f"cannot inventory assurance evidence: {exc}",
        )
        return
    if actual_paths != expected_paths:
        _record(
            findings,
            "ASSURANCE-022",
            CANONICAL_ASSURANCE_ARTIFACT,
            "assurance evidence directory contains missing or unreferenced files; "
            f"missing={sorted(expected_paths - actual_paths)}, "
            f"unreferenced={sorted(actual_paths - expected_paths)}",
        )


def audit_assurance_review(
    root: Path,
    contract: Mapping[str, Any],
    active: Mapping[str, Any],
    resolved: Mapping[str, Any],
    findings: list[GovernanceFinding],
) -> None:
    """Validate one cumulative assurance artifact and its exact evidence closure."""

    report_relative = Path(CANONICAL_ASSURANCE_ARTIFACT)
    try:
        _canonical, report_path = resolve_repository_file(
            root,
            report_relative.as_posix(),
            required_prefix="governance/reviews",
            required_suffix=".json",
        )
    except RepositoryPathError:
        _record(
            findings,
            "ASSURANCE-001",
            report_relative,
            "Native Maximum Assurance report is missing",
        )
        return
    try:
        report = _read_json_object(report_path)
    except ValueError as exc:
        _record(findings, "ASSURANCE-002", report_relative, str(exc))
        return
    _exact_fields(
        report,
        _ASSURANCE_REVIEW_FIELDS,
        findings=findings,
        code="ASSURANCE-003",
        path=report_relative.as_posix(),
        label="assurance report",
    )
    if report.get("schema_version") != _ASSURANCE_REVIEW_SCHEMA:
        _record(findings, "ASSURANCE-004", report_relative, "unsupported assurance report")
    if report.get("status") != "passed":
        _record(findings, "ASSURANCE-005", report_relative, "assurance has not passed")
    for field in ("owner", "reviewer", "review_method"):
        if not _nonblank(report.get(field)):
            _record(
                findings,
                "ASSURANCE-006",
                report_relative,
                f"{field} must be nonblank trimmed text",
            )
    if report.get("owner_acceptance") is not True:
        _record(
            findings,
            "ASSURANCE-006",
            report_relative,
            "owner_acceptance must explicitly be true",
        )
    if report.get("surviving_security_mutants") != contract.get(
        "surviving_security_mutants_allowed"
    ):
        _record(
            findings,
            "ASSURANCE-015",
            report_relative,
            "surviving security mutants exceed the policy allowance",
        )

    reviewed_commit = report.get("reviewed_commit")
    reviewed_commit_value = (
        reviewed_commit
        if isinstance(reviewed_commit, str)
        and _COMMIT_PATTERN.fullmatch(reviewed_commit) is not None
        else None
    )
    valid_reviewed_commit = reviewed_commit_value is not None
    if reviewed_commit_value is None:
        _record(
            findings,
            "ASSURANCE-017",
            report_relative,
            "reviewed_commit must be a full lowercase commit SHA",
        )
    elif not _commit_exists(root, reviewed_commit_value):
        _record(
            findings,
            "ASSURANCE-017",
            report_relative,
            "reviewed_commit does not exist as a commit object",
        )
        valid_reviewed_commit = False
    else:
        try:
            if not _is_ancestor(root, reviewed_commit_value, "HEAD"):
                _record(
                    findings,
                    "ASSURANCE-017",
                    report_relative,
                    "reviewed_commit is not an ancestor of the current head",
                )
                valid_reviewed_commit = False
        except GovernanceContractError as exc:
            _record(findings, "ASSURANCE-017", report_relative, str(exc))
            valid_reviewed_commit = False

    reviewed_tree_digest = report.get("reviewed_tree_digest")
    valid_tree_digest = isinstance(reviewed_tree_digest, str) and _DIGEST_PATTERN.fullmatch(
        reviewed_tree_digest
    ) is not None
    if not valid_tree_digest:
        _record(
            findings,
            "ASSURANCE-018",
            report_relative,
            "reviewed_tree_digest must be a lowercase SHA-256 digest",
        )
    reviewed_active_digest = report.get("reviewed_active_defects_digest")
    valid_active_digest = isinstance(
        reviewed_active_digest, str
    ) and _DIGEST_PATTERN.fullmatch(reviewed_active_digest) is not None
    if not valid_active_digest:
        _record(
            findings,
            "ASSURANCE-019",
            report_relative,
            "reviewed_active_defects_digest must be a lowercase SHA-256 digest",
        )

    passes, referenced_paths = _audit_passes(
        root,
        report.get("passes"),
        contract,
        reviewed_commit,
        findings,
    )
    _audit_mode(report, passes, contract, findings)
    referenced_paths.update(
        _audit_candidate_union(
            root,
            report.get("candidate_union"),
            passes,
            reviewed_commit,
            findings,
        )
    )
    referenced_paths.update(
        _audit_quality_gates(
            root,
            report.get("quality_gates"),
            contract,
            reviewed_commit,
            findings,
        )
    )
    _audit_review_directory(
        root,
        {CANONICAL_ASSURANCE_ARTIFACT, *referenced_paths},
        findings,
    )

    if valid_tree_digest:
        try:
            current_tree_digest = assured_tree_digest(root)
        except GovernanceContractError as exc:
            _record(
                findings,
                "ASSURANCE-020",
                report_relative,
                f"cannot verify assurance binding: {exc}",
            )
        else:
            if current_tree_digest != reviewed_tree_digest:
                _record(
                    findings,
                    "ASSURANCE-021",
                    report_relative,
                    "tracked tree outside permitted finalization artifacts does not "
                    "match the assured tree digest",
                )

    if (
        report.get("status") == "passed"
        and valid_reviewed_commit
        and valid_active_digest
    ):
        audit_defect_closure(root, active, resolved, report, findings)


def _artifact_metadata(path: Path) -> dict[str, Any]:
    payload = _read_json_object(path)
    if payload.get("schema_version") != _ASSURANCE_REVIEW_SCHEMA:
        raise ValueError("unsupported assurance-review schema")
    mode = payload.get("assurance_mode")
    if mode not in _ALLOWED_MODES:
        raise ValueError("unsupported assurance mode")
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read exact ConstructionSight assurance metadata for CI."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("mode", "pull-request-number"):
        child = subparsers.add_parser(command)
        child.add_argument("--review-artifact", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Expose fail-closed assurance metadata to canonical CI."""

    parser = _parser()
    arguments = parser.parse_args(argv)
    try:
        payload = _artifact_metadata(arguments.review_artifact)
        if arguments.command == "mode":
            print(payload["assurance_mode"])
            return 0
        if payload["assurance_mode"] != "independent_human":
            raise ValueError("pull-request-number is only valid for independent_human")
        pull_request_number = payload.get("pull_request_number")
        if not _positive_integer(pull_request_number):
            raise ValueError("human assurance requires a positive pull-request number")
        print(pull_request_number)
        return 0
    except ValueError as exc:
        parser.exit(1, f"assurance metadata failed: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
