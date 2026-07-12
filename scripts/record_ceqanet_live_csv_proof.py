"""Validate one live CEQAnet CSV proof and reconcile canonical evidence ledgers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from constructionsight.ceqanet_csv_live_models import (
    CeqanetCsvLiveExecution,
    CeqanetCsvLiveVerification,
)
from constructionsight.ceqanet_csv_live_service import verify_ceqanet_csv_live_execution
from constructionsight.models import PublicSource, VerificationStatus

ROOT = Path(__file__).resolve().parents[1]
DATE = "2026-07-12"
EVIDENCE_DIR = ROOT / "evidence/source_verification"
EXECUTION_PATH = EVIDENCE_DIR / f"ceqanet_csv_live_execution_{DATE}.json"
VERIFICATION_PATH = EVIDENCE_DIR / f"ceqanet_csv_live_verification_{DATE}.json"
REPORT_PATH = ROOT / f"docs/audits/ceqanet_csv_live_proof_{DATE}.md"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one evidence-ledger anchor in {path}, found {count}: {old!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    execution = CeqanetCsvLiveExecution.model_validate(_load_json(EXECUTION_PATH))
    stored = CeqanetCsvLiveVerification.model_validate(_load_json(VERIFICATION_PATH))
    recomputed = verify_ceqanet_csv_live_execution(execution)
    if stored != recomputed:
        raise RuntimeError("stored CEQAnet CSV verification does not match offline recomputation")

    if execution.request.sch_number != "2026030377" or execution.request.document_id is not None:
        raise RuntimeError("live proof request identity does not match the approved project export")
    if execution.retry_count != 0:
        raise RuntimeError("live proof must perform no retry")
    if execution.documents_downloaded or execution.persistence_mutated:
        raise RuntimeError("live proof crossed a forbidden mutation or document boundary")

    registry = [
        PublicSource.model_validate(item)
        for item in _load_json(ROOT / "data/source_registry.seed.json")
    ]
    ceqanet = [source for source in registry if source.platform_family.value == "ceqanet"]
    if len(ceqanet) != 1 or ceqanet[0].verification_status is not VerificationStatus.PARTIAL:
        raise RuntimeError("live proof phase must preserve CEQAnet partial maturity")

    _write_report(execution, stored)
    _reconcile_readme(execution, stored)
    _reconcile_architecture(execution, stored)
    _reconcile_status(execution, stored)
    _reconcile_audit(execution, stored)


def _result_text(
    execution: CeqanetCsvLiveExecution,
    verification: CeqanetCsvLiveVerification,
) -> str:
    if verification.passed:
        assert execution.inspection is not None
        return (
            "The bounded project CSV proof passed: HTTP 200 returned a complete valid CSV "
            f"with {execution.inspection.row_count} source rows and an independently verified "
            "inspection digest."
        )
    findings = "; ".join(verification.findings)
    return (
        "The bounded project CSV proof failed and was preserved without retry or bypass. "
        f"HTTP status: {execution.status_code}; findings: {findings}"
    )


def _next_gate(verification: CeqanetCsvLiveVerification) -> str:
    if verification.passed:
        return (
            "Review the point-in-time success and its schema separately before any controlled "
            "source-promotion proposal. Promotion, recurring execution, retries, persistence, "
            "and broader coverage remain unauthorized."
        )
    return (
        "Keep CEQAnet partial. Any further access investigation, source clarification, or later "
        "proof must be a separate explicitly authorized phase; no retry or bypass is implied."
    )


def _write_report(
    execution: CeqanetCsvLiveExecution,
    verification: CeqanetCsvLiveVerification,
) -> None:
    inspection = execution.inspection
    headers = inspection.normalized_headers if inspection is not None else []
    row_count = inspection.row_count if inspection is not None else None
    findings = verification.findings or ["none"]
    report = f"""# CEQAnet Bounded Live CSV Proof

Executed at: `{execution.executed_at.isoformat()}`

## Approved request

- Method: `{execution.method}`
- Request URL: `{execution.request_url}`
- Final URL: `{execution.final_url}`
- SCH number: `{execution.request.sch_number}`
- Retry count: `{execution.retry_count}`
- Explicit network execution: `{str(execution.network_executed).lower()}`

## Response evidence

- HTTP status: `{execution.status_code}`
- Content type: `{execution.content_type}`
- Content disposition: `{execution.content_disposition}`
- Observed body bytes: `{execution.observed_body_byte_length}`
- Retained body bytes: `{execution.retained_body_byte_length}`
- Complete body retained: `{str(execution.retained_body_complete).lower()}`
- Body SHA-256: `{execution.body_sha256}`
- Execution digest: `{execution.execution_digest}`
- Document downloads: `{str(execution.documents_downloaded).lower()}`
- Persistence mutated: `{str(execution.persistence_mutated).lower()}`

## Canonical inspection

- Inspection present: `{str(inspection is not None).lower()}`
- Row count: `{row_count}`
- Headers: `{json.dumps(headers)}`
- Inspection error: `{execution.inspection_error}`
- Inspection digest: `{verification.inspection_digest}`

## Independent verification

- Passed: `{str(verification.passed).lower()}`
- Finding count: `{verification.finding_count}`
- Findings:
{chr(10).join(f"  - {finding}" for finding in findings)}

## Maturity decision

CEQAnet remains `partial`. This one request does not itself change source maturity.

{_next_gate(verification)}

## Evidence artifacts

- `{EXECUTION_PATH.relative_to(ROOT).as_posix()}`
- `{VERIFICATION_PATH.relative_to(ROOT).as_posix()}`
"""
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")


def _reconcile_readme(
    execution: CeqanetCsvLiveExecution,
    verification: CeqanetCsvLiveVerification,
) -> None:
    path = ROOT / "README.md"
    result = _result_text(execution, verification)
    _replace_once(
        path,
        "ConstructionSight now has an official CSV contract that can plan exact project/document export URLs, validate already-obtained CSV bytes, and perform one explicitly authorized bounded GET with no retry. The live-proof boundary retains the complete response envelope and canonical offline inspection but has not yet produced a committed live proof. Source maturity therefore remains `partial`; promotion remains a separate controlled decision supported only by reviewed evidence.",
        "ConstructionSight has an official CSV contract that plans exact project/document export URLs, validates already-obtained CSV bytes, and performs one explicitly authorized bounded GET with no retry. "
        + result
        + " Source maturity remains `partial`; promotion remains a separate controlled decision supported only by reviewed evidence.",
    )
    _replace_once(
        path,
        "- `docs/architecture/ceqanet_official_csv_contract.md`\n",
        "- `docs/architecture/ceqanet_official_csv_contract.md`\n"
        "- `evidence/source_verification/ceqanet_csv_live_execution_2026-07-12.json`\n"
        "- `evidence/source_verification/ceqanet_csv_live_verification_2026-07-12.json`\n"
        "- `docs/audits/ceqanet_csv_live_proof_2026-07-12.md`\n",
    )
    _replace_once(
        path,
        "- The official CSV contract can perform one explicitly authorized proof request, but no live proof artifact has yet been committed or reviewed.\n- Real CEQAnet CSV availability and column drift remain unknown until a source-provided response is retained and passes the canonical inspection.\n",
        "- "
        + result
        + "\n- One point-in-time CSV result does not establish recurring availability, completeness, or broader source coverage.\n",
    )


def _reconcile_architecture(
    execution: CeqanetCsvLiveExecution,
    verification: CeqanetCsvLiveVerification,
) -> None:
    path = ROOT / "docs/architecture/ceqanet_official_csv_contract.md"
    result = _result_text(execution, verification)
    _replace_once(
        path,
        "The implementation now proves deterministic planning, strict offline validation, and a bounded live-proof mechanism. It does not yet prove that the current official CSV endpoint returns a reliable valid CSV response to ConstructionSight. The recorded automated HTML path returned HTTP 403 and remains blocked.",
        "The implementation proves deterministic planning, strict offline validation, and a bounded live-proof mechanism. "
        + result
        + " The recorded automated HTML path returned HTTP 403 and remains blocked.",
    )
    _replace_once(
        path,
        "A separate, self-removing evidence phase may perform one project-scoped request for observed SCH `2026030377`.\n\nThe resulting success or failure artifact must be committed with an offline verification report and reviewed before any source-status promotion, parser handoff, recurring schedule, rate policy, persisted attempt ledger, or persistence mutation is considered.",
        "One self-removing evidence phase performed the project-scoped request for SCH `2026030377` and committed the execution and offline verification artifacts.\n\n"
        + _next_gate(verification),
    )


def _reconcile_status(
    execution: CeqanetCsvLiveExecution,
    verification: CeqanetCsvLiveVerification,
) -> None:
    path = ROOT / "docs/architecture/current_implementation_status.md"
    result = _result_text(execution, verification)
    _replace_once(
        path,
        "| CEQAnet official CSV contract | Yes | Yes | Yes | Artifact-only | Yes | Guarded proof only | Exact official URL identities and offline body inspection remain canonical. A one-request/no-retry live-proof boundary now retains complete response evidence and independently verifies canonical inspection agreement. No live proof artifact, persistence, scheduling, or source promotion is claimed. |",
        "| CEQAnet official CSV contract | Yes | Yes | Yes | Artifact-only | Yes | Guarded proof only | Exact URL planning, offline inspection, and one-request/no-retry proof execution are implemented. "
        + result
        + " No persistence, scheduling, or source promotion is claimed. |",
    )
    _replace_once(
        path,
        "| CS-PLAN-002 | Verified recurring live adapters | CEQAnet has `partial` maturity, verified-only recurring-run governance, an offline official CSV inspector, and a one-request/no-retry live-proof boundary. Automated HTML collection received HTTP 403 and remains blocked; no live CSV proof or scheduler exists. | Execute one self-removing bounded project CSV proof, preserve and verify the complete response artifact, then make a separate controlled maturity decision before attempt-ledger, scheduling, archive, observability, and downstream handoff work. |",
        "| CS-PLAN-002 | Verified recurring live adapters | CEQAnet has `partial` maturity, verified-only recurring-run governance, and a committed one-request CSV proof artifact. Automated HTML collection received HTTP 403 and remains blocked; no scheduler exists. | "
        + _next_gate(verification)
        + " |",
    )


def _reconcile_audit(
    execution: CeqanetCsvLiveExecution,
    verification: CeqanetCsvLiveVerification,
) -> None:
    path = ROOT / "docs/audits/full_repo_audit_inventory.md"
    result = _result_text(execution, verification)
    _replace_once(
        path,
        "ConstructionSight is not yet a production recurring live-source platform. Most adapter families are contracts or planned integrations. CEQAnet is canonically `partial`: its official public pages, policies, data fields, and CSV links are materially observed, but bounded automated HTML collection received HTTP 403 and no bypass was attempted. The CSV contract now supports exact offline inspection and one explicitly authorized proof request, but no live proof artifact has been committed or reviewed. The other three canonical sources remain unverified. No source is currently `verified`, no production scheduler exists, and no external outreach-sending behavior or GUI/operator application is implemented.",
        "ConstructionSight is not yet a production recurring live-source platform. Most adapter families are contracts or planned integrations. CEQAnet is canonically `partial`: its official public pages, policies, data fields, and CSV links are materially observed, but bounded automated HTML collection received HTTP 403 and no bypass was attempted. "
        + result
        + " The other three canonical sources remain unverified. No source is currently `verified`, no production scheduler exists, and no external outreach-sending behavior or GUI/operator application is implemented.",
    )
    _replace_once(
        path,
        "| CEQAnet official CSV contract | Yes | Yes | Yes | Artifact-only | Yes | Guarded proof only | Exact URL planning and offline inspection remain canonical. One explicit GET with no retry may retain the complete response envelope, embed canonical inspection, and produce an independently verifiable execution digest. No live proof artifact or persistence is claimed. |",
        "| CEQAnet official CSV contract | Yes | Yes | Yes | Artifact-only | Yes | Guarded proof only | Exact planning, offline inspection, and one explicit no-retry GET are canonical. "
        + result
        + " The execution and verification artifacts are committed; no persistence is claimed. |",
    )
    _replace_once(
        path,
        "| CS-PLAN-002 | Verified recurring live source adapters | CEQAnet is `partial`, verified-only recurring-run governance exists, and the CSV surface has offline inspection plus a one-request/no-retry proof boundary. Automated HTML collection received HTTP 403; no CSV proof, attempt ledger, or scheduler exists. | Execute one self-removing bounded project CSV proof, preserve and verify its complete response evidence, then make a separate controlled maturity decision before attempt identity, scheduling, archive, observability, and downstream handoff work. |",
        "| CS-PLAN-002 | Verified recurring live source adapters | CEQAnet is `partial`, verified-only recurring-run governance exists, and one bounded CSV proof is committed. Automated HTML collection received HTTP 403; no attempt ledger or scheduler exists. | "
        + _next_gate(verification)
        + " |",
    )
    _replace_once(
        path,
        "| Official CSV contract | Deterministic URL planning, offline inspection, and one-request/no-retry proof execution exist; no live proof artifact is yet claimed. |",
        "| Official CSV contract | Deterministic planning, offline inspection, and one-request/no-retry proof execution exist. "
        + result
        + " |",
    )


if __name__ == "__main__":
    main()
