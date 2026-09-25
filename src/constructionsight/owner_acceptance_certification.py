"""Authenticate Native Maximum Assurance owner acceptance against GitHub evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from constructionsight.governance_certification_core import (
    GovernanceFinding,
    _finding,
)
from constructionsight.repository_path_certification import (
    RepositoryPathError,
    resolve_repository_file,
)

_SCHEMA_VERSION: Final = "constructionsight.owner-acceptance-certification/v1"
_ASSURANCE_SCHEMA_VERSION: Final = "constructionsight.assurance-review/v1"
_CANONICAL_ASSURANCE_ARTIFACT: Final = "governance/reviews/assurance_review.json"
_EVIDENCE_DIGEST_DOMAIN: Final = b"constructionsight.owner-acceptance-evidence/v1\0"
_OWNER_PATTERN: Final = re.compile(
    r"github:(?P<login>[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?)"
    r"@pr-(?P<pr>[1-9][0-9]*)#(?P<review>[1-9][0-9]*)"
)
_COMMIT_PATTERN: Final = re.compile(r"[0-9a-f]{40}")
_DIGEST_PATTERN: Final = re.compile(r"[0-9a-f]{64}")
_MATERIAL_FIELDS: Final = (
    "schema_version",
    "status",
    "assurance_mode",
    "independence_claim",
    "reviewed_commit",
    "reviewed_active_defects_digest",
    "reviewed_tree_digest",
    "pull_request_number",
    "surviving_security_mutants",
    "passes",
    "candidate_union",
    "quality_gates",
    "limitations",
)
_REVIEW_METHOD_PREFIX: Final = (
    "frozen exact-tree cumulative adversarial assurance; evidence_sha256="
)
_ACCEPTANCE_HEADER: Final = (
    "ConstructionSight Native Maximum Assurance owner acceptance"
)


def _nonblank(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def _positive_integer(value: object) -> bool:
    return not isinstance(value, bool) and isinstance(value, int) and value > 0


def parse_owner_binding(value: object) -> tuple[str, int, int]:
    """Return bound GitHub login, PR number, and review ID."""

    if not isinstance(value, str):
        raise ValueError(
            "owner must bind a GitHub login, PR number, and review ID"
        )
    match = _OWNER_PATTERN.fullmatch(value)
    if match is None:
        raise ValueError(
            "owner must match "
            "github:<login>@pr-<positive-pr>#<positive-review-id>"
        )
    return (
        match.group("login"),
        int(match.group("pr")),
        int(match.group("review")),
    )


def assurance_evidence_digest(report: Mapping[str, Any]) -> str:
    """Digest every material assurance claim that owner acceptance must cover."""

    payload = {field: report.get(field) for field in _MATERIAL_FIELDS}
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    digest = hashlib.sha256()
    digest.update(_EVIDENCE_DIGEST_DOMAIN)
    digest.update(encoded)
    return digest.hexdigest()


def expected_review_method(report: Mapping[str, Any]) -> str:
    """Return the exact report method claim authenticated by the owner."""

    return _REVIEW_METHOD_PREFIX + assurance_evidence_digest(report)


def expected_acceptance_body(report: Mapping[str, Any]) -> str:
    """Return the exact GitHub review body required for owner acceptance."""

    reviewed_commit = report.get("reviewed_commit")
    reviewed_tree_digest = report.get("reviewed_tree_digest")
    return "\n".join(
        (
            _ACCEPTANCE_HEADER,
            f"reviewed_commit={reviewed_commit}",
            f"reviewed_tree_digest={reviewed_tree_digest}",
            f"assurance_evidence_sha256={assurance_evidence_digest(report)}",
            "decision=accepted",
        )
    )


def local_owner_acceptance_findings(
    report: Mapping[str, Any],
) -> tuple[str, ...]:
    """Return local findings for the owner-bound evidence claim."""

    findings: list[str] = []
    if report.get("schema_version") != _ASSURANCE_SCHEMA_VERSION:
        findings.append("assurance report schema is unsupported")
    if report.get("owner_acceptance") is not True:
        findings.append("owner_acceptance must explicitly be true")
    try:
        bound_login, _pr_number, _review_id = parse_owner_binding(
            report.get("owner")
        )
    except ValueError as exc:
        findings.append(str(exc))
        bound_login = None
    if (
        bound_login is not None
        and report.get("assurance_mode") == "native_maximum"
        and report.get("reviewer") != report.get("owner")
    ):
        findings.append(
            "native owner reviewer must equal the authenticated owner binding"
        )
    if report.get("review_method") != expected_review_method(report):
        findings.append(
            "review_method does not bind the exact material assurance evidence digest"
        )
    return tuple(findings)


def audit_owner_acceptance_binding(
    root: Path,
    findings: list[GovernanceFinding],
) -> None:
    """Require a locally self-consistent authenticated-owner acceptance claim."""

    try:
        _relative, path = resolve_repository_file(
            root,
            _CANONICAL_ASSURANCE_ARTIFACT,
            required_prefix="governance/reviews",
            required_suffix=".json",
        )
    except RepositoryPathError:
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return
    if not isinstance(payload, dict):
        return
    for message in local_owner_acceptance_findings(payload):
        findings.append(
            _finding(
                "ASSURANCE-029",
                _CANONICAL_ASSURANCE_ARTIFACT,
                message,
            )
        )


def verify_github_owner_acceptance(
    assurance_report: Mapping[str, Any],
    github_review: Mapping[str, Any],
    github_pull_request: Mapping[str, Any],
    *,
    repository_owner: str,
) -> tuple[str, ...]:
    """Return findings for externally authenticated owner acceptance."""

    findings = list(local_owner_acceptance_findings(assurance_report))
    try:
        bound_login, bound_pr_number, bound_review_id = parse_owner_binding(
            assurance_report.get("owner")
        )
    except ValueError:
        return tuple(findings)

    if not _nonblank(repository_owner):
        findings.append("repository owner identity must be nonblank")
    elif bound_login.casefold() != repository_owner.casefold():
        findings.append("bound assurance owner is not the repository owner")

    source_pr_number = github_pull_request.get("number")
    if not _positive_integer(source_pr_number):
        findings.append("GitHub pull-request number must be a positive integer")
    elif source_pr_number != bound_pr_number:
        findings.append(
            "GitHub pull request does not match owner acceptance binding"
        )

    review_id = github_review.get("id")
    if not _positive_integer(review_id):
        findings.append("GitHub owner review ID must be a positive integer")
    elif review_id != bound_review_id:
        findings.append("GitHub owner review ID does not match assurance binding")

    if github_review.get("state") != "COMMENTED":
        findings.append(
            "GitHub owner acceptance transport state must be COMMENTED"
        )
    if github_review.get("author_association") != "OWNER":
        findings.append(
            "GitHub owner acceptance must have OWNER author association"
        )

    user = github_review.get("user")
    if not isinstance(user, Mapping):
        findings.append("GitHub owner review user must be an object")
    else:
        login = user.get("login")
        if (
            not isinstance(login, str)
            or login.casefold() != bound_login.casefold()
        ):
            findings.append(
                "GitHub owner review login does not match assurance binding"
            )
        if user.get("type") != "User":
            findings.append(
                "GitHub owner acceptance must come from a User identity"
            )

    reviewed_commit = assurance_report.get("reviewed_commit")
    if (
        not isinstance(reviewed_commit, str)
        or _COMMIT_PATTERN.fullmatch(reviewed_commit) is None
    ):
        findings.append("reviewed_commit must be a full lowercase commit SHA")
    elif github_review.get("commit_id") != reviewed_commit:
        findings.append(
            "GitHub owner review commit does not match reviewed_commit"
        )

    reviewed_tree_digest = assurance_report.get("reviewed_tree_digest")
    if (
        not isinstance(reviewed_tree_digest, str)
        or _DIGEST_PATTERN.fullmatch(reviewed_tree_digest) is None
    ):
        findings.append(
            "reviewed_tree_digest must be a lowercase SHA-256 digest"
        )

    if github_review.get("body") != expected_acceptance_body(assurance_report):
        findings.append(
            "GitHub owner acceptance body does not match exact assurance evidence"
        )
    if not _nonblank(github_review.get("submitted_at")):
        findings.append(
            "GitHub owner acceptance must have a submission timestamp"
        )
    return tuple(findings)


def build_report(
    assurance_report: Mapping[str, Any],
    github_review: Mapping[str, Any],
    github_pull_request: Mapping[str, Any],
    *,
    repository_owner: str,
) -> dict[str, Any]:
    """Build one deterministic owner-acceptance verification report."""

    findings = verify_github_owner_acceptance(
        assurance_report,
        github_review,
        github_pull_request,
        repository_owner=repository_owner,
    )
    return {
        "schema_version": _SCHEMA_VERSION,
        "passed": not findings,
        "owner": assurance_report.get("owner"),
        "reviewed_commit": assurance_report.get("reviewed_commit"),
        "evidence_sha256": assurance_evidence_digest(assurance_report),
        "github_review_id": github_review.get("id"),
        "findings": list(findings),
    }


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"cannot read JSON object from {path}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload at {path} must be an object")
    return payload


def _write_report(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Verify ConstructionSight owner acceptance against GitHub evidence."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("pr-number", "review-id"):
        child = subparsers.add_parser(command)
        child.add_argument("--review-artifact", type=Path, required=True)

    verify = subparsers.add_parser("verify")
    verify.add_argument("--review-artifact", type=Path, required=True)
    verify.add_argument("--github-review", type=Path, required=True)
    verify.add_argument("--github-pull-request", type=Path, required=True)
    verify.add_argument("--repository-owner", required=True)
    verify.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Verify owner acceptance metadata or externally fetched GitHub evidence."""

    parser = _parser()
    args = parser.parse_args(argv)
    try:
        assurance = _read_json_object(args.review_artifact)
        if args.command in {"pr-number", "review-id"}:
            _login, pr_number, review_id = parse_owner_binding(
                assurance.get("owner")
            )
            print(pr_number if args.command == "pr-number" else review_id)
            return 0
        github_review = _read_json_object(args.github_review)
        github_pull_request = _read_json_object(args.github_pull_request)
        report = build_report(
            assurance,
            github_review,
            github_pull_request,
            repository_owner=args.repository_owner,
        )
        _write_report(args.output, report)
    except ValueError as exc:
        parser.exit(
            1,
            f"owner acceptance certification failed: {exc}\n",
        )

    if report["passed"]:
        print("Authenticated GitHub owner acceptance certification passed.")
        return 0
    for finding in report["findings"]:
        print(f"- {finding}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
