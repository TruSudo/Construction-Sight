"""Scope-bound application facade for one manual CEQAnet recurring-run attempt."""

from __future__ import annotations

from dataclasses import dataclass

from constructionsight.authorization_decision import AuthorizationDeniedError
from constructionsight.authorization_decision_models import authorization_digest
from constructionsight.ceqanet_recurring_run_models import (
    CeqanetRecurringRunDefinition,
    CeqanetRecurringRunExecution,
    CeqanetRecurringRunManifest,
    CeqanetRunReadiness,
)
from constructionsight.ceqanet_recurring_run_service import (
    assert_ceqanet_definition_evidence_current,
    bind_authorized_recurring_listing_evidence,
    execute_ceqanet_recurring_run,
)
from constructionsight.effect_consumption import _execute_owned_effect
from constructionsight.effect_consumption_models import EffectReplayPolicy
from constructionsight.local_operator_authorization import (
    LocalAuthorizationResult,
    authorize_local_operator_operation,
)
from constructionsight.models import PublicSource
from constructionsight.source_verification_checklist_models import (
    SourceVerificationChecklistReport,
)


@dataclass(frozen=True)
class AuthorizedRecurringRunResult:
    """Immutable execution and authorization pair."""

    execution: CeqanetRecurringRunExecution
    authorization: LocalAuthorizationResult


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
) -> AuthorizedRecurringRunResult:
    """Authorize one exact, foreground, manually initiated manifest attempt."""

    if not caller_confirmation:
        raise AuthorizationDeniedError(
            "explicit live execution authorization is required in addition to "
            "scope-bound authority"
        )
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
            "definition_digest": definition.definition_digest,
            "manifest_digest": manifest.manifest_digest,
            "source_registry_digest": definition.source_registry_digest,
            "checklist_evidence_digest": definition.checklist_evidence_digest,
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
        caller_confirmation=True,
        limitations=tuple(
            sorted(
                {
                    "attempt uniqueness is enforced by a durable cross-process "
                    "consumption reservation",
                    "local operator identity is not authentication",
                    "manual execution does not authorize scheduling or recurrence",
                    "one durable manifest-attempt allowance across processes",
                },
                key=str.casefold,
            )
        ),
        operator_id=operator_id,
        current_revocation_identity=current_state_identity,
    )
    attempt_identity = authorization_digest(
        "ceqanet-recurring-run-attempt",
        {
            "run_id": manifest.run_id,
            "manifest_digest": manifest.manifest_digest,
            "attempt_sequence": attempt_sequence,
        },
    )

    def execute_owned_recurring_run(_trusted_at: object) -> CeqanetRecurringRunExecution:
        execution = execute_ceqanet_recurring_run(
            definition,
            manifest,
            sources,
            checklist_report,
            attempt_sequence=attempt_sequence,
            execute_live=True,
        )
        return bind_authorized_recurring_listing_evidence(
            execution,
            manifest,
            authorization=authorization.to_dict(),
        )

    execution = _execute_owned_effect(
        authorization,
        allowance_identity=attempt_identity,
        content_identity=current_state_identity,
        implementation_id=(
            "constructionsight.ceqanet_recurring_run_service."
            "execute_ceqanet_recurring_run"
        ),
        replay_policy=EffectReplayPolicy.EXACT,
        effect=execute_owned_recurring_run,
        encode_result=lambda result: result.model_dump(mode="json"),
        decode_result=lambda payload: CeqanetRecurringRunExecution.model_validate(payload),
    )
    return AuthorizedRecurringRunResult(
        execution=execution,
        authorization=authorization,
    )
