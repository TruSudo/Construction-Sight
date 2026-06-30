"""Lead workflow status transition rules."""

from __future__ import annotations

from constructionsight.lead_workflow_models import LeadWorkflowStatus

FINAL_LEAD_WORKFLOW_STATUSES: frozenset[LeadWorkflowStatus] = frozenset(
    {
        LeadWorkflowStatus.CLOSED_SUCCESS,
        LeadWorkflowStatus.CLOSED_NO_FIT,
    }
)

LEAD_WORKFLOW_TRANSITION_RULES: dict[LeadWorkflowStatus, frozenset[LeadWorkflowStatus]] = {
    LeadWorkflowStatus.HOLD: frozenset(
        {
            LeadWorkflowStatus.MONITOR,
            LeadWorkflowStatus.REVIEW,
        }
    ),
    LeadWorkflowStatus.MONITOR: frozenset(
        {
            LeadWorkflowStatus.REVIEW,
            LeadWorkflowStatus.READY,
            LeadWorkflowStatus.HOLD,
        }
    ),
    LeadWorkflowStatus.REVIEW: frozenset(
        {
            LeadWorkflowStatus.READY,
            LeadWorkflowStatus.HOLD,
            LeadWorkflowStatus.MONITOR,
        }
    ),
    LeadWorkflowStatus.READY: frozenset(
        {
            LeadWorkflowStatus.ACTIVE,
            LeadWorkflowStatus.PAUSED,
            LeadWorkflowStatus.CLOSED_NO_FIT,
        }
    ),
    LeadWorkflowStatus.ACTIVE: frozenset(
        {
            LeadWorkflowStatus.PAUSED,
            LeadWorkflowStatus.CLOSED_SUCCESS,
            LeadWorkflowStatus.CLOSED_NO_FIT,
        }
    ),
    LeadWorkflowStatus.PAUSED: frozenset(
        {
            LeadWorkflowStatus.ACTIVE,
            LeadWorkflowStatus.CLOSED_NO_FIT,
        }
    ),
    LeadWorkflowStatus.CLOSED_SUCCESS: frozenset(),
    LeadWorkflowStatus.CLOSED_NO_FIT: frozenset(),
}


def validate_lead_workflow_transition(
    current_status: LeadWorkflowStatus,
    next_status: LeadWorkflowStatus,
) -> None:
    """Raise when a status move is not allowed by the workflow matrix."""

    allowed_statuses = LEAD_WORKFLOW_TRANSITION_RULES[current_status]
    if next_status in allowed_statuses:
        return
    if current_status in FINAL_LEAD_WORKFLOW_STATUSES:
        raise ValueError(
            f"final lead workflow status {current_status.value!r} cannot move to "
            f"{next_status.value!r}"
        )
    allowed_values = ", ".join(status.value for status in sorted(allowed_statuses))
    raise ValueError(
        f"lead workflow status move from {current_status.value!r} to "
        f"{next_status.value!r} is not allowed; allowed next statuses: "
        f"{allowed_values}"
    )
