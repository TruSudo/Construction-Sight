"""Scope-bound operator authorization for persisted lead workflow transitions."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from constructionsight.authorization_decision import AuthorizationDeniedError
from constructionsight.authorization_decision_models import authorization_digest
from constructionsight.effect_consumption import _execute_owned_effect
from constructionsight.effect_consumption_models import EffectReplayPolicy
from constructionsight.lead_operator_models import LeadWorkflowTransitionReport
from constructionsight.lead_operator_service import (
    LeadOperatorError,
    load_persisted_lead_workflow,
    transition_persisted_lead_workflow,
)
from constructionsight.lead_workflow_models import LeadWorkflowStatus
from constructionsight.local_operator_authorization import (
    LocalAuthorizationResult,
    authorize_local_operator_operation,
)


@dataclass(frozen=True)
class AuthorizedLeadWorkflowTransitionResult:
    """Persisted transition report and its claimed authorization."""

    report: LeadWorkflowTransitionReport
    authorization: LocalAuthorizationResult


def apply_authorized_lead_workflow_transition(
    session: Session,
    *,
    workflow_id: str,
    expected_current_status: LeadWorkflowStatus,
    next_status: LeadWorkflowStatus,
    reason: str,
    caller_confirmation: bool,
    operator_id: str | None = None,
) -> AuthorizedLeadWorkflowTransitionResult:
    """Authorize and apply one exact persisted workflow transition."""

    if not caller_confirmation:
        raise AuthorizationDeniedError(
            "caller confirmation is required in addition to scope-bound authority"
        )
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise LeadOperatorError("workflow transition reason must not be blank")
    current = load_persisted_lead_workflow(session, workflow_id)
    if current.status is not expected_current_status:
        raise LeadOperatorError(
            "lead workflow current status does not match the operator expectation: "
            f"expected {expected_current_status.value}, "
            f"observed {current.status.value}"
        )
    state_identity = authorization_digest(
        "lead-workflow-transition-state",
        {
            "workflow": current.model_dump(mode="json"),
            "expected_current_status": expected_current_status.value,
            "next_status": next_status.value,
        },
    )
    resource_id = authorization_digest(
        "lead-workflow-transition-resource",
        {
            "workflow_id": workflow_id,
            "current_status": current.status.value,
            "next_status": next_status.value,
        },
    )
    exact_scope = tuple(
        sorted(
            {
                f"current-status:{current.status.value}",
                f"event-count:{len(current.events)}",
                f"expected-current-status:{expected_current_status.value}",
                f"next-status:{next_status.value}",
                f"workflow-id:{workflow_id}",
                f"workflow-state:{state_identity}",
            },
            key=str.casefold,
        )
    )
    authorization = authorize_local_operator_operation(
        action="transition-lead-workflow",
        resource_type="persisted-lead-workflow",
        resource_id=resource_id,
        exact_scope=exact_scope,
        current_state_identity=state_identity,
        expected_identity=state_identity,
        granted_authority=(
            "apply one exact matrix-valid persisted workflow transition",
        ),
        denied_authority=tuple(
            sorted(
                {
                    "automatic recurrence",
                    "generic record editing",
                    "outreach sending",
                    "result authority mutation",
                    "source promotion",
                    "status skipping",
                    "workflow deletion",
                    "workflow identity mutation",
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
                    "one durable exact-transition allowance across processes",
                    "transition authority does not grant result or outreach authority",
                },
                key=str.casefold,
            )
        ),
        operator_id=operator_id,
        current_revocation_identity=state_identity,
    )

    def execute(_trusted_at: object) -> LeadWorkflowTransitionReport:
        report = transition_persisted_lead_workflow(
            session,
            workflow_id=workflow_id,
            expected_current_status=expected_current_status,
            next_status=next_status,
            reason=normalized_reason,
        )
        session.commit()
        return report

    report = _execute_owned_effect(
        authorization,
        allowance_identity=authorization_digest(
            "lead-workflow-transition-allowance",
            {"resource_id": resource_id, "state_identity": state_identity},
        ),
        content_identity=state_identity,
        implementation_id=(
            "constructionsight.lead_operator_service."
            "transition_persisted_lead_workflow"
        ),
        replay_policy=EffectReplayPolicy.EXACT,
        effect=execute,
        encode_result=lambda result: result.model_dump(mode="json"),
        decode_result=lambda payload: LeadWorkflowTransitionReport.model_validate(payload),
    )
    return AuthorizedLeadWorkflowTransitionResult(
        report=report,
        authorization=authorization,
    )
