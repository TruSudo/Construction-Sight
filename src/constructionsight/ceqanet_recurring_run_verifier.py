"""Canonical CEQAnet recurring-run execution verification boundary."""

from __future__ import annotations

from constructionsight.ceqanet_recurring_run_models import (
    CeqanetRecurringRunDefinition,
    CeqanetRecurringRunExecution,
    CeqanetRecurringRunManifest,
    CeqanetRecurringRunVerification,
)
from constructionsight.ceqanet_recurring_run_service import (
    verify_ceqanet_recurring_run_execution as _verify_semantics,
)
from constructionsight.models import PublicSource
from constructionsight.source_verification_checklist_models import (
    SourceVerificationChecklistReport,
)


def verify_ceqanet_recurring_run_execution(
    definition: CeqanetRecurringRunDefinition,
    manifest: CeqanetRecurringRunManifest,
    execution: CeqanetRecurringRunExecution,
    sources: list[PublicSource] | None = None,
    checklist_report: SourceVerificationChecklistReport | None = None,
) -> CeqanetRecurringRunVerification:
    """Verify complete execution evidence before semantic agreement checks."""

    semantic_verification = _verify_semantics(
        definition,
        manifest,
        execution,
        sources,
        checklist_report,
    )
    findings = list(semantic_verification.findings)
    try:
        execution.assert_integrity()
    except ValueError as exc:
        findings.insert(0, str(exc))
    return CeqanetRecurringRunVerification(
        passed=not findings,
        finding_count=len(findings),
        findings=findings,
        run_id=semantic_verification.run_id,
        definition_digest=semantic_verification.definition_digest,
        manifest_digest=semantic_verification.manifest_digest,
    )
