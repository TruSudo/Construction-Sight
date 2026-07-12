"""Repair the CEQAnet evidence phase and reconcile partial source maturity."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATE = "2026-07-12"
EVIDENCE_DIR = ROOT / "evidence/source_verification"
EVIDENCE_PATH = EVIDENCE_DIR / f"ceqanet_public_access_{DATE}.json"
CHECKLIST_PATH = EVIDENCE_DIR / f"ceqanet_checklist_{DATE}.json"
OBSERVATIONS_PATH = EVIDENCE_DIR / f"ceqanet_observations_{DATE}.json"
PLAN_PATH = EVIDENCE_DIR / f"ceqanet_partial_update_plan_{DATE}.json"
AUDIT_PATH = EVIDENCE_DIR / f"ceqanet_partial_apply_audit_{DATE}.json"
REPORT_PATH = ROOT / f"docs/audits/ceqanet_source_verification_{DATE}.md"
PARTIAL_REPORT_PATH = ROOT / f"docs/audits/ceqanet_partial_maturity_{DATE}.md"
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


def prepare_observations() -> None:
    for path in (EVIDENCE_PATH, CHECKLIST_PATH, REPORT_PATH):
        if not path.is_file():
            raise RuntimeError(f"collector did not produce required artifact: {path}")

    evidence = _load_json(EVIDENCE_PATH)
    if evidence.get("schema_version") != "ceqanet_source_verification_evidence.v1":
        raise RuntimeError("unexpected CEQAnet evidence schema")
    if evidence.get("source_name") != SOURCE_NAME:
        raise RuntimeError("CEQAnet evidence source identity mismatch")
    if evidence.get("registry_status") != "unverified":
        raise RuntimeError("repair evidence must preserve the pre-apply unverified source state")
    if evidence["bounded_search"].get("document_downloads") is not False:
        raise RuntimeError("bounded evidence unexpectedly reports document downloads")
    if evidence["bounded_search"].get("persistence_mutated") is not False:
        raise RuntimeError("bounded evidence unexpectedly reports persistence mutation")
    if evidence["public_detail"].get("document_downloads") is not False:
        raise RuntimeError("detail evidence unexpectedly reports document downloads")
    if evidence["public_detail"].get("persistence_mutated") is not False:
        raise RuntimeError("detail evidence unexpectedly reports persistence mutation")
    barrier = evidence.get("access_barrier_observation")
    if barrier != {
        "login_required": False,
        "captcha_observed": False,
        "paywall_observed": False,
    }:
        raise RuntimeError("bounded evidence does not affirm the reviewed no-barrier state")

    checklist = _load_json(CHECKLIST_PATH)
    rows = checklist.get("rows", [])
    if len(rows) != 1 or rows[0].get("source_name") != SOURCE_NAME:
        raise RuntimeError("collector checklist must contain exactly one CEQAnet row")
    row = rows[0]
    required_statuses = {
        "public_entry_page": "observed",
        "query_behavior": "observed",
        "result_list": "observed",
        "detail_page": "observed",
        "access_barrier": "not_observed",
        "terms_review": "not_checked",
    }
    for field, expected in required_statuses.items():
        if row.get(field) != expected:
            raise RuntimeError(f"collector checklist {field} must be {expected}")

    observation = {
        "source_key": SOURCE_KEY,
        "source_name": SOURCE_NAME,
        "public_entry_observed": True,
        "query_behavior_observed": True,
        "result_list_observed": True,
        "detail_page_observed": True,
        "access_barrier_observed": False,
        "terms_review_observed": None,
        "notes": (
            "Bounded public GET evidence observed official entry, query, result-list, and detail "
            "behavior without login, captcha, paywall, document download, or persistence mutation. "
            "Terms review remains incomplete."
        ),
        "evidence_refs": [EVIDENCE_PATH.relative_to(ROOT).as_posix()],
    }
    _write_json(OBSERVATIONS_PATH, [observation])


def validate_plan() -> None:
    plan = _load_json(PLAN_PATH)
    if plan.get("source_count") != 4:
        raise RuntimeError("partial update plan must preserve the complete four-source registry")
    if plan.get("update_count") != 1:
        raise RuntimeError("partial update plan must propose exactly one status change")
    rows = [row for row in plan.get("rows", []) if row.get("source_name") == SOURCE_NAME]
    if len(rows) != 1:
        raise RuntimeError("partial update plan must contain exactly one CEQAnet row")
    row = rows[0]
    expected = {
        "current_verification_status": "unverified",
        "proposed_verification_status": "partial",
        "planned_action": "mark_partial_candidate",
        "update_required": True,
    }
    for field, value in expected.items():
        if row.get(field) != value:
            raise RuntimeError(f"partial update plan {field} mismatch")
    if row.get("evidence_refs") != [EVIDENCE_PATH.relative_to(ROOT).as_posix()]:
        raise RuntimeError("partial update plan must bind the bounded evidence reference")


def reconcile_after_apply() -> None:
    registry = _load_json(REGISTRY_PATH)
    matches = [row for row in registry if row.get("source_name") == SOURCE_NAME]
    if len(matches) != 1:
        raise RuntimeError("updated registry must contain exactly one CEQAnet source")
    ceqanet = matches[0]
    if ceqanet.get("verification_status") != "partial":
        raise RuntimeError("controlled apply did not classify CEQAnet as partial")
    if ceqanet.get("last_checked_date") is not None:
        raise RuntimeError("status-only apply must not modify last_checked_date")
    if any(
        row.get("verification_status") != "unverified"
        for row in registry
        if row.get("source_name") != SOURCE_NAME
    ):
        raise RuntimeError("controlled apply changed an unrelated source status")

    audit = _load_json(AUDIT_PATH)
    if audit.get("applied_count") != 1 or audit.get("registry_changed") is not True:
        raise RuntimeError("controlled apply audit does not record one applied change")
    applied_rows = [
        row for row in audit.get("rows", []) if row.get("source_name") == SOURCE_NAME
    ]
    if len(applied_rows) != 1:
        raise RuntimeError("controlled apply audit must contain exactly one CEQAnet row")
    applied = applied_rows[0]
    if applied.get("previous_verification_status") != "unverified":
        raise RuntimeError("controlled apply audit previous status mismatch")
    if applied.get("resulting_verification_status") != "partial":
        raise RuntimeError("controlled apply audit resulting status mismatch")
    if applied.get("applied") is not True:
        raise RuntimeError("controlled apply audit did not mark the CEQAnet row applied")

    _replace_once(
        REPORT_PATH,
        "The canonical source must remain unverified until that review is explicit and a controlled promotion plan is approved.",
        "The canonical source is now classified as partial through a separate controlled apply. It must not be promoted to verified until terms review is explicit and a verified-status plan is separately approved.",
    )

    _reconcile_readme()
    _reconcile_status_matrix()
    _reconcile_audit_inventory()
    _reconcile_recurring_governance()
    _write_partial_report(audit)


def _reconcile_readme() -> None:
    path = ROOT / "README.md"
    _replace_once(
        path,
        "Adapter contracts are not the same thing as live source integrations. Most adapter families are still placeholder contracts. Source records in `data/source_registry.seed.json` are seed targets and must remain treated as unverified until checked. Run `constructionsight-source-status report data/source_registry.seed.json` before making any source-readiness claim. Run `constructionsight-source-readiness check data/source_registry.seed.json` and `constructionsight-audit-package build data/source_registry.seed.json --check-http` to produce non-mutating evidence. Use the source checklist, promotion plan, and registry plan commands before any status change. Controlled apply requires a reviewed plan digest, evidence references, explicit `--apply`, status-only mutation, stale-state validation, audit output, and atomic file replacement.",
        "Adapter contracts are not the same thing as live source integrations. Most adapter families are still placeholder contracts. Source records in `data/source_registry.seed.json` preserve per-source maturity: CEQAnet is currently `partial` based on bounded public evidence, while the other canonical sources remain `unverified`. Partial status is not verified usable coverage and does not unlock recurring execution. Run `constructionsight-source-status report data/source_registry.seed.json` before making any source-readiness claim. Run `constructionsight-source-readiness check data/source_registry.seed.json` and `constructionsight-audit-package build data/source_registry.seed.json --check-http` to produce non-mutating evidence. Use the source checklist, promotion plan, and registry plan commands before any status change. Controlled apply requires a reviewed plan digest, evidence references, explicit `--apply`, status-only mutation, stale-state validation, audit output, and atomic file replacement.",
    )
    _replace_once(
        path,
        "Current observed HTTP audit-package outcome for the seed registry is: CEQAnet `cross_host_redirect`, CSLB `no_redirect`, San Bernardino EZOP `same_host_redirect`, Riverside PLUS `downgraded_to_http`, and all four sources `keep_unverified_reachable`. This implementation does not promote any current seed source.",
        "Current canonical maturity is CEQAnet `partial` and the other three source records `unverified`. The bounded CEQAnet evidence observed official entry, search, result-list, and detail behavior without an immediate access barrier; terms review remains incomplete. Partial status remains blocked from recurring execution until a separate verified-status review and controlled apply are completed.",
    )


def _reconcile_status_matrix() -> None:
    path = ROOT / "docs/architecture/current_implementation_status.md"
    _replace_once(
        path,
        "| Source registry | Yes | Yes | Yes | Yes | Yes | No | Seed records remain unverified until checked; controlled apply changes only an approved evidence-backed verification status and does not create live coverage. |",
        "| Source registry | Yes | Yes | Yes | Yes | Yes | No | CEQAnet is evidence-backed `partial`; the other canonical sources remain `unverified`. Controlled apply changes only an approved status and does not create live coverage. |",
    )
    _replace_once(
        path,
        "| CEQAnet recurring-run governance | Yes | Yes | Yes | Artifact-only | Yes | Guarded only | Exact-schema definitions, manifests, executions, and verifications bind source evidence, exact windows, attempts, retained response envelopes, and current-evidence authority. Canonical CEQAnet data remains unverified, so current repository artifacts remain blocked. |",
        "| CEQAnet recurring-run governance | Yes | Yes | Yes | Artifact-only | Yes | Guarded only | Exact-schema definitions, manifests, executions, and verifications bind source evidence, exact windows, attempts, retained response envelopes, and current-evidence authority. CEQAnet is `partial`, not `verified`, and terms review is incomplete, so execution remains blocked. |",
    )
    _replace_once(
        path,
        "| CS-VIAM-016 | P1 | CEQAnet execution evidence | Initial recurring-run executions had semantic verification but no digest over the complete retained response envelope. | Exact execution schemas and a canonical execution digest now bind bodies, URLs, counts, queries, flags, identities, and the no-persistence assertion before semantic verification. |",
        "| CS-VIAM-016 | P1 | CEQAnet execution evidence | Initial recurring-run executions had semantic verification but no digest over the complete retained response envelope. | Exact execution schemas and a canonical execution digest now bind bodies, URLs, counts, queries, flags, identities, and the no-persistence assertion before semantic verification. |\n| CS-VIAM-017 | P1 | CEQAnet evidence phase | PR #93 merged temporary write-enabled collection tooling instead of the claimed evidence packet and audit report. | A repair phase regenerated and committed the evidence, removed all temporary tooling, applied an evidence-bound `partial` status through the controlled registry path, reconciled documentation, and added a regression test. |",
    )
    _replace_once(
        path,
        "| CS-PLAN-002 | Verified recurring live adapters | CEQAnet now has exact-schema, evidence-bound definitions, exact-window manifests, stale-evidence rejection, digest-bound bounded attempts, and full execution verification; canonical source data remains unverified and no scheduler exists. | Complete source-specific evidence review and maturity promotion, then define persisted attempt, scheduling, retry, archive, observability, and downstream handoff governance. |",
        "| CS-PLAN-002 | Verified recurring live adapters | CEQAnet is evidence-backed `partial` and has exact-schema definitions, manifests, stale-evidence rejection, digest-bound attempts, and full execution verification; terms review is incomplete and no scheduler exists. | Complete terms review and separate verified-status controlled apply, then define persisted attempt, scheduling, retry, archive, observability, and downstream handoff governance. |",
    )


def _reconcile_audit_inventory() -> None:
    path = ROOT / "docs/audits/full_repo_audit_inventory.md"
    _replace_once(
        path,
        "ConstructionSight is not yet a production recurring live-source platform. Most adapter families are contracts or planned integrations. CEQAnet has guarded execution, archive tooling, and recurring-run governance, but the canonical source remains unverified and no production scheduler exists. Four canonical source-registry seed records remain unverified. No external outreach-sending behavior or GUI/operator application is implemented.",
        "ConstructionSight is not yet a production recurring live-source platform. Most adapter families are contracts or planned integrations. CEQAnet has guarded execution, archive tooling, recurring-run governance, and bounded evidence-backed `partial` maturity, but it is not verified and no production scheduler exists. The other three canonical source records remain unverified. No external outreach-sending behavior or GUI/operator application is implemented.",
    )
    _replace_once(
        path,
        "| Source registry | Yes | Yes | Yes | File-backed | Yes | No | Seed status is distinct from verified usable coverage. |",
        "| Source registry | Yes | Yes | Yes | File-backed | Yes | No | CEQAnet is `partial`; three canonical sources remain `unverified`. Neither state implies verified usable coverage. |",
    )
    _replace_once(
        path,
        "| CEQAnet recurring-run governance | Yes | Yes | Yes | Artifact-only | Yes | Guarded only | Exact schemas and canonical digests bind source identity, evidence, query, window, attempts, and complete retained response envelopes. Execution requires current registry/checklist agreement and explicit authorization. Canonical source data remains blocked because it is unverified. |",
        "| CEQAnet recurring-run governance | Yes | Yes | Yes | Artifact-only | Yes | Guarded only | Exact schemas and canonical digests bind source identity, evidence, query, window, attempts, and complete retained response envelopes. Execution requires `verified` registry state, completed terms review, current evidence agreement, and explicit authorization; `partial` CEQAnet remains blocked. |",
    )
    _replace_once(
        path,
        "| CS-AUDIT-022 | P1 | CEQAnet execution evidence | Recurring-run executions initially had field-level semantic checks but no digest over the complete retained response envelope. | Exact execution schemas and a canonical execution digest now bind bodies, URLs, queries, counts, flags, identities, and the no-persistence assertion before semantic verification. |",
        "| CS-AUDIT-022 | P1 | CEQAnet execution evidence | Recurring-run executions initially had field-level semantic checks but no digest over the complete retained response envelope. | Exact execution schemas and a canonical execution digest now bind bodies, URLs, queries, counts, flags, identities, and the no-persistence assertion before semantic verification. |\n| CS-AUDIT-023 | P1 | CEQAnet evidence phase | PR #93 merged temporary write-enabled collection files while the claimed evidence JSON and audit report were absent from `main`. | The repair phase regenerated and committed the evidence packet, removed temporary tooling, used deterministic controlled apply for `unverified → partial`, reconciled all maturity claims, and added permanent regression coverage. |",
    )
    _replace_once(
        path,
        "| CS-PLAN-002 | Verified recurring live source adapters | CEQAnet has exact-schema evidence-bound definitions, exact-window manifests, stale-evidence rejection, digest-bound attempts, and complete execution verification. Canonical source data remains unverified; attempts are not scheduled or persisted as a ledger. | Complete source-specific evidence review and maturity promotion, then define persisted attempt identity, scheduling, retry, archive, observability, and downstream handoff governance. |",
        "| CS-PLAN-002 | Verified recurring live source adapters | CEQAnet has evidence-backed `partial` maturity plus exact-schema definitions, manifests, stale-evidence rejection, digest-bound attempts, and complete execution verification. Terms review is incomplete; attempts are not scheduled or persisted as a ledger. | Complete terms review and a separate verified-status controlled apply, then define persisted attempt identity, scheduling, retry, archive, observability, and downstream handoff governance. |",
    )
    _replace_once(path, "| Seed source records | Four unverified records. |", "| Seed source records | One partial CEQAnet record and three unverified records. |")
    _replace_once(path, "| Verified usable source | Zero in the canonical registry. |", "| Verified usable source | Zero; `partial` CEQAnet remains below verified execution authority. |")
    _replace_once(
        path,
        "| Guarded live read-only execution | Limited CEQAnet executors and recurring-run governance exist. Current canonical CEQAnet definitions remain blocked. |",
        "| Guarded live read-only execution | Limited CEQAnet executors and recurring-run governance exist. Current CEQAnet definitions remain blocked because registry state is `partial` and terms review is incomplete. |",
    )


def _reconcile_recurring_governance() -> None:
    path = ROOT / "docs/architecture/ceqanet_recurring_run_governance.md"
    _replace_once(
        path,
        "The canonical CEQAnet registry record remains unverified. Therefore, a definition produced from current canonical repository data remains blocked and cannot execute through this boundary.",
        "The canonical CEQAnet registry record is evidence-backed `partial`, not `verified`, and its terms review remains incomplete. Therefore, a definition produced from current canonical repository data remains blocked and cannot execute through this boundary.",
    )


def _write_partial_report(audit: dict[str, Any]) -> None:
    evidence_ref = EVIDENCE_PATH.relative_to(ROOT).as_posix()
    plan_ref = PLAN_PATH.relative_to(ROOT).as_posix()
    audit_ref = AUDIT_PATH.relative_to(ROOT).as_posix()
    report = f"""# CEQAnet Partial Maturity Classification

Observation date: `{DATE}`

## Classification

CEQAnet is classified as `partial`, not `verified`.

The bounded evidence established official public entry, query, result-list, and detail-page behavior without an observed login, captcha, paywall, document download, persistence mutation, or robots prohibition on the reviewed paths. Terms review remains incomplete.

## Controlled apply

- Previous status: `unverified`
- Resulting status: `partial`
- Applied rows: `{audit['applied_count']}`
- Plan digest: `{audit['plan_digest']}`
- Original registry digest: `{audit['original_registry_digest']}`
- Updated registry digest: `{audit['updated_registry_digest']}`

The controlled apply changed only `verification_status`. It did not modify `last_checked_date`, provenance, URLs, adapter maturity, or any unrelated source.

## Functional effect

Partial maturity lets operators and status reports distinguish evidence-backed source behavior from untouched seed targets. It does not unlock CEQAnet recurring execution. The recurring-run boundary still requires registry status `verified`, observed terms review, current evidence agreement, and explicit per-attempt authorization.

## Evidence and audit artifacts

- `{evidence_ref}`
- `{CHECKLIST_PATH.relative_to(ROOT).as_posix()}`
- `{OBSERVATIONS_PATH.relative_to(ROOT).as_posix()}`
- `{plan_ref}`
- `{audit_ref}`

## Remaining gate

Review the inventoried official terms, privacy, accessibility, conditions, and copyright material. Any later `partial → verified` transition must use a separate deterministic plan and controlled apply.
"""
    PARTIAL_REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: repair_ceqanet_evidence_partial.py prepare|validate-plan|reconcile")
    command = sys.argv[1]
    if command == "prepare":
        prepare_observations()
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
