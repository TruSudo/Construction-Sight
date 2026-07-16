"""Build, verify, and time-check bounded CEQAnet CSV evidence policies."""

from __future__ import annotations

from datetime import date

from constructionsight.ceqanet_csv_access_policy_models import (
    CeqanetCsvAccessPolicy,
    CeqanetCsvAccessPolicyVerification,
)
from constructionsight.ceqanet_csv_live_models import CeqanetCsvLiveExecution
from constructionsight.ceqanet_csv_models import CeqanetCsvExportKind
from constructionsight.ceqanet_csv_replay_models import (
    CeqanetCsvEncodingReplay,
    CeqanetCsvEncodingReplayVerification,
)
from constructionsight.ceqanet_maturity_proposal_models import (
    CeqanetMaturityDecision,
    CeqanetSourceMaturityProposal,
    CeqanetSourceMaturityProposalVerification,
)
from constructionsight.ceqanet_maturity_proposal_service import (
    verify_ceqanet_source_maturity_proposal,
)
from constructionsight.models import PublicSource


def build_ceqanet_csv_access_policy(
    sources: list[PublicSource],
    execution: CeqanetCsvLiveExecution,
    replay: CeqanetCsvEncodingReplay,
    replay_verification: CeqanetCsvEncodingReplayVerification,
    maturity_proposal: CeqanetSourceMaturityProposal,
    maturity_verification: CeqanetSourceMaturityProposalVerification,
    *,
    effective_date: date,
    expires_on: date,
) -> CeqanetCsvAccessPolicy:
    """Build official-CSV-only evidence authority from exact current evidence."""

    recomputed_maturity_verification = verify_ceqanet_source_maturity_proposal(
        sources,
        execution,
        replay,
        replay_verification,
        maturity_proposal,
    )
    if maturity_verification != recomputed_maturity_verification:
        raise ValueError("stored maturity verification does not match current evidence")
    if not maturity_verification.passed:
        raise ValueError("CSV access policy requires a passing maturity verification")
    if maturity_proposal.decision is not CeqanetMaturityDecision.KEEP_PARTIAL:
        raise ValueError("CSV access policy requires a keep-partial maturity decision")

    draft = CeqanetCsvAccessPolicy(
        source_name=maturity_proposal.source_name,
        source_registry_digest=maturity_proposal.source_registry_digest,
        maturity_proposal_digest=maturity_proposal.proposal_digest,
        live_execution_digest=maturity_proposal.live_execution_digest,
        replay_digest=maturity_proposal.replay_digest,
        allowed_export_kinds=[
            CeqanetCsvExportKind.PROJECT,
            CeqanetCsvExportKind.DOCUMENT,
        ],
        halt_status_codes=[401, 403, 407, 429, 451],
        effective_date=effective_date,
        expires_on=expires_on,
        minimum_successful_observations=4,
        minimum_distinct_utc_dates=3,
        required_evidence_export_kinds=[
            CeqanetCsvExportKind.PROJECT,
            CeqanetCsvExportKind.DOCUMENT,
        ],
        production_blockers=[
            "the canonical source registry remains partial",
            "a governed multi-run CSV evidence series is not yet complete",
            "no persistent attempt ledger or production scheduler exists",
        ],
        limitations=[
            "policy authority is limited to explicit evidence collection",
            "each execution permits one official CSV GET and zero retries",
            "any access-control response halts the evidence series without bypass",
            "policy expiry requires a new evidence-bound policy digest",
        ],
        next_gate=(
            "collect and independently verify at least four bounded observations "
            "across three UTC dates and both project and document export scopes"
        ),
        policy_digest="0" * 64,
    )
    policy = draft.model_copy(update={"policy_digest": draft.computed_digest()})
    policy.assert_integrity()
    return policy


def verify_ceqanet_csv_access_policy(
    sources: list[PublicSource],
    execution: CeqanetCsvLiveExecution,
    replay: CeqanetCsvEncodingReplay,
    replay_verification: CeqanetCsvEncodingReplayVerification,
    maturity_proposal: CeqanetSourceMaturityProposal,
    maturity_verification: CeqanetSourceMaturityProposalVerification,
    policy: CeqanetCsvAccessPolicy,
) -> CeqanetCsvAccessPolicyVerification:
    """Recompute one policy from current registry and evidence content."""

    findings: list[str] = []
    try:
        policy.assert_integrity()
    except ValueError as exc:
        findings.append(str(exc))

    try:
        recomputed = build_ceqanet_csv_access_policy(
            sources,
            execution,
            replay,
            replay_verification,
            maturity_proposal,
            maturity_verification,
            effective_date=policy.effective_date,
            expires_on=policy.expires_on,
        )
    except ValueError as exc:
        findings.append(f"CSV access policy recomputation failed: {exc}")
    else:
        if policy.evidence_payload() != recomputed.evidence_payload():
            findings.append("CSV access policy does not match current evidence and governance")

    return CeqanetCsvAccessPolicyVerification(
        passed=not findings,
        finding_count=len(findings),
        findings=findings,
        policy_digest=policy.policy_digest,
        source_registry_digest=policy.source_registry_digest,
        maturity_proposal_digest=policy.maturity_proposal_digest,
        live_execution_digest=policy.live_execution_digest,
        replay_digest=policy.replay_digest,
    )


def assert_ceqanet_csv_access_policy_current(
    policy: CeqanetCsvAccessPolicy,
    *,
    as_of_date: date,
) -> None:
    """Reject evidence execution outside the exact reviewed authority window."""

    policy.assert_integrity()
    if as_of_date < policy.effective_date:
        raise ValueError("CEQAnet CSV access policy is not yet effective")
    if as_of_date > policy.expires_on:
        raise ValueError("CEQAnet CSV access policy has expired")
