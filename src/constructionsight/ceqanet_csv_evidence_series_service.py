"""Build, execute, and verify governed CEQAnet CSV evidence series."""

from __future__ import annotations

from datetime import datetime

from constructionsight.authorization_decision_models import authorization_digest
from constructionsight.ceqanet_csv_access_policy_models import (
    CeqanetCsvAccessPolicy,
    CeqanetCsvAccessPolicyVerification,
)
from constructionsight.ceqanet_csv_access_policy_service import (
    assert_ceqanet_csv_access_policy_current,
    verify_ceqanet_csv_access_policy,
)
from constructionsight.ceqanet_csv_evidence_series_models import (
    CeqanetCsvEvidenceExecution,
    CeqanetCsvEvidenceObservation,
    CeqanetCsvEvidenceSeries,
    CeqanetCsvEvidenceSeriesStatus,
    CeqanetCsvEvidenceSeriesVerification,
)
from constructionsight.ceqanet_csv_live_models import CeqanetCsvLiveExecution
from constructionsight.ceqanet_csv_live_service import (
    execute_ceqanet_csv_live_request,
    verify_ceqanet_csv_live_execution,
)
from constructionsight.ceqanet_csv_models import CeqanetCsvExportRequest
from constructionsight.ceqanet_csv_replay_models import (
    CeqanetCsvEncodingReplay,
    CeqanetCsvEncodingReplayVerification,
)
from constructionsight.ceqanet_maturity_proposal_models import (
    CeqanetSourceMaturityProposal,
    CeqanetSourceMaturityProposalVerification,
)
from constructionsight.effect_consumption import _execute_owned_effect, trusted_utc_now
from constructionsight.effect_consumption_models import EffectReplayPolicy
from constructionsight.local_operator_authorization import (
    authorize_local_operator_operation,
)
from constructionsight.models import PublicSource

EvidenceExecutionInput = tuple[str, CeqanetCsvEvidenceExecution]


def build_ceqanet_csv_evidence_series(
    sources: list[PublicSource],
    original_execution: CeqanetCsvLiveExecution,
    replay: CeqanetCsvEncodingReplay,
    replay_verification: CeqanetCsvEncodingReplayVerification,
    maturity_proposal: CeqanetSourceMaturityProposal,
    maturity_verification: CeqanetSourceMaturityProposalVerification,
    policy: CeqanetCsvAccessPolicy,
    policy_verification: CeqanetCsvAccessPolicyVerification,
    evidence_executions: list[EvidenceExecutionInput],
) -> CeqanetCsvEvidenceSeries:
    """Build one immutable ledger snapshot from complete evidence executions."""

    _assert_policy_verified(
        sources,
        original_execution,
        replay,
        replay_verification,
        maturity_proposal,
        maturity_verification,
        policy,
        policy_verification,
    )
    observations = sorted(
        (
            _build_observation(policy, artifact_ref, evidence_execution)
            for artifact_ref, evidence_execution in evidence_executions
        ),
        key=lambda item: (
            item.executed_at,
            item.evidence_execution_digest,
        ),
    )
    series = _build_series_snapshot(
        policy,
        observations=[],
        predecessor_series_digest=None,
    )
    for sequence in range(1, len(observations) + 1):
        if series.status is not CeqanetCsvEvidenceSeriesStatus.COLLECTING:
            raise ValueError("terminal evidence series cannot accept later observations")
        series = _build_series_snapshot(
            policy,
            observations=observations[:sequence],
            predecessor_series_digest=series.series_digest,
        )
    return series


def verify_ceqanet_csv_evidence_series(
    sources: list[PublicSource],
    original_execution: CeqanetCsvLiveExecution,
    replay: CeqanetCsvEncodingReplay,
    replay_verification: CeqanetCsvEncodingReplayVerification,
    maturity_proposal: CeqanetSourceMaturityProposal,
    maturity_verification: CeqanetSourceMaturityProposalVerification,
    policy: CeqanetCsvAccessPolicy,
    policy_verification: CeqanetCsvAccessPolicyVerification,
    evidence_executions: list[EvidenceExecutionInput],
    series: CeqanetCsvEvidenceSeries,
) -> CeqanetCsvEvidenceSeriesVerification:
    """Independently rebuild a series from current policy and response evidence."""

    findings: list[str] = []
    try:
        series.assert_integrity()
    except ValueError as exc:
        findings.append(str(exc))

    try:
        recomputed = build_ceqanet_csv_evidence_series(
            sources,
            original_execution,
            replay,
            replay_verification,
            maturity_proposal,
            maturity_verification,
            policy,
            policy_verification,
            evidence_executions,
        )
    except ValueError as exc:
        findings.append(f"CEQAnet CSV evidence series recomputation failed: {exc}")
    else:
        if series.evidence_payload() != recomputed.evidence_payload():
            findings.append(
                "CEQAnet CSV evidence series does not match current policy "
                "and execution artifacts"
            )

    return CeqanetCsvEvidenceSeriesVerification(
        passed=not findings,
        finding_count=len(findings),
        findings=findings,
        policy_digest=series.policy_digest,
        series_digest=series.series_digest,
        observation_count=series.observation_count,
        successful_observation_count=series.successful_observation_count,
        ready_for_maturity_review=(
            not findings
            and series.status
            is CeqanetCsvEvidenceSeriesStatus.READY_FOR_MATURITY_REVIEW
        ),
    )


def execute_ceqanet_csv_evidence_request(
    sources: list[PublicSource],
    original_execution: CeqanetCsvLiveExecution,
    replay: CeqanetCsvEncodingReplay,
    replay_verification: CeqanetCsvEncodingReplayVerification,
    maturity_proposal: CeqanetSourceMaturityProposal,
    maturity_verification: CeqanetSourceMaturityProposalVerification,
    policy: CeqanetCsvAccessPolicy,
    policy_verification: CeqanetCsvAccessPolicyVerification,
    series: CeqanetCsvEvidenceSeries,
    existing_evidence_executions: list[EvidenceExecutionInput],
    request: CeqanetCsvExportRequest,
    *,
    execute_live: bool,
    max_retained_rows: int = 1_000,
    operator_id: str | None = None,
    authorization_reason: str = (
        "Execute one policy-bound CEQAnet CSV evidence request."
    ),
) -> CeqanetCsvEvidenceExecution:
    """Authorize one policy-bound GET after independently verifying the ledger."""

    if not execute_live:
        raise ValueError(
            "explicit live confirmation is required for CEQAnet CSV evidence"
        )
    authorized_at = trusted_utc_now()

    series_verification = verify_ceqanet_csv_evidence_series(
        sources,
        original_execution,
        replay,
        replay_verification,
        maturity_proposal,
        maturity_verification,
        policy,
        policy_verification,
        existing_evidence_executions,
        series,
    )
    if not series_verification.passed:
        raise ValueError(
            "current CEQAnet CSV evidence series failed independent verification"
        )
    assert_ceqanet_csv_access_policy_current(
        policy,
        as_of_date=authorized_at.date(),
    )
    if series.status is not CeqanetCsvEvidenceSeriesStatus.COLLECTING:
        raise ValueError(
            "CEQAnet CSV evidence execution requires a collecting series"
        )
    if any(item.utc_date == authorized_at.date() for item in series.observations):
        raise ValueError(
            "CEQAnet CSV policy permits at most one execution per UTC day"
        )
    if series.observations and authorized_at <= series.observations[-1].executed_at:
        raise ValueError("execution authorization must follow the current series head")
    if not 0 <= max_retained_rows <= 1_000:
        raise ValueError("max_retained_rows must be between 0 and 1000")
    if request.export_kind not in policy.allowed_export_kinds:
        raise ValueError("CEQAnet CSV export kind is not allowed by policy")

    state_identity = authorization_digest(
        "ceqanet-csv-evidence-state",
        {
            "policy_digest": policy.policy_digest,
            "series_digest": series.series_digest,
            "series_sequence": series.series_sequence,
            "series_status": series.status.value,
            "series_verification": series_verification.model_dump(mode="json"),
            "existing_execution_digests": [
                execution.evidence_execution_digest
                for _artifact_ref, execution in existing_evidence_executions
            ],
            "request": request.model_dump(mode="json"),
            "authorized_utc_date": authorized_at.date().isoformat(),
            "timeout_seconds": policy.timeout_seconds,
            "max_body_bytes": policy.max_body_bytes,
            "max_retained_rows": max_retained_rows,
        },
    )
    resource_id = authorization_digest(
        "ceqanet-csv-evidence-resource",
        {
            "policy_digest": policy.policy_digest,
            "source_name": series.source_name,
        },
    )
    exact_scope = tuple(
        sorted(
            {
                f"authorized-utc-date:{authorized_at.date().isoformat()}",
                f"export-kind:{request.export_kind.value}",
                f"max-body-bytes:{policy.max_body_bytes}",
                f"max-retained-rows:{max_retained_rows}",
                "method:GET",
                f"policy-digest:{policy.policy_digest}",
                "policy:CS-NET-003",
                "redirects:denied",
                "retries:0",
                f"series-digest:{series.series_digest}",
                f"timeout-seconds:{policy.timeout_seconds:g}",
                f"url:{request.source_url}",
            },
            key=str.casefold,
        )
    )
    authorization = authorize_local_operator_operation(
        action="execute-ceqanet-csv-evidence-request",
        resource_type="ceqanet-csv-evidence-series",
        resource_id=resource_id,
        exact_scope=exact_scope,
        current_state_identity=state_identity,
        expected_identity=state_identity,
        granted_authority=(
            "execute one exact policy-bound CEQAnet CSV evidence GET",
        ),
        denied_authority=tuple(
            sorted(
                {
                    "access-control bypass",
                    "credential use",
                    "document download",
                    "multiple executions per UTC day",
                    "persistence mutation",
                    "policy bypass",
                    "production recurrence",
                    "redirect following",
                    "request mutation",
                    "retry",
                    "series mutation",
                    "source promotion",
                },
                key=str.casefold,
            )
        ),
        reason=authorization_reason,
        caller_confirmation=execute_live,
        limitations=tuple(
            sorted(
                {
                    "local operator identity is not authentication",
                    "the execution artifact does not itself advance the series",
                    "the request cannot authorize maturity promotion or recurrence",
                    "one durable UTC-date allowance across processes",
                },
                key=str.casefold,
            )
        ),
        operator_id=operator_id,
        current_revocation_identity=state_identity,
    )

    def execute(trusted_at: datetime) -> CeqanetCsvEvidenceExecution:
        live_execution = execute_ceqanet_csv_live_request(
            request,
            execute_live=True,
            timeout_seconds=policy.timeout_seconds,
            max_body_bytes=policy.max_body_bytes,
            max_retained_rows=max_retained_rows,
            executed_at=trusted_at,
        )
        live_verification = verify_ceqanet_csv_live_execution(live_execution)
        draft = CeqanetCsvEvidenceExecution(
            policy_digest=policy.policy_digest,
            authorization_granted_at=authorized_at,
            authorized_utc_date=trusted_at.date(),
            timeout_seconds=policy.timeout_seconds,
            max_body_bytes=policy.max_body_bytes,
            max_retained_rows=max_retained_rows,
            live_execution=live_execution,
            live_verification=live_verification,
            evidence_execution_digest="0" * 64,
        )
        evidence_execution = draft.model_copy(
            update={"evidence_execution_digest": draft.computed_digest()}
        )
        evidence_execution.assert_integrity()
        return evidence_execution

    return _execute_owned_effect(
        authorization,
        allowance_identity=authorization_digest(
            "ceqanet-csv-daily-allowance",
            {
                "policy_digest": policy.policy_digest,
                "source_name": series.source_name,
                "utc_date": authorized_at.date().isoformat(),
            },
        ),
        content_identity=state_identity,
        implementation_id=(
            "constructionsight.ceqanet_csv_live_service."
            "execute_ceqanet_csv_live_request"
        ),
        replay_policy=EffectReplayPolicy.EXACT,
        effect=execute,
        encode_result=lambda result: result.model_dump(mode="json"),
        decode_result=lambda payload: CeqanetCsvEvidenceExecution.model_validate(payload),
        required_utc_date=authorized_at.date(),
    )


def _build_series_snapshot(
    policy: CeqanetCsvAccessPolicy,
    *,
    observations: list[CeqanetCsvEvidenceObservation],
    predecessor_series_digest: str | None,
) -> CeqanetCsvEvidenceSeries:
    successful = [item for item in observations if item.successful]
    successful_dates = sorted({item.utc_date for item in successful})
    successful_kinds = sorted(
        {item.export_kind for item in successful},
        key=lambda item: item.value,
    )
    halted = next(
        (item for item in observations if item.access_control_halt),
        None,
    )
    ready = (
        halted is None
        and len(successful) >= policy.minimum_successful_observations
        and len(successful_dates) >= policy.minimum_distinct_utc_dates
        and set(successful_kinds) == set(policy.required_evidence_export_kinds)
    )
    if halted is not None:
        status = CeqanetCsvEvidenceSeriesStatus.HALTED
        next_gate = (
            "halt evidence collection and review the retained access-control "
            "response without bypass"
        )
    elif ready:
        status = CeqanetCsvEvidenceSeriesStatus.READY_FOR_MATURITY_REVIEW
        next_gate = (
            "perform a separate evidence-bound maturity review; this series "
            "does not itself authorize promotion or production execution"
        )
    else:
        status = CeqanetCsvEvidenceSeriesStatus.COLLECTING
        next_gate = policy.next_gate

    draft = CeqanetCsvEvidenceSeries(
        source_name=policy.source_name,
        policy_digest=policy.policy_digest,
        policy_effective_date=policy.effective_date,
        policy_expires_on=policy.expires_on,
        observations=observations,
        series_sequence=len(observations),
        predecessor_series_digest=predecessor_series_digest,
        observation_count=len(observations),
        successful_observation_count=len(successful),
        distinct_successful_utc_dates=successful_dates,
        observed_successful_export_kinds=successful_kinds,
        minimum_successful_observations=policy.minimum_successful_observations,
        minimum_distinct_utc_dates=policy.minimum_distinct_utc_dates,
        required_export_kinds=policy.required_evidence_export_kinds,
        status=status,
        halted_on=halted.utc_date if halted is not None else None,
        halt_status_code=halted.status_code if halted is not None else None,
        next_gate=next_gate,
        series_digest="0" * 64,
    )
    series = draft.model_copy(update={"series_digest": draft.computed_digest()})
    series.assert_integrity()
    return series


def _assert_policy_verified(
    sources: list[PublicSource],
    original_execution: CeqanetCsvLiveExecution,
    replay: CeqanetCsvEncodingReplay,
    replay_verification: CeqanetCsvEncodingReplayVerification,
    maturity_proposal: CeqanetSourceMaturityProposal,
    maturity_verification: CeqanetSourceMaturityProposalVerification,
    policy: CeqanetCsvAccessPolicy,
    policy_verification: CeqanetCsvAccessPolicyVerification,
) -> None:
    recomputed = verify_ceqanet_csv_access_policy(
        sources,
        original_execution,
        replay,
        replay_verification,
        maturity_proposal,
        maturity_verification,
        policy,
    )
    if policy_verification != recomputed:
        raise ValueError(
            "stored CEQAnet CSV policy verification does not match current evidence"
        )
    if not policy_verification.passed:
        raise ValueError(
            "CEQAnet CSV evidence series requires a passing policy verification"
        )


def _build_observation(
    policy: CeqanetCsvAccessPolicy,
    artifact_ref: str,
    evidence_execution: CeqanetCsvEvidenceExecution,
) -> CeqanetCsvEvidenceObservation:
    evidence_execution.assert_integrity()
    if evidence_execution.policy_digest != policy.policy_digest:
        raise ValueError("evidence execution policy digest does not match series policy")
    if evidence_execution.timeout_seconds != policy.timeout_seconds:
        raise ValueError("evidence execution timeout does not match policy")
    if evidence_execution.max_body_bytes != policy.max_body_bytes:
        raise ValueError("evidence execution body limit does not match policy")

    live = evidence_execution.live_execution
    verification = verify_ceqanet_csv_live_execution(live)
    if verification != evidence_execution.live_verification:
        raise ValueError(
            "stored live verification does not match retained execution evidence"
        )
    assert_ceqanet_csv_access_policy_current(
        policy,
        as_of_date=evidence_execution.authorized_utc_date,
    )
    if live.request.export_kind not in policy.allowed_export_kinds:
        raise ValueError("evidence execution export kind is not allowed by policy")

    draft = CeqanetCsvEvidenceObservation(
        evidence_execution_artifact_ref=artifact_ref,
        policy_digest=policy.policy_digest,
        evidence_execution_digest=evidence_execution.evidence_execution_digest,
        live_execution_digest=live.execution_digest,
        executed_at=live.executed_at,
        utc_date=evidence_execution.authorized_utc_date,
        export_kind=live.request.export_kind,
        sch_number=live.request.sch_number,
        document_id=live.request.document_id,
        request_url=live.request_url,
        status_code=live.status_code,
        observed_body_byte_length=live.observed_body_byte_length,
        retained_body_complete=live.retained_body_complete,
        body_sha256=live.body_sha256,
        inspection_digest=verification.inspection_digest,
        verification_passed=verification.passed,
        verification_finding_count=verification.finding_count,
        verification_findings=verification.findings,
        successful=verification.passed,
        access_control_halt=(
            live.status_code in policy.halt_status_codes
            if live.status_code is not None
            else False
        ),
        observation_digest="0" * 64,
    )
    observation = draft.model_copy(
        update={"observation_digest": draft.computed_digest()}
    )
    observation.assert_integrity()
    return observation
