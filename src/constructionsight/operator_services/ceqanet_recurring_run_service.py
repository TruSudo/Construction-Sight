"""Scope-bound application facade for one manual CEQAnet recurring-run attempt."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from constructionsight.adapters.ceqanet_listing_executor import CeqanetListingHttpClient
from constructionsight.authorization_decision import AuthorizationUseLedger
from constructionsight.authorization_decision_models import authorization_digest
from constructionsight.ceqanet_recurring_run_models import (
    CeqanetRecurringRunDefinition,
    CeqanetRecurringRunExecution,
    CeqanetRecurringRunManifest,
    CeqanetRunReadiness,
)
from constructionsight.ceqanet_recurring_run_service import (
    assert_ceqanet_definition_evidence_current,
    execute_ceqanet_recurring_run,
)
from constructionsight.local_operator_authorization import (
    LocalAuthorizationResult,
    authorize_local_operator_operation,
)
from constructionsight.models import PublicSource
from constructionsight.source_verification_checklist_models import (
    SourceVerificationChecklistReport,
)


class RecurringRunExecutor(Protocol):
    """Execution interface used by the authorized facade and deterministic tests."""

    def __call__(
        self,
        definition: CeqanetRecurringRunDefinition,
        manifest: CeqanetRecurringRunManifest,
        sources: list[PublicSource],
        checklist_report: SourceVerificationChecklistReport,
        *,
        attempt_sequence: int,
        execute_live: bool,
        client: CeqanetListingHttpClient | None = None,
    ) -> CeqanetRecurringRunExecution:
        """Execute one exact manifest attempt."""


class AuthorizedRecurringRunResult(tuple):
    """Immutable execution and authorization pair."""

    __slots__ = ()

    def __new__(
        cls,
        execution: CeqanetRecurringRunExecution,
        authorization: LocalAuthorizationResult,
    ) -> AuthorizedRecurringRunResult:
        return super().__new__(cls, (execution, authorization))

    @property
    def execution(self) -> CeqanetRecurringRunExecution:
        return self[0]

    @property
    def authorization(self) -> LocalAuthorizationResult:
        return self[1]


def execute_authorized_ceqanet_recurring_run(
    *,
    definition: CeqanetRecurringRunDefinition,
    manifest: CeqanetRecurringRunManifest,
    sources: list[PublicSource],
    checklist_report: SourceVerificationChecklistReport,
    attempt_sequence: int,
    caller_confirmation: bool,
    authorization_reason: str,
    operator_id: str | None = None,
    now: Callable[[], datetime] | None = None,
    ledger: AuthorizationUseLedger | None = None,
    client: CeqanetListingHttpClient | None = None,
    executor: RecurringRunExecutor | None = None,
) -> AuthorizedRecurringRunResult:
    """Authorize one exact, foreground, manually initiated manifest attempt."""

    definition.assert_integrity()
    manifest.assert_integrity()
    assert_ceqanet_definition_evidence_current(
        definition,
        sources,
        checklist_report,
    )
    if manifest.definition_digest != definition.definition_digest:
        raise ValueError("manifest definition digest does not match definition")
    if manifest.source_key != definition.source_key:
        raise ValueError("manifest source key does not match definition")
    if manifest.readiness is not CeqanetRunReadiness.READY_FOR_MANUAL_EXECUTION:
        raise ValueError("CEQAnet recurring-run manifest is blocked")
    if attempt_sequence < 1:
        raise ValueError("attempt_sequence must be at least 1")

    current_state_identity = authorization_digest(
        "ceqanet-recurring-run-current-state",
        {
            "definition": definition.model_dump(mode="json"),
            "manifest": manifest.model_dump(mode="json"),
            "sources": [source.model_dump(mode="json") for source in sources],
            "checklist": checklist_report.model_dump(mode="json"),
            "attempt_sequence": attempt_sequence,
        },
    )
    resource_id = authorization_digest(
        "ceqanet-recurring-run-resource",
        {
            "run_id": manifest.run_id,
            "manifest_digest": manifest.manifest_digest,
            "attempt_sequence": attempt_sequence,
        },
    )
    exact_scope = tuple(
        sorted(
            {
                f"attempt-sequence:{attempt_sequence}",
                f"definition-digest:{definition.definition_digest}",
                "execution-mode:foreground-manual",
                f"manifest-digest:{manifest.manifest_digest}",
                f"max-body-bytes:{manifest.max_body_chars}",
                f"max-pages:{definition.query_template.max_pages}",
                "method:GET",
                "policy:CS-NET-002",
                "redirects:denied",
                "retries-inside-attempt:0",
                f"run-id:{manifest.run_id}",
                f"source-key:{manifest.source_key}",
                f"timeout-seconds:{manifest.timeout_seconds:g}",
                f"window-end:{manifest.window_end.isoformat()}",
                f"window-start:{manifest.window_start.isoformat()}",
            },
            key=str.casefold,
        )
    )
    authorization = authorize_local_operator_operation(
        action="execute-ceqanet-recurring-run-attempt",
        resource_type="ceqanet-recurring-run-manifest",
        resource_id=resource_id,
        exact_scope=exact_scope,
        current_state_identity=current_state_identity,
        expected_identity=current_state_identity,
        granted_authority=(
            "execute one exact foreground CEQAnet manifest attempt",
        ),
        denied_authority=tuple(
            sorted(
                {
                    "access-control bypass",
                    "automatic recurrence",
                    "automatic retry",
                    "background scheduling",
                    "concurrent execution",
                    "credential use",
                    "document download",
                    "manifest mutation",
                    "persistence mutation",
                    "source promotion",
                },
                key=str.casefold,
            )
        ),
        reason=authorization_reason,
        caller_confirmation=caller_confirmation,
        limitations=tuple(
            sorted(
                {
                    "attempt uniqueness is local-process only until a durable attempt ledger exists",
                    "local operator identity is not authentication",
                    "manual execution does not authorize scheduling or recurrence",
                    "single local-process use only",
                },
                key=str.casefold,
            )
        ),
        operator_id=operator_id,
        current_revocation_identity=current_state_identity,
        now=now,
        ledger=ledger,
    )
    active_executor: RecurringRunExecutor = executor or execute_ceqanet_recurring_run
    execution = active_executor(
        definition,
        manifest,
        sources,
        checklist_report,
        attempt_sequence=attempt_sequence,
        execute_live=True,
        client=client,
    )
    return AuthorizedRecurringRunResult(execution, authorization)
