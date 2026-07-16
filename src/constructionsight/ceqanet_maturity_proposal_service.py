"""Build and independently verify report-only CEQAnet maturity proposals."""

from __future__ import annotations

from constructionsight.ceqanet_csv_live_models import CeqanetCsvLiveExecution
from constructionsight.ceqanet_csv_models import CeqanetCsvExportKind
from constructionsight.ceqanet_csv_replay_models import (
    CeqanetCsvEncodingReplay,
    CeqanetCsvEncodingReplayVerification,
)
from constructionsight.ceqanet_csv_replay_service import (
    verify_ceqanet_csv_encoding_replay,
)
from constructionsight.ceqanet_maturity_proposal_models import (
    CeqanetMaturityDecision,
    CeqanetSourceMaturityProposal,
    CeqanetSourceMaturityProposalVerification,
)
from constructionsight.models import PlatformFamily, PublicSource, VerificationStatus
from constructionsight.source_registry_integrity import source_registry_digest


def build_ceqanet_source_maturity_proposal(
    sources: list[PublicSource],
    execution: CeqanetCsvLiveExecution,
    replay: CeqanetCsvEncodingReplay,
    replay_verification: CeqanetCsvEncodingReplayVerification,
) -> CeqanetSourceMaturityProposal:
    """Bind current evidence into a non-mutating keep-partial proposal."""

    source = _ceqanet_source(sources)
    if source.verification_status is not VerificationStatus.PARTIAL:
        raise ValueError("CEQAnet maturity proposal requires registry status partial")

    execution.assert_integrity()
    if execution.status_code != 200:
        raise ValueError("CEQAnet maturity proposal requires an HTTP 200 execution")
    if execution.error is not None:
        raise ValueError("CEQAnet maturity proposal requires execution without network error")
    if not execution.retained_body_complete:
        raise ValueError("CEQAnet maturity proposal requires a complete retained body")
    if execution.request.export_kind is not CeqanetCsvExportKind.PROJECT:
        raise ValueError("CEQAnet maturity proposal requires the retained project export")
    if execution.documents_downloaded or execution.persistence_mutated:
        raise ValueError("CEQAnet maturity proposal refuses mutating or document evidence")

    replay.assert_integrity()
    if replay.inspection.encoding != "windows-1252":
        raise ValueError("CEQAnet maturity proposal requires the verified Windows-1252 replay")
    if replay.inspection.rows_truncated:
        raise ValueError("CEQAnet maturity proposal requires all observed rows to be retained")
    if replay.inspection.row_count < 1:
        raise ValueError("CEQAnet maturity proposal requires at least one observed row")

    recomputed_verification = verify_ceqanet_csv_encoding_replay(execution, replay)
    if replay_verification != recomputed_verification:
        raise ValueError("stored replay verification does not match current evidence")
    if not replay_verification.passed:
        raise ValueError("CEQAnet maturity proposal requires a passing replay verification")

    draft = CeqanetSourceMaturityProposal(
        source_name=source.source_name,
        source_registry_digest=source_registry_digest(sources),
        live_execution_digest=execution.execution_digest,
        source_body_sha256=execution.body_sha256,
        replay_digest=replay.replay_digest,
        inspection_digest=replay.inspection.inspection_digest,
        observed_row_count=replay.inspection.row_count,
        decision=CeqanetMaturityDecision.KEEP_PARTIAL,
        reasons=[
            "one retained official CSV response returned HTTP 200",
            "the exact retained response independently replays as Windows-1252",
            "execution, body, inspection, and replay digests are bound",
        ],
        blockers=[
            "one point-in-time response does not establish recurring availability",
            "retained evidence does not authorize recurring automated access",
            "the canonical source registry status remains partial",
        ],
        limitations=[
            "this proposal is offline, report-only, and does not mutate the registry",
            "the HTML automated-access barrier remains outside the CSV proof",
            "no scheduler, cadence, retry policy, or recurring success series is established",
        ],
        next_gate=(
            "review a separate bounded CSV recurring-access policy and collect a governed "
            "multi-run evidence series before any source promotion"
        ),
        proposal_digest="0" * 64,
    )
    proposal = draft.model_copy(update={"proposal_digest": draft.computed_digest()})
    proposal.assert_integrity()
    return proposal


def verify_ceqanet_source_maturity_proposal(
    sources: list[PublicSource],
    execution: CeqanetCsvLiveExecution,
    replay: CeqanetCsvEncodingReplay,
    replay_verification: CeqanetCsvEncodingReplayVerification,
    proposal: CeqanetSourceMaturityProposal,
) -> CeqanetSourceMaturityProposalVerification:
    """Independently recompute proposal authority and evidence bindings."""

    findings: list[str] = []
    try:
        proposal.assert_integrity()
    except ValueError as exc:
        findings.append(str(exc))

    try:
        recomputed = build_ceqanet_source_maturity_proposal(
            sources,
            execution,
            replay,
            replay_verification,
        )
    except ValueError as exc:
        findings.append(f"maturity proposal recomputation failed: {exc}")
    else:
        if proposal.evidence_payload() != recomputed.evidence_payload():
            findings.append("maturity proposal does not match current evidence and registry")

    return CeqanetSourceMaturityProposalVerification(
        passed=not findings,
        finding_count=len(findings),
        findings=findings,
        proposal_digest=proposal.proposal_digest,
        source_registry_digest=proposal.source_registry_digest,
        live_execution_digest=proposal.live_execution_digest,
        replay_digest=proposal.replay_digest,
    )


def _ceqanet_source(sources: list[PublicSource]) -> PublicSource:
    matches = [source for source in sources if source.platform_family is PlatformFamily.CEQANET]
    if len(matches) != 1:
        raise ValueError("source registry must contain exactly one CEQAnet source")
    return matches[0]
