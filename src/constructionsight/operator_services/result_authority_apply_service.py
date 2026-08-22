"""Scope-bound operator authorization for authoritative result selection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from constructionsight.authorization_decision import AuthorizationDeniedError
from constructionsight.authorization_decision_models import authorization_digest
from constructionsight.effect_consumption import _execute_owned_effect
from constructionsight.effect_consumption_models import EffectReplayPolicy
from constructionsight.lead_operator_service import load_persisted_lead_workflow
from constructionsight.local_operator_authorization import (
    LocalAuthorizationResult,
    authorize_local_operator_operation,
)
from constructionsight.result_authority_models import ResultAuthorityApplyReport
from constructionsight.result_authority_service import (
    ResultAuthorityError,
    apply_authoritative_result,
    load_result_authority_snapshot,
)
from constructionsight.result_ledger_models import ResultLedgerStatus


@dataclass(frozen=True)
class AuthorizedResultAuthorityApplyResult:
    """Authoritative result report and its claimed operator authorization."""

    report: ResultAuthorityApplyReport
    authorization: LocalAuthorizationResult


def apply_authorized_authoritative_result(
    session: Session,
    *,
    workflow_id: str,
    expected_current_ledger_id: str | None,
    status: ResultLedgerStatus,
    authorization_reason: str,
    caller_confirmation: bool,
    decided_date: date | None = None,
    gross_value: float | None = None,
    share_rate: float | None = None,
    outcome_reasons: list[str] | None = None,
    operator_id: str | None = None,
) -> AuthorizedResultAuthorityApplyResult:
    """Authorize and apply one exact initial result or correction."""

    if not caller_confirmation:
        raise AuthorizationDeniedError(
            "caller confirmation is required in addition to scope-bound authority"
        )
    normalized_reason = authorization_reason.strip()
    if not normalized_reason:
        raise ResultAuthorityError("result authority reason must not be blank")
    workflow = load_persisted_lead_workflow(session, workflow_id)
    snapshot = load_result_authority_snapshot(session, workflow_id)
    observed_ledger_id = snapshot.current.ledger_id if snapshot is not None else None
    if observed_ledger_id != expected_current_ledger_id:
        expected = expected_current_ledger_id or "none"
        observed = observed_ledger_id or "none"
        raise ResultAuthorityError(
            "result authority current ledger does not match the operator expectation: "
            f"expected {expected}, observed {observed}"
        )
    normalized_outcome_reasons = list(outcome_reasons or [])
    desired_outcome_identity = authorization_digest(
        "result-authority-desired-outcome",
        {
            "status": status.value,
            "decided_date": decided_date.isoformat() if decided_date else None,
            "gross_value": gross_value,
            "share_rate": share_rate,
            "outcome_reasons": normalized_outcome_reasons,
        },
    )
    state_identity = authorization_digest(
        "result-authority-current-state",
        {
            "workflow": workflow.model_dump(mode="json"),
            "current_snapshot": (
                snapshot.model_dump(mode="json") if snapshot is not None else None
            ),
            "expected_current_ledger_id": expected_current_ledger_id,
        },
    )
    resource_id = authorization_digest(
        "result-authority-resource",
        {
            "workflow_id": workflow_id,
            "current_ledger_id": observed_ledger_id,
            "desired_outcome_identity": desired_outcome_identity,
        },
    )
    exact_scope = tuple(
        sorted(
            {
                f"current-ledger:{observed_ledger_id or 'none'}",
                f"desired-outcome:{desired_outcome_identity}",
                f"expected-current-ledger:{expected_current_ledger_id or 'none'}",
                f"status:{status.value}",
                f"workflow-id:{workflow_id}",
                f"workflow-status:{workflow.status.value}",
            },
            key=str.casefold,
        )
    )
    authorization = authorize_local_operator_operation(
        action="apply-authoritative-result",
        resource_type="result-authority-ledger-tip",
        resource_id=resource_id,
        exact_scope=exact_scope,
        current_state_identity=state_identity,
        expected_identity=state_identity,
        granted_authority=(
            "create or correct one exact authoritative result ledger tip",
        ),
        denied_authority=tuple(
            sorted(
                {
                    "automatic recurrence",
                    "generic ledger editing",
                    "history deletion",
                    "outreach sending",
                    "share payment execution",
                    "source promotion",
                    "workflow transition",
                },
                key=str.casefold,
            )
        ),
        reason=normalized_reason,
        caller_confirmation=True,
        limitations=tuple(
            sorted(
                {
                    "local operator identity is not authentication",
                    "result authority does not authorize payment or outreach",
                    "one durable exact-result allowance across processes",
                },
                key=str.casefold,
            )
        ),
        operator_id=operator_id,
        current_revocation_identity=state_identity,
    )

    def execute(_trusted_at: object) -> ResultAuthorityApplyReport:
        report = apply_authoritative_result(
            session,
            workflow_id=workflow_id,
            expected_current_ledger_id=expected_current_ledger_id,
            status=status,
            authority_reason=normalized_reason,
            decided_date=decided_date,
            gross_value=gross_value,
            share_rate=share_rate,
            outcome_reasons=normalized_outcome_reasons,
        )
        session.commit()
        return report

    report = _execute_owned_effect(
        authorization,
        allowance_identity=authorization_digest(
            "result-authority-apply-allowance",
            {"resource_id": resource_id, "state_identity": state_identity},
        ),
        content_identity=desired_outcome_identity,
        implementation_id=(
            "constructionsight.result_authority_service.apply_authoritative_result"
        ),
        replay_policy=EffectReplayPolicy.EXACT,
        effect=execute,
        encode_result=lambda result: result.model_dump(mode="json"),
        decode_result=lambda payload: ResultAuthorityApplyReport.model_validate(payload),
    )
    return AuthorizedResultAuthorityApplyResult(
        report=report,
        authorization=authorization,
    )
