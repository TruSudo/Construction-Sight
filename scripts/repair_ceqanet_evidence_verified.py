"""Repair CEQAnet evidence and apply verified maturity through governed controls."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from constructionsight.adapters import default_adapter_family_specs
from constructionsight.models import PublicSource
from constructionsight.source_verification_checklist_models import (
    ChecklistItemStatus,
    SourceVerificationObservation,
)
from constructionsight.source_verification_checklist_service import (
    build_source_verification_checklist_report,
)

ROOT = Path(__file__).resolve().parents[1]
DATE = "2026-07-12"
EVIDENCE_DIR = ROOT / "evidence/source_verification"
EVIDENCE_PATH = EVIDENCE_DIR / f"ceqanet_public_access_{DATE}.json"
RAW_CHECKLIST_PATH = EVIDENCE_DIR / f"ceqanet_checklist_{DATE}.json"
TERMS_REVIEW_PATH = EVIDENCE_DIR / f"ceqanet_terms_review_{DATE}.json"
OBSERVATIONS_PATH = EVIDENCE_DIR / f"ceqanet_observations_{DATE}.json"
REVIEWED_CHECKLIST_PATH = EVIDENCE_DIR / f"ceqanet_verified_checklist_{DATE}.json"
PLAN_PATH = EVIDENCE_DIR / f"ceqanet_verified_update_plan_{DATE}.json"
AUDIT_PATH = EVIDENCE_DIR / f"ceqanet_verified_apply_audit_{DATE}.json"
REPORT_PATH = ROOT / f"docs/audits/ceqanet_source_verification_{DATE}.md"
VERIFIED_REPORT_PATH = ROOT / f"docs/audits/ceqanet_verified_maturity_{DATE}.md"
REGISTRY_PATH = ROOT / "data/source_registry.seed.json"
SOURCE_NAME = "CEQAnet State Clearinghouse"
SOURCE_KEY = "source:ceqanet-state-clearinghouse"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one reconciliation anchor in {path}: {old!r}; found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _load_sources() -> list[PublicSource]:
    payload = _load_json(REGISTRY_PATH)
    return [PublicSource.model_validate(item) for item in payload]


def _observations() -> list[SourceVerificationObservation]:
    payload = _load_json(OBSERVATIONS_PATH)
    return [SourceVerificationObservation.model_validate(item) for item in payload]


def prepare_reviewed_evidence() -> None:
    for path in (EVIDENCE_PATH, RAW_CHECKLIST_PATH, REPORT_PATH):
        if not path.is_file():
            raise RuntimeError(f"collector did not produce required artifact: {path}")

    evidence = _load_json(EVIDENCE_PATH)
    if evidence.get("schema_version") != "ceqanet_source_verification_evidence.v1":
        raise RuntimeError("unexpected CEQAnet evidence schema")
    if evidence.get("source_name") != SOURCE_NAME:
        raise RuntimeError("CEQAnet evidence source identity mismatch")
    if evidence.get("registry_status") != "unverified":
        raise RuntimeError("raw evidence must preserve the pre-apply unverified state")
    if evidence["bounded_search"].get("document_downloads") is not False:
        raise RuntimeError("bounded evidence unexpectedly reports document downloads")
    if evidence["bounded_search"].get("persistence_mutated") is not False:
        raise RuntimeError("bounded evidence unexpectedly reports persistence mutation")
    if evidence["public_detail"].get("document_downloads") is not False:
        raise RuntimeError("detail evidence unexpectedly reports document downloads")
    if evidence["public_detail"].get("persistence_mutated") is not False:
        raise RuntimeError("detail evidence unexpectedly reports persistence mutation")
    if evidence.get("access_barrier_observation") != {
        "login_required": False,
        "captcha_observed": False,
        "paywall_observed": False,
    }:
        raise RuntimeError("bounded evidence does not affirm the reviewed no-barrier state")

    observed_markers = set(evidence["public_detail"].get("observed_field_markers", []))
    required_markers = {"sch_number", "project_info", "title", "description"}
    if not required_markers.issubset(observed_markers) or len(observed_markers) < 5:
        raise RuntimeError("current CEQAnet detail marker evidence is incomplete")

    terms_records = evidence.get("terms_privacy_accessibility_links", [])
    required_paths = {
        "/home/conditionsofuse": "conditions_of_use",
        "/home/privacy": "privacy_policy",
        "/home/accessibility": "accessibility",
    }
    reviewed: dict[str, dict[str, Any]] = {}
    for record in terms_records:
        final_url = str(record.get("final_url", ""))
        path = urlparse(final_url).path.lower().rstrip("/")
        label = required_paths.get(path)
        if label is None:
            continue
        if record.get("status_code") != 200:
            raise RuntimeError(f"official {label} page did not return HTTP 200")
        if record.get("official_https_final_url") is not True:
            raise RuntimeError(f"official {label} page left the approved HTTPS host boundary")
        reviewed[label] = {
            "url": final_url,
            "status_code": record["status_code"],
            "body_length_bytes": record["body_length_bytes"],
            "body_sha256": record["body_sha256"],
            "title": record.get("title"),
        }
    if set(reviewed) != set(required_paths.values()):
        raise RuntimeError("official conditions, privacy, and accessibility evidence is incomplete")

    terms_review = {
        "schema_version": "ceqanet_terms_review.v1",
        "reviewed_at": evidence["observed_at"],
        "source_key": SOURCE_KEY,
        "source_name": SOURCE_NAME,
        "reviewed_pages": reviewed,
        "conclusion": "no_explicit_restriction_observed_for_bounded_public_read_only_access",
        "findings": [
            "the published policy contemplates public browsing and downloading of information",
            "state-created information is generally described as public domain and distributable as permitted by law",
            "the system may be monitored for proper operation and security",
            "modification, security circumvention, and use outside intended purposes are prohibited",
            "no explicit prohibition of bounded robots-aware GET-only public-record access was found",
        ],
        "operating_constraints": [
            "GET-only public access",
            "no authentication or access-control bypass",
            "no captcha, paywall, or robots bypass",
            "no remote mutation",
            "no document download unless separately authorized",
            "bounded requests with explicit per-attempt authorization",
            "re-review if the published policies or source behavior changes",
        ],
        "limitations": [
            "this is an operational source-governance review, not a legal opinion",
            "the policy is subject to change without notice",
            "third-party documents may carry separate rights or accessibility limitations",
        ],
    }
    _write_json(TERMS_REVIEW_PATH, terms_review)

    observation = {
        "source_key": SOURCE_KEY,
        "source_name": SOURCE_NAME,
        "public_entry_observed": True,
        "query_behavior_observed": True,
        "result_list_observed": True,
        "detail_page_observed": True,
        "access_barrier_observed": False,
        "terms_review_observed": True,
        "notes": (
            "Bounded public GET evidence and official policy review support verified manual "
            "read-only execution under the retained operating constraints."
        ),
        "evidence_refs": [
            EVIDENCE_PATH.relative_to(ROOT).as_posix(),
            TERMS_REVIEW_PATH.relative_to(ROOT).as_posix(),
        ],
    }
    _write_json(OBSERVATIONS_PATH, [observation])


def validate_plan() -> None:
    plan = _load_json(PLAN_PATH)
    if plan.get("source_count") != 4:
        raise RuntimeError("verified update plan must preserve the complete four-source registry")
    if plan.get("update_count") != 1:
        raise RuntimeError("verified update plan must propose exactly one status change")
    rows = [row for row in plan.get("rows", []) if row.get("source_name") == SOURCE_NAME]
    if len(rows) != 1:
        raise RuntimeError("verified update plan must contain exactly one CEQAnet row")
    row = rows[0]
    expected = {
        "current_verification_status": "unverified",
        "proposed_verification_status": "verified",
        "planned_action": "verified_candidate_review",
        "update_required": True,
    }
    for field, value in expected.items():
        if row.get(field) != value:
            raise RuntimeError(f"verified update plan {field} mismatch")
    expected_refs = {
        EVIDENCE_PATH.relative_to(ROOT).as_posix(),
        TERMS_REVIEW_PATH.relative_to(ROOT).as_posix(),
    }
    if set(row.get("evidence_refs", [])) != expected_refs:
        raise RuntimeError("verified update plan must bind public and terms evidence")


def reconcile_after_apply() -> None:
    sources = _load_sources()
    matches = [source for source in sources if source.source_name == SOURCE_NAME]
    if len(matches) != 1:
        raise RuntimeError("updated registry must contain exactly one CEQAnet source")
    ceqanet = matches[0]
    if ceqanet.verification_status.value != "verified":
        raise RuntimeError("controlled apply did not classify CEQAnet as verified")
    if ceqanet.last_checked_date is not None:
        raise RuntimeError("status-only apply must not modify last_checked_date")
    if any(
        source.verification_status.value != "unverified"
        for source in sources
        if source.source_name != SOURCE_NAME
    ):
        raise RuntimeError("controlled apply changed an unrelated source status")

    audit = _load_json(AUDIT_PATH)
    if audit.get("applied_count") != 1 or audit.get("registry_changed") is not True:
        raise RuntimeError("controlled apply audit does not record one applied change")
    rows = [row for row in audit.get("rows", []) if row.get("source_name") == SOURCE_NAME]
    if len(rows) != 1:
        raise RuntimeError("controlled apply audit must contain exactly one CEQAnet row")
    row = rows[0]
    if row.get("previous_verification_status") != "unverified":
        raise RuntimeError("controlled apply audit previous status mismatch")
    if row.get("resulting_verification_status") != "verified":
        raise RuntimeError("controlled apply audit resulting status mismatch")
    if row.get("applied") is not True:
        raise RuntimeError("controlled apply audit did not mark the CEQAnet row applied")

    reviewed_checklist = build_source_verification_checklist_report(
        sources,
        default_adapter_family_specs(),
        check_http=False,
        observations=_observations(),
    )
    reviewed_rows = [item for item in reviewed_checklist.rows if item.source_name == SOURCE_NAME]
    if len(reviewed_rows) != 1:
        raise RuntimeError("reviewed checklist must contain exactly one CEQAnet row")
    reviewed_row = reviewed_rows[0]
    required = (
        reviewed_row.public_entry_page,
        reviewed_row.query_behavior,
        reviewed_row.result_list,
        reviewed_row.detail_page,
        reviewed_row.terms_review,
    )
    if any(status is not ChecklistItemStatus.OBSERVED for status in required):
        raise RuntimeError("reviewed checklist does not preserve complete observed evidence")
    if reviewed_row.access_barrier is not ChecklistItemStatus.NOT_OBSERVED:
        raise RuntimeError("reviewed checklist does not preserve no-barrier evidence")
    _write_json(REVIEWED_CHECKLIST_PATH, reviewed_checklist.to_dict())

    _replace_once(
        REPORT_PATH,
        "Manual review of the inventoried official terms/privacy/accessibility material remains required.",
        "The inventoried official conditions, privacy, and accessibility material was reviewed in the separate terms-review artifact. No explicit restriction on bounded public GET-only access was observed; all operating constraints remain mandatory.",
    )
    _replace_once(
        REPORT_PATH,
        "The canonical source must remain unverified until that review is explicit and a controlled promotion plan is approved.",
        "The canonical source was promoted to verified through a separate evidence-bound controlled apply. This authorizes only guarded manual execution under the documented constraints; it does not authorize scheduling, persistence mutation, or document downloads.",
    )

    _reconcile_readme()
    _reconcile_status_matrix()
    _reconcile_audit_inventory()
    _reconcile_recurring_governance()
    _write_verified_report(audit)


def _reconcile_readme() -> None:
    path = ROOT / "README.md"
    _replace_once(
        path,
        "Adapter contracts are not the same thing as live source integrations. Most adapter families are still placeholder contracts. Source records in `data/source_registry.seed.json` are seed targets and must remain treated as unverified until checked. Run `constructionsight-source-status report data/source_registry.seed.json` before making any source-readiness claim. Run `constructionsight-source-readiness check data/source_registry.seed.json` and `constructionsight-audit-package build data/source_registry.seed.json --check-http` to produce non-mutating evidence. Use the source checklist, promotion plan, and registry plan commands before any status change. Controlled apply requires a reviewed plan digest, evidence references, explicit `--apply`, status-only mutation, stale-state validation, audit output, and atomic file replacement.",
        "Adapter contracts are not the same thing as live source integrations. Most adapter families are still placeholder contracts. Source records in `data/source_registry.seed.json` preserve per-source maturity: CEQAnet is currently `verified` for bounded guarded manual public-read execution, while the other canonical sources remain `unverified`. Verified source status does not imply scheduling, persistence ingestion, document-download authority, or complete coverage. Run `constructionsight-source-status report data/source_registry.seed.json` before making any source-readiness claim. Use the source checklist, promotion plan, registry plan, and controlled apply before any status change. Controlled apply requires a reviewed plan digest, evidence references, explicit `--apply`, status-only mutation, stale-state validation, audit output, and atomic file replacement.",
    )
    _replace_once(
        path,
        "Current observed HTTP audit-package outcome for the seed registry is: CEQAnet `cross_host_redirect`, CSLB `no_redirect`, San Bernardino EZOP `same_host_redirect`, Riverside PLUS `downgraded_to_http`, and all four sources `keep_unverified_reachable`. This implementation does not promote any current seed source.",
        "Current canonical maturity is CEQAnet `verified` and the other three source records `unverified`. Bounded evidence and official policy review support guarded manual GET-only CEQAnet execution. Scheduling, autonomous retries, persistence mutation, document downloads, and production coverage remain separately gated.",
    )


def _reconcile_status_matrix() -> None:
    path = ROOT / "docs/architecture/current_implementation_status.md"
    _replace_once(
        path,
        "| Source registry | Yes | Yes | Yes | Yes | Yes | No | Seed records remain unverified until checked; controlled apply changes only an approved evidence-backed verification status and does not create live coverage. |",
        "| Source registry | Yes | Yes | Yes | Yes | Yes | No | CEQAnet is evidence-backed `verified` for guarded manual public reads; the other canonical sources remain `unverified`. Controlled apply changed status only and did not create production coverage. |",
    )
    _replace_once(
        path,
        "| CEQAnet recurring-run governance | Yes | Yes | Yes | Artifact-only | Yes | Guarded only | Exact-schema definitions, manifests, executions, and verifications bind source evidence, exact windows, attempts, retained response envelopes, and current-evidence authority. Canonical CEQAnet data remains unverified, so current repository artifacts remain blocked. |",
        "| CEQAnet recurring-run governance | Yes | Yes | Yes | Artifact-only | Yes | Guarded only | Exact-schema definitions, manifests, executions, and verifications bind current source evidence, exact windows, attempts, retained response envelopes, and authority. CEQAnet now satisfies the verified/manual-execution gate; every live attempt still requires explicit authorization and permits no persistence. |",
    )
    _replace_once(
        path,
        "| CS-VIAM-016 | P1 | CEQAnet execution evidence | Initial recurring-run executions had semantic verification but no digest over the complete retained response envelope. | Exact execution schemas and a canonical execution digest now bind bodies, URLs, counts, queries, flags, identities, and the no-persistence assertion before semantic verification. |",
        "| CS-VIAM-016 | P1 | CEQAnet execution evidence | Initial recurring-run executions had semantic verification but no digest over the complete retained response envelope. | Exact execution schemas and a canonical execution digest now bind bodies, URLs, counts, queries, flags, identities, and the no-persistence assertion before semantic verification. |\n| CS-VIAM-017 | P1 | CEQAnet evidence phase | PR #93 merged temporary write-enabled collection tooling instead of the claimed evidence packet and audit report. | The repair phase regenerated and committed current-structure evidence, reviewed official policies, removed all temporary tooling, applied `unverified → verified` through controlled apply, reconciled documentation, and added regression coverage. |",
    )
    _replace_once(
        path,
        "| CS-PLAN-002 | Verified recurring live adapters | CEQAnet now has exact-schema, evidence-bound definitions, exact-window manifests, stale-evidence rejection, digest-bound bounded attempts, and full execution verification; canonical source data remains unverified and no scheduler exists. | Complete source-specific evidence review and maturity promotion, then define persisted attempt, scheduling, retry, archive, observability, and downstream handoff governance. |",
        "| CS-PLAN-002 | Production recurring live adapters | CEQAnet is verified for guarded manual public-read attempts and has exact-schema definitions, manifests, stale-evidence rejection, digest-bound execution, and full verification. No scheduler or attempt ledger exists. | Prove a reviewed manual run, then define persisted attempt identity, scheduling, retry, archive, observability, rate, and downstream handoff governance. |",
    )


def _reconcile_audit_inventory() -> None:
    path = ROOT / "docs/audits/full_repo_audit_inventory.md"
    _replace_once(
        path,
        "ConstructionSight is not yet a production recurring live-source platform. Most adapter families are contracts or planned integrations. CEQAnet has guarded execution, archive tooling, and recurring-run governance, but the canonical source remains unverified and no production scheduler exists. Four canonical source-registry seed records remain unverified. No external outreach-sending behavior or GUI/operator application is implemented.",
        "ConstructionSight is not yet a production recurring live-source platform. Most adapter families are contracts or planned integrations. CEQAnet has bounded evidence-backed `verified` maturity, guarded execution, archive tooling, and recurring-run governance, but no production scheduler or persisted attempt ledger exists. The other three canonical source records remain unverified. No external outreach-sending behavior or GUI/operator application is implemented.",
    )
    _replace_once(
        path,
        "| Source registry | Yes | Yes | Yes | File-backed | Yes | No | Seed status is distinct from verified usable coverage. |",
        "| Source registry | Yes | Yes | Yes | File-backed | Yes | No | CEQAnet is `verified` for guarded manual public reads; three canonical sources remain `unverified`. Verification is not a production-coverage claim. |",
    )
    _replace_once(
        path,
        "| CEQAnet recurring-run governance | Yes | Yes | Yes | Artifact-only | Yes | Guarded only | Exact schemas and canonical digests bind source identity, evidence, query, window, attempts, and complete retained response envelopes. Execution requires current registry/checklist agreement and explicit authorization. Canonical source data remains blocked because it is unverified. |",
        "| CEQAnet recurring-run governance | Yes | Yes | Yes | Artifact-only | Yes | Guarded only | Exact schemas and canonical digests bind source identity, evidence, query, window, attempts, and complete retained response envelopes. Verified CEQAnet may execute only through explicit bounded manual authorization; scheduling and persistence remain unavailable. |",
    )
    _replace_once(
        path,
        "| CS-AUDIT-022 | P1 | CEQAnet execution evidence | Recurring-run executions initially had field-level semantic checks but no digest over the complete retained response envelope. | Exact execution schemas and a canonical execution digest now bind bodies, URLs, queries, counts, flags, identities, and the no-persistence assertion before semantic verification. |",
        "| CS-AUDIT-022 | P1 | CEQAnet execution evidence | Recurring-run executions initially had field-level semantic checks but no digest over the complete retained response envelope. | Exact execution schemas and a canonical execution digest now bind bodies, URLs, queries, counts, flags, identities, and the no-persistence assertion before semantic verification. |\n| CS-AUDIT-023 | P1 | CEQAnet evidence phase | PR #93 merged temporary write-enabled collection files while the claimed evidence JSON and audit report were absent from `main`. | The repair phase regenerated current-structure evidence, added an official-policy review, removed temporary tooling, used deterministic controlled apply for `unverified → verified`, reconciled all maturity claims, and added permanent regression coverage. |",
    )
    _replace_once(
        path,
        "| CS-PLAN-002 | Verified recurring live source adapters | CEQAnet has exact-schema evidence-bound definitions, exact-window manifests, stale-evidence rejection, digest-bound attempts, and complete execution verification. Canonical source data remains unverified; attempts are not scheduled or persisted as a ledger. | Complete source-specific evidence review and maturity promotion, then define persisted attempt identity, scheduling, retry, archive, observability, and downstream handoff governance. |",
        "| CS-PLAN-002 | Production recurring live source adapters | CEQAnet is verified for guarded manual public-read attempts and has exact-schema evidence-bound definitions, manifests, stale-evidence rejection, digest-bound attempts, and complete verification. Attempts are not scheduled or persisted as a ledger. | Prove a reviewed manual run, then define persisted attempt identity, scheduling, retry, archive, observability, rate, and downstream handoff governance. |",
    )
    _replace_once(path, "| Seed source records | Four unverified records. |", "| Seed source records | One verified CEQAnet record and three unverified records. |")
    _replace_once(path, "| Verified usable source | Zero in the canonical registry. |", "| Verified usable source | One guarded manual-read source: CEQAnet. |")
    _replace_once(
        path,
        "| Guarded live read-only execution | Limited CEQAnet executors and recurring-run governance exist. Current canonical CEQAnet definitions remain blocked. |",
        "| Guarded live read-only execution | Verified CEQAnet may produce current evidence-bound definitions and explicit bounded manual attempts. No scheduler or persistence handoff is authorized. |",
    )


def _reconcile_recurring_governance() -> None:
    path = ROOT / "docs/architecture/ceqanet_recurring_run_governance.md"
    _replace_once(
        path,
        "The canonical CEQAnet registry record remains unverified. Therefore, a definition produced from current canonical repository data remains blocked and cannot execute through this boundary.",
        "The canonical CEQAnet registry record is verified through bounded public evidence, a reviewed official-policy artifact, and controlled apply. A definition may therefore become ready for explicit manual execution when it binds the current reviewed checklist. This does not authorize scheduling, persistence mutation, or document downloads.",
    )


def _write_verified_report(audit: dict[str, Any]) -> None:
    report = f"""# CEQAnet Verified Manual-Read Maturity

Observation and policy-review date: `{DATE}`

## Classification

CEQAnet is classified as `verified` for guarded, bounded, explicit manual public-read execution.

The evidence established official public entry, query, result-list, and current project-detail behavior. The reviewed paths showed no login, captcha, paywall, or robots prohibition. The official conditions, privacy, and accessibility pages were reviewed and hashed. No explicit restriction on bounded GET-only public-record access was observed.

## Controlled apply

- Previous status: `unverified`
- Resulting status: `verified`
- Applied rows: `{audit['applied_count']}`
- Plan digest: `{audit['plan_digest']}`
- Original registry digest: `{audit['original_registry_digest']}`
- Updated registry digest: `{audit['updated_registry_digest']}`

The controlled apply changed only `verification_status`. It did not modify `last_checked_date`, provenance, URLs, adapter maturity, or unrelated sources.

## Functional effect

Current evidence-bound CEQAnet recurring-run definitions may become ready for explicit manual execution. Every attempt still requires `--execute-live`, current registry/checklist agreement, bounded GET-only requests, retained response evidence, and post-run verification.

## Not authorized

- autonomous scheduling;
- persisted attempt ledgers;
- automatic retry or backoff;
- document downloads;
- persistence ingestion;
- outreach; or
- production coverage claims.

## Evidence and audit artifacts

- `{EVIDENCE_PATH.relative_to(ROOT).as_posix()}`
- `{RAW_CHECKLIST_PATH.relative_to(ROOT).as_posix()}`
- `{TERMS_REVIEW_PATH.relative_to(ROOT).as_posix()}`
- `{OBSERVATIONS_PATH.relative_to(ROOT).as_posix()}`
- `{REVIEWED_CHECKLIST_PATH.relative_to(ROOT).as_posix()}`
- `{PLAN_PATH.relative_to(ROOT).as_posix()}`
- `{AUDIT_PATH.relative_to(ROOT).as_posix()}`

## Next gate

Execute one narrow date-window run manually, verify the complete execution artifact, review source behavior and data quality, and only then design persisted attempt and scheduling governance.
"""
    VERIFIED_REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: repair_ceqanet_evidence_verified.py prepare|validate-plan|reconcile")
    command = sys.argv[1]
    if command == "prepare":
        prepare_reviewed_evidence()
        return
    if command == "validate-plan":
        validate_plan()
        return
    if command == "reconcile":
        reconcile_after_apply()
        return
    raise SystemExit(f"unknown command: {command}")


if __name__ == "__main__":
    main()
